"""
Detección de la instalación de Steam vía Windows Registry (winreg),
descubrimiento de bibliotecas secundarias mediante libraryfolders.vdf
y extracción de juegos instalados desde archivos appmanifest_*.acf.
"""

import os
import re
import sys
import winreg
from pathlib import Path
from typing import Any, Dict, List, Optional

import vdf
from logger import get_logger

logger = get_logger("SteamDetector")


def get_steam_install_path(custom_path: Optional[str] = None) -> Optional[Path]:
    """
    Detecta la ruta de instalación de Steam buscando en:
    1. Ruta personalizada provista por el usuario.
    2. Registro de Windows HKCU\\Software\\Valve\\Steam\\SteamPath.
    3. Registro de Windows HKLM\\SOFTWARE\\WOW6432Node\\Valve\\Steam\\InstallPath.
    4. Rutas comunes predeterminadas de Windows.
    """
    if custom_path and Path(custom_path).exists():
        logger.info(f"Usando ruta personalizada de Steam: {custom_path}")
        return Path(custom_path).resolve()

    # 1. HKCU\Software\Valve\Steam (SteamPath)
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            val, _ = winreg.QueryValueEx(key, "SteamPath")
            if val:
                path = Path(val).resolve()
                if path.exists():
                    logger.info(f"Steam detectado en HKCU: {path}")
                    return path
    except Exception as e:
        logger.debug(f"No se pudo leer SteamPath de HKCU: {e}")

    # 2. HKLM\SOFTWARE\WOW6432Node\Valve\Steam (InstallPath)
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam") as key:
            val, _ = winreg.QueryValueEx(key, "InstallPath")
            if val:
                path = Path(val).resolve()
                if path.exists():
                    logger.info(f"Steam detectado en HKLM: {path}")
                    return path
    except Exception as e:
        logger.debug(f"No se pudo leer InstallPath de HKLM: {e}")

    # 3. Rutas típicas por defecto
    default_candidates = [
        Path(r"C:\Program Files (x86)\Steam"),
        Path(r"C:\Program Files\Steam"),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Steam",
    ]
    for candidate in default_candidates:
        if candidate.exists() and (candidate / "steam.exe").exists():
            logger.info(f"Steam detectado en ruta típica: {candidate}")
            return candidate.resolve()

    logger.warning("No se pudo detectar la ruta de instalación de Steam automáticamente.")
    return None


def get_steam_executable(steam_path: Optional[Path] = None) -> Optional[Path]:
    """Retorna la ruta al ejecutable steam.exe."""
    base = steam_path or get_steam_install_path()
    if not base:
        return None
    exe = base / "steam.exe"
    return exe.resolve() if exe.exists() else None


def get_library_folders(steam_path: Optional[Path] = None) -> List[Path]:
    """
    Descubre todas las carpetas de biblioteca de Steam (discos primario y secundarios)
    analizando el archivo 'steamapps/libraryfolders.vdf'.
    """
    base = steam_path or get_steam_install_path()
    if not base:
        return []

    libraries: List[Path] = []
    # Siempre incluir la biblioteca principal
    primary_apps = base / "steamapps"
    if primary_apps.exists():
        libraries.append(base)

    vdf_file = primary_apps / "libraryfolders.vdf"
    if not vdf_file.exists():
        return libraries

    try:
        with open(vdf_file, "r", encoding="utf-8", errors="ignore") as f:
            data = vdf.load(f)

        folders_dict = data.get("libraryfolders", {})
        for _, info in folders_dict.items():
            if isinstance(info, dict) and "path" in info:
                lib_path = Path(info["path"]).resolve()
                if lib_path.exists() and (lib_path / "steamapps").exists():
                    if lib_path not in libraries:
                        libraries.append(lib_path)
    except Exception as e:
        logger.error(f"Error parseando {vdf_file} con vdf: {e}. Intentando fallback regex.")
        # Fallback por regex si vdf falla
        try:
            with open(vdf_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            matches = re.findall(r'"path"\s+"([^"]+)"', content)
            for m in matches:
                p = Path(m.replace("\\\\", "\\")).resolve()
                if p.exists() and (p / "steamapps").exists() and p not in libraries:
                    libraries.append(p)
        except Exception as re_err:
            logger.error(f"Fallo también en fallback regex: {re_err}")

    logger.debug(f"Bibliotecas de Steam detectadas ({len(libraries)}): {[str(p) for p in libraries]}")
    return libraries


def get_installed_games(steam_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Busca y parsea todos los archivos 'appmanifest_*.acf' en todas las carpetas de biblioteca.
    Filtra los juegos listos para jugar.
    """
    libraries = get_library_folders(steam_path)
    installed_games: List[Dict[str, Any]] = []

    # AppIDs de utilidades de Steam o redistribuibles que no son juegos reales
    IGNORED_APPIDS = {228980, 228983, 228984, 228985, 228986, 228988, 228990}

    for lib in libraries:
        steamapps_dir = lib / "steamapps"
        if not steamapps_dir.exists():
            continue

        for acf_file in steamapps_dir.glob("appmanifest_*.acf"):
            try:
                with open(acf_file, "r", encoding="utf-8", errors="ignore") as f:
                    data = vdf.load(f)

                app_state = data.get("AppState", {})
                if not app_state:
                    continue

                raw_appid = app_state.get("appid")
                if not raw_appid:
                    continue

                appid = int(raw_appid)
                if appid in IGNORED_APPIDS:
                    continue

                name = app_state.get("name", f"App {appid}")
                install_dir = app_state.get("installdir", "")
                size_bytes = int(app_state.get("SizeOnDisk", 0))
                state_flags = int(app_state.get("StateFlags", 4))

                # StateFlags == 4 indica que el juego está completamente instalado
                # Aunque si StateFlags tiene el bit de 4 (StateFlags & 4), está listo
                is_ready = (state_flags & 4) != 0 or state_flags == 4

                if is_ready:
                    installed_games.append({
                        "appid": appid,
                        "name": name,
                        "install_dir": install_dir,
                        "size_bytes": size_bytes,
                        "library_path": str(lib),
                        "manifest_path": str(acf_file),
                        "state_flags": state_flags
                    })

            except Exception as e:
                logger.warning(f"Error procesando manifiesto {acf_file.name}: {e}")

    logger.info(f"Total de juegos instalados detectados: {len(installed_games)}")
    return installed_games
