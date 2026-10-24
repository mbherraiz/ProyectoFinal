"""
Rastreador de descargas activas en steamapps/downloading/ y manifiestos ACF.
Calcula porcentaje de progreso, velocidad de descarga en tiempo real y tiempo estimado (ETA).
"""

import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import vdf
from core import steam_detector
from logger import get_logger

logger = get_logger("DownloadTracker")


class DownloadInfo:
    """Estructura de datos con el estado actual de una descarga."""
    def __init__(
        self,
        is_active: bool = False,
        appid: Optional[int] = None,
        game_name: str = "",
        progress_pct: float = 0.0,
        bytes_downloaded: int = 0,
        bytes_total: int = 0,
        speed_mb_s: float = 0.0,
        eta_str: str = ""
    ):
        self.is_active = is_active
        self.appid = appid
        self.game_name = game_name
        self.progress_pct = progress_pct
        self.bytes_downloaded = bytes_downloaded
        self.bytes_total = bytes_total
        self.speed_mb_s = speed_mb_s
        self.eta_str = eta_str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_active": self.is_active,
            "appid": self.appid,
            "game_name": self.game_name,
            "progress_pct": round(self.progress_pct, 1),
            "bytes_downloaded": self.bytes_downloaded,
            "bytes_total": self.bytes_total,
            "speed_mb_s": round(self.speed_mb_s, 2),
            "eta_str": self.eta_str,
            "speed_str": f"{self.speed_mb_s:.2f} MB/s" if self.speed_mb_s > 0 else "-- MB/s"
        }


class DownloadTracker:
    """
    Monitor en segundo plano que examina periódicamente las carpetas 'steamapps'
    y 'steamapps/downloading' de todas las bibliotecas de Steam detectadas.
    """

    def __init__(
        self,
        steam_path: Optional[Path] = None,
        callback: Optional[Callable[[DownloadInfo], None]] = None,
        poll_interval: float = 1.2
    ):
        self.steam_path = steam_path
        self.callback = callback
        self.poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Historial para cálculo de velocidad
        self._last_bytes: int = 0
        self._last_time: float = 0.0
        self._last_appid: Optional[int] = None
        self._cached_libraries: List[Path] = []
        self._last_lib_scan: float = 0.0

    def start(self) -> None:
        """Inicia el rastreador en un hilo secundario."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="DownloadTrackerThread", daemon=True)
        self._thread.start()
        logger.info("Monitor de descargas de Steam iniciado.")

    def stop(self) -> None:
        """Detiene el hilo de rastreo."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("Monitor de descargas de Steam detenido.")

    def _run_loop(self) -> None:
        while self._running:
            try:
                info = self.check_active_downloads()
                if self.callback:
                    try:
                        self.callback(info)
                    except Exception as cb_err:
                        logger.error(f"Error en callback de download tracker: {cb_err}")
            except Exception as e:
                logger.debug(f"Excepción en ciclo de download tracker: {e}")

            time.sleep(self.poll_interval)

    def check_active_downloads(self) -> DownloadInfo:
        """
        Escanea las bibliotecas para hallar descargas en curso.
        Examina manifiestos en steamapps/ y archivos en steamapps/downloading/.
        """
        current_time = time.time()
        if not self._cached_libraries or (current_time - self._last_lib_scan > 25.0):
            self._cached_libraries = steam_detector.get_library_folders(self.steam_path)
            self._last_lib_scan = current_time

        libraries = self._cached_libraries

        for lib in libraries:
            steamapps_dir = lib / "steamapps"
            downloading_dir = steamapps_dir / "downloading"

            # 1. Comprobar manifiestos de juegos en descarga activa
            for acf_file in steamapps_dir.glob("appmanifest_*.acf"):
                try:
                    with open(acf_file, "r", encoding="utf-8", errors="ignore") as f:
                        data = vdf.load(f)

                    app_state = data.get("AppState", {})
                    if not app_state:
                        continue

                    bytes_to_download = int(app_state.get("BytesToDownload", 0))
                    bytes_downloaded = int(app_state.get("BytesDownloaded", 0))
                    state_flags = int(app_state.get("StateFlags", 0))

                    # Si hay bytes pendientes o state_flags tiene bits de descarga (1026, 1030, etc.)
                    # Y BytesToDownload > 0 y BytesDownloaded < BytesToDownload
                    is_downloading = (
                        bytes_to_download > 0 and
                        bytes_downloaded < bytes_to_download and
                        (state_flags & 1024 != 0 or (downloading_dir / str(app_state.get("appid", ""))).exists())
                    )

                    if is_downloading:
                        appid = int(app_state.get("appid"))
                        game_name = app_state.get("name", f"App {appid}")

                        progress_pct = (bytes_downloaded / bytes_to_download) * 100.0

                        # Cálculo de velocidad de descarga
                        speed_mb_s = 0.0
                        if self._last_appid == appid and self._last_time > 0:
                            delta_time = current_time - self._last_time
                            delta_bytes = bytes_downloaded - self._last_bytes
                            if delta_time > 0 and delta_bytes >= 0:
                                speed_bps = delta_bytes / delta_time
                                speed_mb_s = speed_bps / (1024 * 1024)

                        self._last_appid = appid
                        self._last_bytes = bytes_downloaded
                        self._last_time = current_time

                        # Cálculo de ETA (tiempo estimado)
                        remaining_bytes = bytes_to_download - bytes_downloaded
                        eta_str = "--"
                        if speed_mb_s > 0.05:
                            remaining_sec = remaining_bytes / (speed_mb_s * 1024 * 1024)
                            if remaining_sec < 60:
                                eta_str = f"{int(remaining_sec)}s restantes"
                            elif remaining_sec < 3600:
                                eta_str = f"{int(remaining_sec // 60)}m restantes"
                            else:
                                eta_str = f"{remaining_sec / 3600:.1f}h restantes"

                        return DownloadInfo(
                            is_active=True,
                            appid=appid,
                            game_name=game_name,
                            progress_pct=progress_pct,
                            bytes_downloaded=bytes_downloaded,
                            bytes_total=bytes_to_download,
                            speed_mb_s=speed_mb_s,
                            eta_str=eta_str
                        )
                except Exception:
                    continue

        # Si no se encontró ninguna descarga activa, reiniciar contadores
        self._last_appid = None
        self._last_bytes = 0
        self._last_time = current_time
        return DownloadInfo(is_active=False)
