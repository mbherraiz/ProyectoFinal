"""
Panel modal de configuración en Monochrome UI.
Permite configurar SteamID64, SteamIDs de familiares, Steam Web API Key y opciones de rendimiento.
"""

from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk
from config import (
    COLOR_BG_MAIN,
    COLOR_BORDER,
    COLOR_BORDER_FOCUS,
    COLOR_BTN_PRIMARY,
    COLOR_BTN_PRIMARY_HOVER,
    COLOR_BTN_SECONDARY,
    COLOR_BTN_SECONDARY_HOVER,
    COLOR_CONTAINER,
    COLOR_INPUT_BG,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)
import database
from core import overlay_manager, steam_detector
from logger import get_logger

logger = get_logger("SettingsDialog")


class SettingsDialog(ctk.CTkToplevel):
    """
    Modal de ajustes del sistema y rendimiento con estética monocromática minimalista.
    """

    def __init__(
        self,
        parent: Optional[ctk.CTk] = None,
        on_saved_callback: Optional[Callable[[], None]] = None
    ):
        super().__init__(parent)

        self.title("Ajustes del Launcher")
        self.geometry("580x640")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG_MAIN)

        self.transient(parent)
        self.lift()
        self.attributes("-topmost", True)

        self.on_saved_callback = on_saved_callback
        self.steam_path = steam_detector.get_steam_install_path()

        self._center_window(parent)
        self._build_ui()
        self._load_current_settings()

        try:
            self.grab_set()
        except Exception:
            pass

    def _center_window(self, parent: Optional[ctk.CTk]) -> None:
        """Centra el modal sobre la ventana principal."""
        self.update_idletasks()
        w = 580
        h = 640

        if parent and parent.winfo_exists():
            px = parent.winfo_x()
            py = parent.winfo_y()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
        else:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            x = (sw - w) // 2
            y = (sh - h) // 2

        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    def _build_ui(self) -> None:
        """Construye los controles del modal."""
        container = ctk.CTkFrame(
            self,
            fg_color=COLOR_CONTAINER,
            corner_radius=8,
            border_width=1,
            border_color=COLOR_BORDER
        )
        container.pack(fill="both", expand=True, padx=16, pady=16)

        # Encabezado
        title_label = ctk.CTkLabel(
            container,
            text="Configuración y Rendimiento",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        title_label.pack(fill="x", padx=18, pady=(14, 2))

        subtitle = ctk.CTkLabel(
            container,
            text="Configura tus credenciales, cuentas de Familia compartida y opciones de juego.",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        )
        subtitle.pack(fill="x", padx=18, pady=(0, 10))

        sep1 = ctk.CTkFrame(container, height=1, fg_color=COLOR_BORDER)
        sep1.pack(fill="x", padx=18, pady=(0, 10))

        # ----------------- SECCIÓN 1: Credenciales Web API y Familia -----------------
        lbl_sec1 = ctk.CTkLabel(
            container,
            text="Cuentas de Steam (Propia y Familia)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        lbl_sec1.pack(fill="x", padx=18, pady=(0, 4))

        # SteamID64 Principal
        lbl_steamid = ctk.CTkLabel(container, text="Tu SteamID64 Principal:", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_SECONDARY, anchor="w")
        lbl_steamid.pack(fill="x", padx=18, pady=(2, 1))
        self.entry_steamid = ctk.CTkEntry(
            container,
            placeholder_text="Ej: 76561198000000000",
            fg_color=COLOR_INPUT_BG,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            height=28
        )
        self.entry_steamid.pack(fill="x", padx=18, pady=(0, 6))

        # SteamIDs Familiares compartidos
        lbl_family = ctk.CTkLabel(container, text="SteamIDs de Familiares (separados por comas):", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_SECONDARY, anchor="w")
        lbl_family.pack(fill="x", padx=18, pady=(0, 1))
        self.entry_family = ctk.CTkEntry(
            container,
            placeholder_text="Ej: 76561198353854122, 76561198111222333",
            fg_color=COLOR_INPUT_BG,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            height=28
        )
        self.entry_family.pack(fill="x", padx=18, pady=(0, 6))

        # Steam Web API Key
        lbl_apikey = ctk.CTkLabel(container, text="Steam Web API Key:", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_SECONDARY, anchor="w")
        lbl_apikey.pack(fill="x", padx=18, pady=(0, 1))
        self.entry_apikey = ctk.CTkEntry(
            container,
            placeholder_text="Clave de 32 caracteres hexadecimales",
            fg_color=COLOR_INPUT_BG,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            show="•",
            height=28
        )
        self.entry_apikey.pack(fill="x", padx=18, pady=(0, 10))

        sep2 = ctk.CTkFrame(container, height=1, fg_color=COLOR_BORDER)
        sep2.pack(fill="x", padx=18, pady=(0, 10))

        # ----------------- SECCIÓN 2: Opciones de Rendimiento y Overlay -----------------
        lbl_sec2 = ctk.CTkLabel(
            container,
            text="Opciones de Optimización y Experiencia en Juegos",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        lbl_sec2.pack(fill="x", padx=18, pady=(0, 8))

        # Switch 1: Modo Ultraligero / Reducido
        self.switch_light = ctk.CTkSwitch(
            container,
            text="Lanzar Steam en Modo Compacto (sin tienda pesada en RAM)",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_SECONDARY,
            progress_color="#444444",
            button_color="#ffffff",
            button_hover_color="#d0d0d0"
        )
        self.switch_light.pack(fill="x", padx=18, pady=3)

        # Switch 2: Habilitar Steam Overlay (Shift+Tab)
        self.switch_overlay = ctk.CTkSwitch(
            container,
            text="Habilitar Steam Overlay en juegos (Shift+Tab, capturas y chat)",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_SECONDARY,
            progress_color="#444444",
            button_color="#ffffff",
            button_hover_color="#d0d0d0"
        )
        self.switch_overlay.pack(fill="x", padx=18, pady=3)

        # Switch 3: Minimizar al Tray
        self.switch_tray = ctk.CTkSwitch(
            container,
            text="Minimizar el launcher a la bandeja (System Tray) al iniciar un juego",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_SECONDARY,
            progress_color="#444444",
            button_color="#ffffff",
            button_hover_color="#d0d0d0"
        )
        self.switch_tray.pack(fill="x", padx=18, pady=3)

        # Ruta de instalación detectada
        detected_path_str = str(self.steam_path) if self.steam_path else "No detectada"
        lbl_path = ctk.CTkLabel(
            container,
            text=f"Ruta Steam: {detected_path_str}",
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        )
        lbl_path.pack(fill="x", padx=18, pady=(8, 0))

        # ----------------- SECCIÓN 3: Botones de Acción -----------------
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", padx=18, pady=(12, 10), side="bottom")

        btn_cancel = ctk.CTkButton(
            btn_frame,
            text="Cancelar",
            fg_color=COLOR_BTN_SECONDARY,
            hover_color=COLOR_BTN_SECONDARY_HOVER,
            text_color=COLOR_TEXT_MUTED,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=6,
            height=32,
            width=90,
            command=self.destroy
        )
        btn_cancel.pack(side="right", padx=(8, 0))

        btn_save = ctk.CTkButton(
            btn_frame,
            text="Guardar y Aplicar",
            fg_color=COLOR_BTN_PRIMARY,
            hover_color=COLOR_BTN_PRIMARY_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=6,
            height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._save_settings
        )
        btn_save.pack(side="right")

    def _load_current_settings(self) -> None:
        """Carga los valores guardados en SQLite en los controles."""
        steamid = database.get_setting("steamid64", "")
        family_ids = database.get_setting("family_steamids", "")
        apikey = database.get_setting("api_key", "")
        light_mode = database.get_setting("ultra_light_mode", "1") == "1"
        enable_overlay = database.get_setting("enable_overlay", "1") == "1"
        min_tray = database.get_setting("minimize_to_tray", "1") == "1"

        self.entry_steamid.insert(0, steamid or "")
        self.entry_family.insert(0, family_ids or "")
        self.entry_apikey.insert(0, apikey or "")

        if light_mode:
            self.switch_light.select()
        else:
            self.switch_light.deselect()

        # El overlay está activado por defecto
        if enable_overlay:
            self.switch_overlay.select()
        else:
            self.switch_overlay.deselect()

        if min_tray:
            self.switch_tray.select()
        else:
            self.switch_tray.deselect()

    def _save_settings(self) -> None:
        """Guarda los ajustes en la base de datos y aplica cambios en config.vdf si corresponde."""
        steamid = self.entry_steamid.get().strip()
        family_ids = self.entry_family.get().strip()
        apikey = self.entry_apikey.get().strip()
        light_mode = "1" if self.switch_light.get() else "0"
        enable_overlay = "1" if self.switch_overlay.get() else "0"
        minimize_tray = "1" if self.switch_tray.get() else "0"

        database.set_setting("steamid64", steamid)
        database.set_setting("family_steamids", family_ids)
        database.set_setting("api_key", apikey)
        database.set_setting("ultra_light_mode", light_mode)
        database.set_setting("enable_overlay", enable_overlay)
        database.set_setting("disable_overlay", "0" if enable_overlay == "1" else "1")
        database.set_setting("minimize_to_tray", minimize_tray)

        # Aplicar el estado de Overlay en config.vdf (DisableOverlay = 0 si está habilitado)
        if self.steam_path:
            logger.info(f"Aplicando estado de Steam Overlay: {'Habilitado' if enable_overlay == '1' else 'Deshabilitado'}...")
            try:
                overlay_manager.set_overlay_enabled(
                    self.steam_path,
                    enabled=(enable_overlay == "1"),
                    restart_steam_if_running=True
                )
            except Exception as e:
                logger.error(f"Error actualizando config.vdf desde Ajustes: {e}")

        logger.info("Ajustes guardados con éxito.")

        if self.on_saved_callback:
            try:
                self.on_saved_callback()
            except Exception as e:
                logger.error(f"Error en callback on_saved: {e}")

        self.destroy()
