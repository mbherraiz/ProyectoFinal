"""
Punto de entrada principal (Entry Point) para Steam Light Launcher.
Inicializa el sistema de trazabilidad de errores, la base de datos local SQLite,
los manejadores globales de excepciones y arranca el loop de CustomTkinter.
"""

import os
import sys
from config import LOG_FILE
import database
from logger import (
    get_logger,
    install_global_exception_hooks,
    notify_error,
    setup_logging,
)
from ui.main_window import MainWindow


def _hide_console_window() -> None:
    """Oculta la ventana de consola de comandos en Windows si se inició mediante python.exe."""
    if sys.platform == "win32":
        try:
            import ctypes
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                # 0 = SW_HIDE
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:
            pass


def main() -> None:
    _hide_console_window()

    # 1. Configuración del sistema de logging centralizado (app_crash.log)
    setup_logging()
    logger = get_logger("Main")
    logger.info("Iniciando Steam Light Launcher...")

    # 2. Instalación de capturadores globales de excepciones no controladas
    install_global_exception_hooks()

    # 3. Inicialización de la base de datos SQLite local
    try:
        database.init_db()
    except Exception as e:
        logger.critical(f"Error fatal inicializando la base de datos SQLite: {e}")
        notify_error("Fallo de Base de Datos", f"No se pudo inicializar la base de datos local:\n{e}", exc=e)
        sys.exit(1)

    # 4. Instanciación de la interfaz gráfica y ejecución del loop principal
    try:
        app = MainWindow()
        app.mainloop()
    except Exception as e:
        logger.critical(f"Excepción fatal durante la ejecución de la ventana principal: {e}")
        notify_error("Error Fatal de Aplicación", f"Ocurrió un fallo no recuperable:\n{e}", exc=e)
        sys.exit(1)


if __name__ == "__main__":
    main()
