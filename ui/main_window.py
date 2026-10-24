"""
Ventana principal del Steam Light Launcher en Monochrome UI.
Coordina pestañas (Instalados, Biblioteca Completa), barra de estado de presencia,
monitor de descargas nativo, telemetría y minimización a la bandeja del sistema (System Tray vía pystray).
"""

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

import customtkinter as ctk
from PIL import Image, ImageDraw
import pystray
from config import (
    COLOR_BG_MAIN,
    COLOR_BORDER,
    COLOR_BTN_PRIMARY,
    COLOR_BTN_PRIMARY_HOVER,
    COLOR_BTN_SECONDARY,
    COLOR_BTN_SECONDARY_HOVER,
    COLOR_CONTAINER,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    STEAM_URI_INSTALL,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
    WINDOW_TITLE,
)
import database
from core import download_tracker, process_manager, steam_detector
from logger import get_logger, register_error_ui_callback
from ui.dispatcher import dispatch_to_main, init_dispatcher
from ui.error_dialog import show_error_modal
from ui.settings_dialog import SettingsDialog
from ui.status_bar import StatusBar
from ui.tabs.installed_tab import InstalledTab
from ui.tabs.library_tab import LibraryTab

logger = get_logger("MainWindow")


def create_tray_icon_image() -> Image.Image:
    """Genera un icono monocromático en memoria para la bandeja del sistema (pystray)."""
    size = (64, 64)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Fondo circular gris oscuro
    draw.ellipse([4, 4, 60, 60], fill="#1e1e1e", outline="#ffffff", width=3)
    # Símbolo central minimalista tipo Steam
    draw.ellipse([20, 20, 44, 44], fill="#ffffff")
    draw.ellipse([26, 26, 38, 38], fill="#1e1e1e")
    draw.ellipse([34, 14, 48, 28], fill="#ffffff")
    draw.ellipse([38, 18, 44, 24], fill="#1e1e1e")
    return img


