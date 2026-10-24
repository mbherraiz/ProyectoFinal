"""
Módulo centralizado de logging, trazabilidad de errores y captura global de excepciones.
Redirige fallos críticos a 'app_crash.log' y facilita su apertura en el editor del sistema.
"""

import logging
import os
import subprocess
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from config import LOG_FILE

# Logger principal de la aplicación
_logger: Optional[logging.Logger] = None
# Callback para desplegar la ventana emergente de error en la UI (Tkinter)
_error_ui_callback: Optional[Callable[[str, str], None]] = None


def setup_logging() -> logging.Logger:
    """
    Inicializa el sistema de logging con formato detallado y rotación/salida
    a 'app_crash.log' y a la consola estándar.
    """
    global _logger
    if _logger is not None:
        return _logger

    _logger = logging.getLogger("SteamLightLauncher")
    _logger.setLevel(logging.DEBUG)

    # Formato de los logs con fecha, nivel, hilo y mensaje
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(threadName)s] [%(name)s.%(funcName)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Manejador de archivo de fallos (app_crash.log)
    try:
        file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        _logger.addHandler(file_handler)
    except Exception as e:
        print(f"Error al inicializar FileHandler para {LOG_FILE}: {e}", file=sys.stderr)

    # Manejador de consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    _logger.addHandler(console_handler)

    _logger.info("=== Sesión de Steam Light Launcher iniciada ===")
    return _logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Retorna una instancia nombrada de logger."""
    if _logger is None:
        setup_logging()
    if name:
        return logging.getLogger(f"SteamLightLauncher.{name}")
    return _logger or logging.getLogger("SteamLightLauncher")


def register_error_ui_callback(callback: Callable[[str, str], None]) -> None:
    """
    Registra la función de la UI encargada de mostrar el modal Monochrome
    ante excepciones no controladas.
    Firma esperada: callback(titulo: str, mensaje_error: str)
    """
    global _error_ui_callback
    _error_ui_callback = callback


def notify_error(title: str, message: str, exc: Optional[BaseException] = None) -> None:
    """
    Registra el error en app_crash.log y solicita a la UI el despliegue del modal de fallo.
    """
    log = get_logger("ErrorHandler")
    if exc:
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        full_msg = f"{message}\nDetalles técnicos:\n{tb}"
        log.error(full_msg)
    else:
        full_msg = message
        log.error(message)

    # Invocar modal de UI si está disponible
    if _error_ui_callback:
        try:
            _error_ui_callback(title, message)
        except Exception as ui_err:
            log.error(f"Error al desplegar modal de error en la UI: {ui_err}")


def open_log_file() -> None:
    """
    Abre inmediatamente el archivo app_crash.log en el editor de texto
    predeterminado del sistema operativo (Notepad, VS Code, etc.).
    """
    log = get_logger("LogOpener")
    log_path = Path(LOG_FILE).resolve()

    if not log_path.exists():
        try:
            log_path.touch()
        except Exception as e:
            log.error(f"No se pudo crear el archivo de log vacío: {e}")

    try:
        # En Windows os.startfile lanza la aplicación asociada por defecto (.log -> Bloc de notas)
        if hasattr(os, "startfile"):
            os.startfile(str(log_path))
        else:
            subprocess.Popen(["notepad.exe", str(log_path)])
    except Exception as e:
        log.warning(f"os.startfile falló ({e}), intentando notepad.exe vía subprocess...")
        try:
            subprocess.Popen(["notepad.exe", str(log_path)])
        except Exception as sub_err:
            log.error(f"Fallo crítico al abrir el archivo de log: {sub_err}")


def install_global_exception_hooks() -> None:
    """
    Instala manejadores globales para capturar excepciones no atrapadas
    en el hilo principal (sys.excepthook) y en hilos secundarios (threading.excepthook).
    """
    def handle_sys_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        log = get_logger("GlobalExcepthook")
        log.critical(f"Excepción no controlada en el hilo principal:\n{tb_text}")
        notify_error(
            title="Excepción No Controlada",
            message=f"Se ha producido un error inesperado en la aplicación:\n\n{exc_type.__name__}: {exc_value}",
            exc=exc_value
        )

    def handle_thread_exception(args: threading.ExceptHookArgs):
        if issubclass(args.exc_type, KeyboardInterrupt):
            return

        tb_text = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        log = get_logger("ThreadExcepthook")
        log.critical(f"Excepción no controlada en hilo '{args.thread.name}':\n{tb_text}")
        notify_error(
            title="Error en Tarea Asíncrona",
            message=f"Ocurrió un error en un proceso en segundo plano ({args.thread.name}):\n\n{args.exc_type.__name__}: {args.exc_value}",
            exc=args.exc_value
        )

    sys.excepthook = handle_sys_exception
    threading.excepthook = handle_thread_exception
