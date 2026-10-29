"""
Control de procesos del sistema mediante psutil, ejecución ultraligera de Steam,
reinicio transparente, lanzamiento de juegos y supervisión del estado de ejecución (HKCU).
"""

import os
import subprocess
import threading
import time
import winreg
from pathlib import Path
from typing import Callable, Optional

import psutil
from config import STEAM_ULTRALIGHT_FLAGS, STEAM_URI_RUN
from logger import get_logger

logger = get_logger("ProcessManager")


_steam_pids_cache: set = set()
_last_pid_scan_time: float = 0.0


def _refresh_steam_pids_if_needed(force: bool = False) -> set:
    global _steam_pids_cache, _last_pid_scan_time
    now = time.time()
    if force or not _steam_pids_cache or (now - _last_pid_scan_time > 10.0):
        steam_names = {"steam.exe", "steamwebhelper.exe"}
        found_pids = set()
        for proc in psutil.process_iter(["name", "pid"]):
            try:
                name = proc.info.get("name")
                if name and name.lower() in steam_names:
                    found_pids.add(proc.info.get("pid"))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        _steam_pids_cache = found_pids
        _last_pid_scan_time = now
    return _steam_pids_cache


def is_steam_running() -> bool:
    """Verifica si steam.exe se encuentra actualmente en ejecución."""
    pids = _refresh_steam_pids_if_needed()
    if not pids:
        # Reintentar forzado por si acaba de abrir
        pids = _refresh_steam_pids_if_needed(force=True)
    for pid in list(pids):
        try:
            p = psutil.Process(pid)
            if p.is_running() and p.name().lower() == "steam.exe":
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            _steam_pids_cache.discard(pid)
    return False


def get_steam_process() -> Optional[psutil.Process]:
    """Retorna la instancia psutil.Process del ejecutable principal de Steam si existe."""
    pids = _refresh_steam_pids_if_needed(force=True)
    for pid in pids:
        try:
            p = psutil.Process(pid)
            if p.is_running() and p.name().lower() == "steam.exe":
                return p
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def get_steam_memory_usage_mb() -> float:
    """Calcula el consumo total de memoria RAM (en MB) de todos los procesos asociados a Steam."""
    total_bytes = 0
    pids = list(_refresh_steam_pids_if_needed())
    for pid in pids:
        try:
            p = psutil.Process(pid)
            if p.is_running():
                total_bytes += p.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            _steam_pids_cache.discard(pid)
    return round(total_bytes / (1024 * 1024), 1)


def trim_steam_memory() -> int:
    """
    Fuerza a Windows (API psapi.EmptyWorkingSet) a purgar la memoria RAM no esencial
    de steam.exe y steamwebhelper.exe. Reduce drásticamente el consumo en el Administrador de Tareas.
    """
    import ctypes
    flags = 0x0100 | 0x0400  # PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION
    trimmed_count = 0

    for proc in psutil.process_iter(["name", "pid"]):
        try:
            name = proc.info.get("name")
            if name and name.lower() in ("steam.exe", "steamwebhelper.exe"):
                pid = proc.info.get("pid")
                if pid:
                    h_proc = ctypes.windll.kernel32.OpenProcess(flags, False, pid)
                    if h_proc:
                        ctypes.windll.psapi.EmptyWorkingSet(h_proc)
                        ctypes.windll.kernel32.CloseHandle(h_proc)
                        trimmed_count += 1
        except Exception:
            continue

    if trimmed_count > 0:
        logger.debug(f"Memoria purgada en {trimmed_count} procesos de Steam.")
    return trimmed_count