class MainWindow(ctk.CTk):
    """
    Ventana principal del Launcher.
    """

    def __init__(self):
        super().__init__()

        # Configuración estética Monochrome UI de CustomTkinter
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title(WINDOW_TITLE)
        self.geometry(f"{DEFAULT_WIDTH}x{DEFAULT_HEIGHT}")
        self.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.configure(fg_color=COLOR_BG_MAIN)

        # Iniciar despachador seguro de tareas para Tkinter (compatibilidad Python 3.13)
        init_dispatcher(self)

        self.steam_path = steam_detector.get_steam_install_path()
        self.steam_exe = steam_detector.get_steam_executable(self.steam_path)

        # Estado del System Tray
        self._tray_icon: Optional[pystray.Icon] = None
        self._is_minimized_to_tray = False

        # Registrar callback global de UI para el sistema de logging
        register_error_ui_callback(self._on_global_error_dispatched)

        self._build_header()
        self._build_tabs()
        self._build_status_bar()

        # Iniciar monitor de descargas y telemetría de Steam
        self._init_download_tracker()
        self._start_telemetry_loop()

        # Manejador de cierre de ventana
        self.protocol("WM_DELETE_WINDOW", self._on_window_close_request)

    def _build_header(self) -> None:
        """Construye la cabecera superior con título y botones de acción."""
        header_frame = ctk.CTkFrame(
            self,
            fg_color=COLOR_CONTAINER,
            height=60,
            corner_radius=0,
            border_color=COLOR_BORDER,
            border_width=1
        )
        header_frame.pack(fill="x", side="top")
        header_frame.pack_propagate(False)

        # Logotipo y título
        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.pack(side="left", padx=20)

        lbl_logo = ctk.CTkLabel(
            title_box,
            text="[S]",
            font=ctk.CTkFont(family="Consolas", size=20, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        lbl_logo.pack(side="left", padx=(0, 8))

        lbl_title = ctk.CTkLabel(
            title_box,
            text="STEAM LIGHT LAUNCHER",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        lbl_title.pack(side="left")

        lbl_badge = ctk.CTkLabel(
            title_box,
            text="• ULTRA-LIGHT MODE",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        )
        lbl_badge.pack(side="left", padx=(10, 0))

        # Controles de la cabecera derecha
        ctrl_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        ctrl_box.pack(side="right", padx=20)

        # Botón para arrancar o reiniciar Steam ultraligero manualmente
        self.btn_steam_toggle = ctk.CTkButton(
            ctrl_box,
            text="Lanzar Steam Ligero",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=COLOR_BTN_PRIMARY,
            hover_color=COLOR_BTN_PRIMARY_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=6,
            height=30,
            command=self._launch_or_restart_steam
        )
        self.btn_steam_toggle.pack(side="left", padx=6)

        # Botón de Ajustes
        btn_settings = ctk.CTkButton(
            ctrl_box,
            text="Ajustes",
            font=ctk.CTkFont(size=11),
            fg_color=COLOR_BTN_SECONDARY,
            hover_color=COLOR_BTN_SECONDARY_HOVER,
            text_color=COLOR_TEXT_SECONDARY,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=6,
            height=30,
            width=75,
            command=self._open_settings_dialog
        )
        btn_settings.pack(side="left", padx=6)

    def _build_tabs(self) -> None:
        """Construye las pestañas centrales de navegación."""
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=COLOR_BG_MAIN,
            segmented_button_fg_color=COLOR_CONTAINER,
            segmented_button_selected_color=COLOR_BTN_PRIMARY,
            segmented_button_selected_hover_color=COLOR_BTN_PRIMARY_HOVER,
            segmented_button_unselected_color=COLOR_CONTAINER,
            segmented_button_unselected_hover_color=COLOR_BTN_SECONDARY_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=8,
            border_width=1,
            border_color=COLOR_BORDER
        )
        self.tabview.pack(fill="both", expand=True, padx=16, pady=(8, 4))

        # Pestaña 1: Instalados
        tab_installed = self.tabview.add("Juegos Instalados")
        self.installed_tab = InstalledTab(
            tab_installed,
            on_launch_game=self.launch_game_action
        )
        self.installed_tab.pack(fill="both", expand=True)

        # Pestaña 2: Biblioteca Completa
        tab_library = self.tabview.add("Biblioteca Completa")
        self.library_tab = LibraryTab(
            tab_library,
            on_launch_game=self.launch_game_action,
            on_install_game=self.install_game_action,
            on_notify_fallback=self._notify_offline_fallback
        )
        self.library_tab.pack(fill="both", expand=True)

    def _build_status_bar(self) -> None:
        """Construye la barra inferior."""
        self.status_bar = StatusBar(self)
        self.status_bar.pack(fill="x", side="bottom")

    def _init_download_tracker(self) -> None:
        """Inicializa el monitor de descargas de Steam en segundo plano."""
        self.tracker = download_tracker.DownloadTracker(
            steam_path=self.steam_path,
            callback=lambda info: dispatch_to_main(lambda: self.status_bar.update_download_status(info.to_dict()))
        )
        self.tracker.start()

    def _start_telemetry_loop(self) -> None:
        """Supervisa el consumo de memoria y purga RAM no esencial de Steam cada 5 segundos."""
        def _telemetry_worker():
            cycle = 0
            while not getattr(self, "_is_closing", False):
                try:
                    running = process_manager.is_steam_running()
                    if running:
                        cycle += 1
                        # Purgar memoria de Chromium en segundo plano
                        if cycle % 2 == 0:
                            process_manager.trim_steam_memory()

                    ram_mb = process_manager.get_steam_memory_usage_mb() if running else 0.0
                    dispatch_to_main(lambda r=running, m=ram_mb: self._update_steam_ui_state(r, m))
                except Exception as e:
                    logger.debug(f"Error en ciclo de telemetría: {e}")

                time.sleep(2.5)

        threading.Thread(target=_telemetry_worker, name="TelemetryWorker", daemon=True).start()

    def _update_steam_ui_state(self, is_running: bool, ram_mb: float) -> None:
        """Actualiza el botón superior y el texto de la barra inferior."""
        self.status_bar.update_steam_telemetry(is_running, ram_mb)
        if is_running:
            self.btn_steam_toggle.configure(text="Reiniciar Steam Ligero")
        else:
            self.btn_steam_toggle.configure(text="Lanzar Steam Ligero")

    def _launch_or_restart_steam(self) -> None:
        """Lanza o reinicia Steam en modo ultraligero en un hilo separado."""
        if not self.steam_exe or not self.steam_exe.exists():
            show_error_modal(self, "Steam no encontrado", "No se detectó el ejecutable steam.exe en tu sistema.")
            return

        def _worker():
            if process_manager.is_steam_running():
                process_manager.restart_steam_ultralight(self.steam_exe)
            else:
                process_manager.launch_steam_ultralight(self.steam_exe)

        threading.Thread(target=_worker, name="LaunchSteamWorker", daemon=True).start()

    def launch_game_action(self, appid: int) -> None:
        """
        Lanza un juego mediante steam://run/<appid> y activa la minimización al System Tray si está habilitada.
        """
        logger.info(f"Acción de lanzamiento solicitada para AppID {appid}")

        # Si Steam no está corriendo y el modo ultraligero está activo, asegurar que Steam inicie primero
        if not process_manager.is_steam_running() and self.steam_exe:
            process_manager.launch_steam_ultralight(self.steam_exe)
            time.sleep(1.0)

        success = process_manager.launch_game(appid)
        if not success:
            show_error_modal(self, "Error al lanzar juego", f"No se pudo ejecutar el juego con AppID {appid}.")
            return

        # Comprobar si está activada la opción de minimizar al System Tray
        minimize_pref = database.get_setting("minimize_to_tray", "1") == "1"
        if minimize_pref:
            # Observar el ciclo de vida del juego (cuando arranca, minimiza; cuando termina, restaura)
            process_manager.watch_game_lifecycle(
                appid=appid,
                on_started=lambda: dispatch_to_main(self.minimize_to_tray),
                on_exited=lambda: dispatch_to_main(self.restore_from_tray)
            )

    def install_game_action(self, appid: int) -> None:
        """
        Inicia la instalación de un juego mediante steam://install/<appid>.
        """
        logger.info(f"Acción de instalación solicitada para AppID {appid}")
        uri = STEAM_URI_INSTALL.format(appid=appid)
        try:
            if hasattr(os, "startfile"):
                os.startfile(uri)
            else:
                subprocess.Popen(["cmd.exe", "/c", "start", uri])
        except Exception as e:
            logger.error(f"Fallo al invocar instalación para AppID {appid}: {e}")
            show_error_modal(self, "Error de instalación", f"No se pudo invocar la instalación de Steam: {e}")

    # ---------------------------------------------------------------------------
    # GESTIÓN DEL SYSTEM TRAY (Bandeja del sistema vía pystray)
    # ---------------------------------------------------------------------------
    def minimize_to_tray(self) -> None:
        """Oculta la ventana principal y crea el icono en la bandeja del sistema."""
        if self._is_minimized_to_tray:
            return

        logger.info("Minimizando launcher a la bandeja del sistema (System Tray)...")
        self.withdraw()
        self._is_minimized_to_tray = True

        def _setup_tray():
            menu = pystray.Menu(
                pystray.MenuItem("Mostrar Launcher", lambda icon, item: dispatch_to_main(self.restore_from_tray)),
                pystray.MenuItem("Reiniciar Steam Ligero", lambda icon, item: dispatch_to_main(self._launch_or_restart_steam)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Salir", lambda icon, item: dispatch_to_main(self.quit_application))
            )
            icon_img = create_tray_icon_image()
            self._tray_icon = pystray.Icon("SteamLightLauncher", icon_img, "Steam Light Launcher", menu)
            self._tray_icon.run()

        threading.Thread(target=_setup_tray, name="SystemTrayThread", daemon=True).start()

    def restore_from_tray(self) -> None:
        """Restaura la ventana desde la bandeja del sistema."""
        logger.info("Restaurando ventana desde la bandeja del sistema...")
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
            self._tray_icon = None

        self._is_minimized_to_tray = False
        self.deiconify()
        self.lift()
        self.focus_force()

    def _open_settings_dialog(self) -> None:
        """Abre el panel de ajustes."""
        SettingsDialog(
            parent=self,
            on_saved_callback=self._on_settings_saved
        )

    def _on_settings_saved(self) -> None:
        """Refresca las vistas tras modificar ajustes."""
        self.library_tab.load_initial_data()
        self.installed_tab.load_games_async()

    def _notify_offline_fallback(self, message: str) -> None:
        """Notifica al usuario sobre la activación del modo sin conexión."""
        show_error_modal(self, "Aviso de Conexión", message)

    def _on_global_error_dispatched(self, title: str, message: str) -> None:
        """Manejador para errores globales registrados desde logger.py."""
        dispatch_to_main(lambda: show_error_modal(self, title, message))

    def _on_window_close_request(self) -> None:
        """Maneja el evento de cerrar la ventana."""
        self.quit_application()

    def quit_application(self) -> None:
        """Cierre ordenado de todos los hilos, iconos del tray y la aplicación."""
        logger.info("Cerrando Steam Light Launcher...")
        self._is_closing = True
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass

        if hasattr(self, "tracker"):
            self.tracker.stop()

        try:
            self.destroy()
        except Exception:
            pass
