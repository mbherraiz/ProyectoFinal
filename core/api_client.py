"""
Cliente HTTP para la Steam Web API (IPlayerService/GetOwnedGames)
y descargador asíncrono de carátulas desde la CDN oficial de Steam.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests
from config import COVERS_DIR, STEAM_API_BASE_URL, STEAM_CDN_COVER_URL
from logger import get_logger

logger = get_logger("APIClient")


class SteamAPIError(Exception):
    """Excepción para errores de respuesta de la Steam Web API (credenciales inválidas, perfil privado, etc.)."""
    pass


class SteamNetworkError(Exception):
    """Excepción para fallos de red o falta de conexión a internet."""
    pass


def fetch_owned_games(steamid_input: Any, api_key: str, timeout: float = 12.0) -> List[Dict[str, Any]]:
    """
    Consulta la Steam Web API para obtener el catálogo de juegos.
    Permite consultar una sola cuenta o múltiples cuentas (ej. Grupo Familiar / Family Sharing).
    steamid_input puede ser un string único, lista de strings, o strings separados por comas.
    Retorna la lista unificada de juegos sin duplicados.
    """
    if not steamid_input or not api_key:
        raise SteamAPIError("SteamID64 y API Key son obligatorios para consultar la biblioteca.")

    if isinstance(steamid_input, str):
        # Separar por comas o saltos de línea si se ingresaron varios IDs
        raw_ids = [s.strip() for s in steamid_input.replace("\n", ",").split(",") if s.strip()]
    elif isinstance(steamid_input, (list, tuple, set)):
        raw_ids = [str(s).strip() for s in steamid_input if str(s).strip()]
    else:
        raw_ids = [str(steamid_input).strip()]

    if not raw_ids:
        raise SteamAPIError("No se proporcionó ningún SteamID64 válido.")

    endpoint = f"{STEAM_API_BASE_URL}/IPlayerService/GetOwnedGames/v0001/"
    all_games_map: Dict[int, Dict[str, Any]] = {}
    successful_queries = 0
    last_error = None

    for sid in raw_ids:
        params = {
            "key": api_key,
            "steamid": sid,
            "include_appinfo": "1",
            "include_played_free_games": "1",
            "format": "json"
        }

        try:
            logger.info(f"Consultando catálogo en Steam Web API para cuenta {sid}...")
            response = requests.get(endpoint, params=params, timeout=timeout)

            if response.status_code == 200:
                data = response.json()
                games = data.get("response", {}).get("games", [])
                successful_queries += 1
                for g in games:
                    appid = int(g["appid"])
                    if appid not in all_games_map:
                        g["owner_steamid"] = sid
                        all_games_map[appid] = g
                logger.info(f"Cuenta {sid}: {len(games)} juegos obtenidos.")
            elif response.status_code in (401, 403):
                logger.warning(f"Cuenta {sid}: Perfil privado o sin permisos.")
                last_error = f"La cuenta {sid} tiene el perfil de juegos privado."
            else:
                logger.warning(f"Cuenta {sid}: Error HTTP {response.status_code}")
                last_error = f"Error HTTP {response.status_code} al consultar {sid}."

        except requests.exceptions.ConnectionError:
            raise SteamNetworkError("No se pudo conectar a los servidores de Steam. Comprueba tu conexión.")
        except requests.exceptions.Timeout:
            raise SteamNetworkError("Tiempo de espera agotado al conectar a Steam.")
        except Exception as e:
            logger.error(f"Error consultando cuenta {sid}: {e}")
            last_error = str(e)

    if not all_games_map and successful_queries == 0:
        if last_error:
            raise SteamAPIError(last_error)
        raise SteamAPIError("No se pudieron obtener juegos de las cuentas proporcionadas.")

    unified_games = list(all_games_map.values())
    logger.info(f"Total de juegos unificados de la biblioteca familiar/personal: {len(unified_games)}")
    return unified_games


def get_cached_cover_path(appid: int) -> Optional[Path]:
    """Retorna la ruta a la carátula si ya está descargada en el caché local."""
    path = COVERS_DIR / f"{appid}.jpg"
    return path if path.exists() and path.stat().st_size > 0 else None


def download_game_cover(appid: int, timeout: float = 8.0) -> Optional[Path]:
    """
    Descarga la imagen horizontal header.jpg de la CDN oficial de Steam
    y la guarda en cache/covers/{appid}.jpg.
    Retorna la ruta al archivo descargado o None si no existe o falla.
    """
    cached = get_cached_cover_path(appid)
    if cached:
        return cached

    url = STEAM_CDN_COVER_URL.format(appid=appid)
    dest_path = COVERS_DIR / f"{appid}.jpg"

    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200 and len(response.content) > 500:
            with open(dest_path, "wb") as f:
                f.write(response.content)
            return dest_path
        else:
            return None
    except Exception:
        # Fallos en carátulas son comunes (algunas apps antiguas no tienen header.jpg)
        return None


def download_covers_pool(
    appids: List[int],
    on_cover_ready: Optional[Callable[[int, Path], None]] = None,
    max_workers: int = 6
) -> None:
    """
    Descarga carátulas de juegos en paralelo usando ThreadPoolExecutor.
    Invoca el callback on_cover_ready(appid, path) cuando cada imagen esté lista.
    """
    def _worker(appid: int):
        path = download_game_cover(appid)
        if path and on_cover_ready:
            try:
                on_cover_ready(appid, path)
            except Exception as e:
                logger.error(f"Error en callback on_cover_ready para AppID {appid}: {e}")

    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="CoverDownloader") as executor:
        for appid in appids:
            executor.submit(_worker, appid)
