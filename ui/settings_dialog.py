"""
Panel modal de configuración en Monochrome UI.
Permite configurar SteamID64, SteamIDs de familiares, Steam Web API Key y opciones de rendimiento.
Incluye enlaces directos a Steam/SteamID para facilitar la obtención de credenciales.
"""

from pathlib import Path
from typing import Callable, Optional
import webbrowser

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
from core import steam_detector
from logger import get_logger

logger = get_logger("SettingsDialog")

URL_GET_STEAMID64 = "https://steamid.io/"
URL_GET_APIKEY = "https://steamcommunity.com/dev/apikey"


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
        self.geometry("620x620")
        self.minsize(580, 580)
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
        w = 620
        h = 620

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

    def _open_url(self, url: str) -> None:
        """Abre un enlace en el navegador predeterminado."""
        try:
            webbrowser.open(url)
        except Exception as e:
            logger.error(f"Error abriendo enlace '{url}': {e}")

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

        # ----------------- 1. BOTONES DE ACCIÓN INFERIORES (Empaquetados primero con side='bottom') -----------------
        # Al empacarlos primero con side='bottom', Tkinter reserva siempre su espacio visible y nunca los recorta.
        btn_frame = ctk.CTkFrame(container, fg_color="transparent", height=42)
        btn_frame.pack(fill="x", side="bottom", padx=20, pady=(10, 16))
        btn_frame.pack_propagate(False)

        btn_save = ctk.CTkButton(
            btn_frame,
            text="Guardar y Aplicar",
            fg_color=COLOR_BTN_PRIMARY,
            hover_color=COLOR_BTN_PRIMARY_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_color=COLOR_BORDER_FOCUS,
            border_width=1,
            corner_radius=6,
            height=36,
            width=140,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._save_settings
        )
        btn_save.pack(side="right")

        btn_cancel = ctk.CTkButton(
            btn_frame,
            text="Cancelar",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_BTN_SECONDARY,
            hover_color=COLOR_BTN_SECONDARY_HOVER,
            text_color=COLOR_TEXT_MUTED,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=6,
            height=36,
            width=95,
            command=self.destroy
        )
        btn_cancel.pack(side="right", padx=(0, 10))

        # ----------------- 2. CONTENIDO SUPERIOR -----------------
        content_frame = ctk.CTkFrame(container, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=20, pady=(16, 0), side="top")

        # Encabezado
        title_label = ctk.CTkLabel(
            content_frame,
            text="Configuración y Rendimiento",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        title_label.pack(fill="x", pady=(0, 2))

        subtitle = ctk.CTkLabel(
            content_frame,
            text="Configura tus credenciales de Steam, cuentas familiares y opciones de ejecución.",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        )
        subtitle.pack(fill="x", pady=(0, 10))

        sep1 = ctk.CTkFrame(content_frame, height=1, fg_color=COLOR_BORDER)
        sep1.pack(fill="x", pady=(0, 12))

        # SECCIÓN 1: Credenciales Web API y Familia
        lbl_sec1 = ctk.CTkLabel(
            content_frame,
            text="Cuentas de Steam (Propia y Familia)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        lbl_sec1.pack(fill="x", pady=(0, 6))

        # SteamID64 Principal + Botón con enlace
        row_steamid = ctk.CTkFrame(content_frame, fg_color="transparent")
        row_steamid.pack(fill="x", pady=(2, 2))

        lbl_steamid = ctk.CTkLabel(
            row_steamid,
            text="Tu SteamID64 Principal:",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w"
        )
        lbl_steamid.pack(side="left")

        btn_link_steamid = ctk.CTkButton(
            row_steamid,
            text="¿Dónde sacarlo? ↗",
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            hover_color=COLOR_CONTAINER,
            text_color="#90b8f8",
            height=20,
            width=110,
            command=lambda: self._open_url(URL_GET_STEAMID64)
        )
        btn_link_steamid.pack(side="right")

        self.entry_steamid = ctk.CTkEntry(
            content_frame,
            placeholder_text="Ej: 76561198000000000",
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_INPUT_BG,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            height=32
        )
        self.entry_steamid.pack(fill="x", pady=(0, 8))

        # SteamIDs Familiares compartidos
        lbl_family = ctk.CTkLabel(
            content_frame,
            text="SteamIDs de Familiares (separados por comas):",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w"
        )
        lbl_family.pack(fill="x", pady=(0, 2))

        self.entry_family = ctk.CTkEntry(
            content_frame,
            placeholder_text="Ej: 76561198353854122, 76561198111222333",
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_INPUT_BG,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            height=32
        )
        self.entry_family.pack(fill="x", pady=(0, 8))

        # Steam Web API Key + Botón con enlace oficial de Steam
        row_apikey = ctk.CTkFrame(content_frame, fg_color="transparent")
        row_apikey.pack(fill="x", pady=(0, 2))

        lbl_apikey = ctk.CTkLabel(
            row_apikey,
            text="Steam Web API Key:",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w"
        )
        lbl_apikey.pack(side="left")

        btn_link_apikey = ctk.CTkButton(
            row_apikey,
            text="Obtener en Steam ↗",
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            hover_color=COLOR_CONTAINER,
            text_color="#90b8f8",
            height=20,
            width=120,
            command=lambda: self._open_url(URL_GET_APIKEY)
        )
        btn_link_apikey.pack(side="right")

        self.entry_apikey = ctk.CTkEntry(
            content_frame,
            placeholder_text="Clave de 32 caracteres hexadecimales",
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_INPUT_BG,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            show="•",
            height=32
        )
        self.entry_apikey.pack(fill="x", pady=(0, 12))

        sep2 = ctk.CTkFrame(content_frame, height=1, fg_color=COLOR_BORDER)
        sep2.pack(fill="x", pady=(0, 12))

        # SECCIÓN 2: Opciones de Rendimiento
        lbl_sec2 = ctk.CTkLabel(
            content_frame,
            text="Opciones de Rendimiento",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        lbl_sec2.pack(fill="x", pady=(0, 8))

        # Switch 1: Modo Ultraligero / Reducido
        self.switch_light = ctk.CTkSwitch(
            content_frame,
            text="Lanzar Steam en Modo Compacto (sin tienda pesada en RAM)",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_SECONDARY,
            progress_color="#444444",
            button_color="#ffffff",
            button_hover_color="#d0d0d0"
        )
        self.switch_light.pack(fill="x", pady=4)

        # Switch 2: Minimizar al Tray
        self.switch_tray = ctk.CTkSwitch(
            content_frame,
            text="Minimizar el launcher a la bandeja (System Tray) al iniciar un juego",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_SECONDARY,
            progress_color="#444444",
            button_color="#ffffff",
            button_hover_color="#d0d0d0"
        )
        self.switch_tray.pack(fill="x", pady=4)

        # Ruta de instalación detectada
        detected_path_str = str(self.steam_path) if self.steam_path else "No detectada"
        lbl_path = ctk.CTkLabel(
            content_frame,
            text=f"Ruta Steam: {detected_path_str}",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        )
        lbl_path.pack(fill="x", pady=(10, 0))

    def _load_current_settings(self) -> None:
        """Carga los valores guardados en SQLite en los controles."""
        steamid = database.get_setting("steamid64", "")
        family_ids = database.get_setting("family_steamids", "")
        apikey = database.get_setting("api_key", "")
        light_mode = database.get_setting("ultra_light_mode", "1") == "1"
        min_tray = database.get_setting("minimize_to_tray", "1") == "1"

        self.entry_steamid.insert(0, steamid or "")
        self.entry_family.insert(0, family_ids or "")
        self.entry_apikey.insert(0, apikey or "")

        if light_mode:
            self.switch_light.select()
        else:
            self.switch_light.deselect()

        if min_tray:
            self.switch_tray.select()
        else:
            self.switch_tray.deselect()

    def _save_settings(self) -> None:
        """Guarda los ajustes en la base de datos."""
        steamid = self.entry_steamid.get().strip()
        family_ids = self.entry_family.get().strip()
        apikey = self.entry_apikey.get().strip()
        light_mode = "1" if self.switch_light.get() else "0"
        minimize_tray = "1" if self.switch_tray.get() else "0"

        database.set_setting("steamid64", steamid)
        database.set_setting("family_steamids", family_ids)
        database.set_setting("api_key", apikey)
        database.set_setting("ultra_light_mode", light_mode)
        database.set_setting("minimize_to_tray", minimize_tray)

        logger.info("Ajustes guardados con éxito.")

        if self.on_saved_callback:
            try:
                self.on_saved_callback()
            except Exception as e:
                logger.error(f"Error en callback on_saved: {e}")

        self.destroy()
