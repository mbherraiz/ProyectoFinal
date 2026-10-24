"""
Gestor de base de datos SQLite para la caché local de juegos y ajustes de usuario.
Garantiza el modo sin conexión (Offline Fallback) y la persistencia de configuraciones.
"""

import sqlite3
import threading
from typing import Any, Dict, List, Optional
from config import DB_FILE
from logger import get_logger

logger = get_logger("Database")
_db_lock = threading.Lock()


def get_connection() -> sqlite3.Connection:
    """Crea una conexión a la base de datos con row_factory para acceso por clave."""
    conn = sqlite3.connect(str(DB_FILE), check_same_thread=False, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Crea las tablas necesarias si no existen."""
    with _db_lock, get_connection() as conn:
        cursor = conn.cursor()

        # Tabla de ajustes de la aplicación
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Tabla de juegos instalados localmente en disco
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS installed_games (
                appid INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                install_dir TEXT,
                size_bytes INTEGER DEFAULT 0,
                library_path TEXT,
                cover_path TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabla de catálogo completo de la biblioteca (Steam Web API)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS library_games (
                appid INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                playtime_forever INTEGER DEFAULT 0,
                img_icon_url TEXT,
                cover_path TEXT,
                is_installed INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insertar valores predeterminados de ajustes si no existen
        defaults = {
            "steamid64": "",
            "family_steamids": "",
            "api_key": "",
            "ultra_light_mode": "1",
            "enable_overlay": "1",
            "disable_overlay": "0",
            "minimize_to_tray": "1",
            "steam_custom_path": ""
        }
        for k, v in defaults.items():
            cursor.execute("""
                INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)
            """, (k, v))

        conn.commit()
    logger.info("Base de datos SQLite inicializada correctamente.")


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Obtiene un valor de la tabla de ajustes."""
    with _db_lock, get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row:
            return row["value"]
        return default


def set_setting(key: str, value: Any) -> None:
    """Inserta o actualiza un ajuste en la base de datos."""
    with _db_lock, get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, str(value)))
        conn.commit()
    logger.debug(f"Ajuste guardado: {key}={value}")


def get_all_settings() -> Dict[str, str]:
    """Retorna todos los ajustes en un diccionario."""
    with _db_lock, get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        return {r["key"]: r["value"] for r in rows}


def save_installed_games(games: List[Dict[str, Any]]) -> None:
    """
    Guarda o actualiza la lista de juegos instalados detectados en disco.
    """
    with _db_lock, get_connection() as conn:
        cursor = conn.cursor()
        # Limpiamos registros anteriores para reflejar desinstalaciones
        cursor.execute("DELETE FROM installed_games")

        for g in games:
            cursor.execute("""
                INSERT INTO installed_games (appid, name, install_dir, size_bytes, library_path, cover_path)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                int(g["appid"]),
                g.get("name", f"App {g['appid']}"),
                g.get("install_dir", ""),
                int(g.get("size_bytes", 0)),
                g.get("library_path", ""),
                g.get("cover_path", "")
            ))
        conn.commit()
    logger.info(f"Guardados {len(games)} juegos instalados en la base de datos local.")


def get_installed_games() -> List[Dict[str, Any]]:
    """Obtiene los juegos instalados almacenados en la base de datos."""
    with _db_lock, get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM installed_games ORDER BY name COLLATE NOCASE ASC")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def save_library_games(games: List[Dict[str, Any]]) -> None:
    """
    Guarda o actualiza el catálogo completo obtenido de la Steam Web API.
    """
    with _db_lock, get_connection() as conn:
        cursor = conn.cursor()
        for g in games:
            cursor.execute("""
                INSERT INTO library_games (appid, name, playtime_forever, img_icon_url, cover_path, is_installed)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(appid) DO UPDATE SET
                    name = excluded.name,
                    playtime_forever = excluded.playtime_forever,
                    img_icon_url = excluded.img_icon_url,
                    cover_path = COALESCE(excluded.cover_path, library_games.cover_path),
                    is_installed = excluded.is_installed,
                    last_updated = CURRENT_TIMESTAMP
            """, (
                int(g["appid"]),
                g.get("name", f"App {g['appid']}"),
                int(g.get("playtime_forever", 0)),
                g.get("img_icon_url", ""),
                g.get("cover_path", ""),
                1 if g.get("is_installed") else 0
            ))
        conn.commit()
    logger.info(f"Guardados/actualizados {len(games)} juegos en la caché de biblioteca completa.")


def get_library_games() -> List[Dict[str, Any]]:
    """Obtiene el catálogo completo de la biblioteca en caché."""
    with _db_lock, get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM library_games ORDER BY name COLLATE NOCASE ASC")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def update_cover_path(appid: int, cover_path: str) -> None:
    """Actualiza la ruta de la carátula local de un juego tanto en installed como en library."""
    with _db_lock, get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE installed_games SET cover_path = ? WHERE appid = ?", (cover_path, appid))
        cursor.execute("UPDATE library_games SET cover_path = ? WHERE appid = ?", (cover_path, appid))
        conn.commit()


def mark_as_installed(appid: int, is_installed: bool) -> None:
    """Actualiza el estado de instalación de un juego en la biblioteca."""
    with _db_lock, get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE library_games SET is_installed = ? WHERE appid = ?", (1 if is_installed else 0, appid))
        conn.commit()