def kill_steam_cleanly(steam_exe_path: Optional[Path] = None, timeout_sec: float = 6.0) -> bool:
    """
    Termina todos los procesos de Steam (steam.exe, steamwebhelper.exe, etc.)
    de forma ordenada y exhaustiva para asegurar que no queden instancias retenidas en memoria.
    """
    logger.info("Iniciando cierre completo de procesos de Steam...")
    # Solo terminar steam.exe y steamwebhelper.exe (nunca steamservice que corre como servicio SYSTEM)
    steam_names = {"steam.exe", "steamwebhelper.exe"}

    # 1. Intentar primero cierre ordenado oficial mediante 'steam.exe -shutdown'
    if steam_exe_path and steam_exe_path.exists():
        try:
            subprocess.run([str(steam_exe_path), "-shutdown"], timeout=3.0, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.debug(f"Aviso al invocar steam.exe -shutdown: {e}")

    # 2. Recolectar procesos de usuario de Steam
    active_procs = []
    for proc in psutil.process_iter(["name"]):
        try:
            name = proc.info.get("name")
            if name and name.lower() in steam_names:
                active_procs.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if not active_procs:
        logger.info("No se detectaron procesos activos de Steam.")
        return True

    # 3. Solicitar terminate()
    for p in active_procs:
        try:
            p.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # 4. Esperar a que finalicen capturando AccessDenied
    alive = []
    for p in active_procs:
        try:
            p.wait(timeout=timeout_sec)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except psutil.TimeoutExpired:
            alive.append(p)

    # 5. Si quedan procesos rezagados, forzar kill()
    if alive:
        logger.warning(f"Quedan {len(alive)} procesos de Steam tras timeout; forzando kill...")
        for p in alive:
            try:
                p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            try:
                p.wait(timeout=2.0)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                pass

    # 6. Comprobación final
    time.sleep(0.5)
    remaining = is_steam_running()
    if remaining:
        logger.warning("Aún se detectan instancias de Steam activas.")
        return False

    logger.info("Todos los procesos de Steam fueron finalizados con éxito.")
    return True


def launch_steam_ultralight(steam_exe_path: Path, extra_flags: Optional[list] = None) -> bool:
    """
    Lanza Steam en segundo plano de forma 100% independiente (desacoplado del proceso Python).
    Utiliza el shell de Windows (os.startfile) para evitar que el Administrador de Tareas
    agrupe a Steam dentro de Python 3.13.
    """
    if not steam_exe_path.exists():
        logger.error(f"No se encontró el ejecutable de Steam en: {steam_exe_path}")
        return False

    flags = list(STEAM_ULTRALIGHT_FLAGS)
    if extra_flags:
        flags.extend(extra_flags)

    args_str = " ".join(flags)
    logger.info(f"Lanzando Steam independiente: {steam_exe_path} {args_str}")

    try:
        # 1. Intentar os.startfile con argumentos (desacopla el proceso a Explorer de Windows)
        if hasattr(os, "startfile"):
            try:
                os.startfile(str(steam_exe_path), arguments=args_str)
                return True
            except TypeError:
                # Versiones de Python donde startfile no acepta arguments
                pass

        # 2. Fallback desacoplado con CREATE_NEW_PROCESS_GROUP y DETACHED_PROCESS
        creation_flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(
            [str(steam_exe_path)] + flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
            close_fds=True
        )
        return True
    except Exception as e:
        logger.error(f"Fallo al ejecutar Steam ultraligero: {e}")
        return False


def restart_steam_ultralight(steam_exe_path: Path) -> bool:
    """
    Cierra Steam completamente si está en ejecución, espera a que libere archivos
    y lo reinicia en modo ultraligero con las banderas optimizadas.
    """
    logger.info("Reiniciando cliente de Steam en modo ultraligero...")
    if is_steam_running():
        kill_steam_cleanly(steam_exe_path=steam_exe_path, timeout_sec=5.0)
        # Esperar hasta que no haya ningún proceso
        start_wait = time.time()
        while is_steam_running() and time.time() - start_wait < 5.0:
            time.sleep(0.3)
        time.sleep(1.0)  # Pausa para asegurar liberación de sockets y archivos

    return launch_steam_ultralight(steam_exe_path)


def is_game_running(appid: int) -> bool:
    """
    Comprueba si un juego con el appid dado está en ejecución
    consultando el Registro de Windows: HKCU\\Software\\Valve\\Steam\\Apps\\<appid>\\Running.
    """
    reg_path = rf"Software\Valve\Steam\Apps\{appid}"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path) as key:
            val, _ = winreg.QueryValueEx(key, "Running")
            return val == 1
    except FileNotFoundError:
        return False
    except Exception as e:
        logger.debug(f"Error leyendo registro de ejecución para appid {appid}: {e}")
        return False


def launch_game(appid: int) -> bool:
    """
    Ejecuta un juego mediante la URI nativa steam://run/<appid>.
    """
    uri = STEAM_URI_RUN.format(appid=appid)
    logger.info(f"Lanzando juego AppID {appid} mediante URI: {uri}")
    try:
        if hasattr(os, "startfile"):
            os.startfile(uri)
        else:
            subprocess.Popen(["cmd.exe", "/c", "start", uri])
        return True
    except Exception as e:
        logger.error(f"Fallo al invocar URI para appid {appid}: {e}")
        return False


def watch_game_lifecycle(
    appid: int,
    on_started: Optional[Callable[[], None]] = None,
    on_exited: Optional[Callable[[], None]] = None,
    poll_interval: float = 1.5,
    max_wait_start_sec: float = 45.0
) -> threading.Thread:
    """
    Inicia un hilo secundario que vigila el ciclo de vida de un juego recién lanzado:
    1. Espera a que el juego cambie a Running == 1 (hasta max_wait_start_sec).
    2. Al arrancar, invoca on_started() (p. ej. minimizar a la bandeja).
    3. Vigila hasta que Running vuelva a 0.
    4. Al terminar, invoca on_exited() (restaurar ventana principal).
    """
    def _worker():
        logger.info(f"Monitor de ciclo de vida iniciado para AppID {appid}")
        started = False
        start_time = time.time()

        # Fase 1: Esperar a que el juego inicie
        while time.time() - start_time < max_wait_start_sec:
            if is_game_running(appid):
                started = True
                logger.info(f"AppID {appid} detectado en ejecución.")
                if on_started:
                    try:
                        on_started()
                    except Exception as e:
                        logger.error(f"Error en callback on_started: {e}")
                break
            time.sleep(poll_interval)

        if not started:
            logger.warning(f"AppID {appid} no inició dentro del tiempo límite ({max_wait_start_sec}s).")
            return

        # Fase 2: Vigilar mientras se ejecuta
        while True:
            time.sleep(poll_interval)
            if not is_game_running(appid):
                logger.info(f"AppID {appid} ha finalizado su ejecución.")
                if on_exited:
                    try:
                        on_exited()
                    except Exception as e:
                        logger.error(f"Error en callback on_exited: {e}")
                break

    thread = threading.Thread(target=_worker, name=f"WatchGame-{appid}", daemon=True)
    thread.start()
    return thread
