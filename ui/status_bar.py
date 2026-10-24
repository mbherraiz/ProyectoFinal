"""
Barra de estado inferior en Monochrome UI.
Permite cambiar el estado de presencia en Steam con un clic (Online, Away, Invisible, Offline),
abrir chat/amigos, y visualizar el consumo de RAM de Steam y el progreso de descargas.
"""

from typing import Any, Callable, Dict, Optional

import customtkinter as ctk
from config import (
    COLOR_BORDER,
    COLOR_BTN_PRIMARY,
    COLOR_BTN_PRIMARY_HOVER,
    COLOR_BTN_SECONDARY,
    COLOR_BTN_SECONDARY_HOVER,
    COLOR_CONTAINER,
    COLOR_STATUS_AWAY,
    COLOR_STATUS_INVISIBLE,
    COLOR_STATUS_OFFLINE,
    COLOR_STATUS_ONLINE,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)
from core import presence_manager
from logger import get_logger

logger = get_logger("StatusBar")


class StatusBar(ctk.CTkFrame):
    """
    Barra inferior integrada con selectores de presencia y telemetría de Steam.
    """

    def __init__(self, master: Any, **kwargs):
        super().__init__(
            master,
            fg_color=COLOR_CONTAINER,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=0,
            height=46,
            **kwargs
        )
        self.pack_propagate(False)

        self._active_presence = "invisible"
        self._build_ui()

    def _build_ui(self) -> None:
        """Construye la disposición de la barra de estado."""
        # ----------------- SECCIÓN IZQUIERDA: Presencia de Steam -----------------
        left_frame = ctk.CTkFrame(self, fg_color="transparent")
        left_frame.pack(side="left", padx=12, fill="y")

        lbl_presencia = ctk.CTkLabel(
            left_frame,
            text="Presencia:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXT_SECONDARY
        )
        lbl_presencia.pack(side="left", padx=(0, 8))

        # Botones rápidos de presencia monocromáticos
        self.btn_online = self._create_presence_btn(left_frame, "En línea", "online", COLOR_STATUS_ONLINE)
        self.btn_away = self._create_presence_btn(left_frame, "Ausente", "away", COLOR_STATUS_AWAY)
        self.btn_invisible = self._create_presence_btn(left_frame, "Invisible", "invisible", COLOR_STATUS_INVISIBLE)
        self.btn_offline = self._create_presence_btn(left_frame, "Desconectado", "offline", COLOR_STATUS_OFFLINE)

        # Accesos rápidos a Amigos y Chat
        sep_1 = ctk.CTkFrame(left_frame, width=1, height=18, fg_color=COLOR_BORDER)
        sep_1.pack(side="left", padx=8)

        btn_friends = ctk.CTkButton(
            left_frame,
            text="Amigos",
            font=ctk.CTkFont(size=10),
            fg_color=COLOR_BTN_SECONDARY,
            hover_color=COLOR_BTN_SECONDARY_HOVER,
            text_color=COLOR_TEXT_SECONDARY,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=4,
            height=24,
            width=58,
            command=presence_manager.open_friends_list
        )
        btn_friends.pack(side="left", padx=2)

        btn_chat = ctk.CTkButton(
            left_frame,
            text="Chat",
            font=ctk.CTkFont(size=10),
            fg_color=COLOR_BTN_SECONDARY,
            hover_color=COLOR_BTN_SECONDARY_HOVER,
            text_color=COLOR_TEXT_SECONDARY,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=4,
            height=24,
            width=48,
            command=presence_manager.open_chat_window
        )
        btn_chat.pack(side="left", padx=2)

        # ----------------- SECCIÓN CENTRAL: Descargas en Curso -----------------
        self.download_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.download_frame.pack(side="left", expand=True, fill="both", padx=16)

        self.lbl_download_title = ctk.CTkLabel(
            self.download_frame,
            text="",
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w"
        )
        self.lbl_download_title.pack(side="left", padx=(0, 8))

        self.progress_bar = ctk.CTkProgressBar(
            self.download_frame,
            width=140,
            height=8,
            fg_color="#181818",
            progress_color="#e0e0e0",
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=3
        )
        self.progress_bar.set(0)
        # Oculto por defecto hasta que haya descarga
        self.progress_bar.pack_forget()

        self.lbl_download_meta = ctk.CTkLabel(
            self.download_frame,
            text="",
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_MUTED
        )
        self.lbl_download_meta.pack(side="left", padx=8)

        # ----------------- SECCIÓN DERECHA: Telemetría de Steam -----------------
        right_frame = ctk.CTkFrame(self, fg_color="transparent")
        right_frame.pack(side="right", padx=12, fill="y")

        self.lbl_steam_ram = ctk.CTkLabel(
            right_frame,
            text="Steam: Comprobando...",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_MUTED
        )
        self.lbl_steam_ram.pack(side="right", padx=4)

    def _create_presence_btn(self, parent, text: str, key: str, dot_color: str) -> ctk.CTkButton:
        """Crea un botón estilizado para el selector de presencia."""
        btn = ctk.CTkButton(
            parent,
            text=f"● {text}",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=COLOR_BTN_SECONDARY,
            hover_color=COLOR_BTN_SECONDARY_HOVER,
            text_color=dot_color,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=4,
            height=24,
            width=75,
            command=lambda k=key: self._on_presence_selected(k)
        )
        btn.pack(side="left", padx=2)
        return btn

    def _on_presence_selected(self, key: str) -> None:
        """Envía la solicitud de cambio de presencia y actualiza el estado visual."""
        self._active_presence = key
        success = presence_manager.set_presence(key)
        if success:
            logger.info(f"Presencia cambiada a {key}")

    def update_download_status(self, info: Dict[str, Any]) -> None:
        """Actualiza la visualización de descargas con los datos de DownloadTracker."""
        if info.get("is_active"):
            name = info.get("game_name", "Descarga")
            pct = info.get("progress_pct", 0.0)
            speed = info.get("speed_str", "")
            eta = info.get("eta_str", "")

            short_name = name if len(name) <= 18 else f"{name[:16]}..."
            self.lbl_download_title.configure(text=f"Descargando {short_name}:")
            self.progress_bar.pack(side="left", padx=(0, 6))
            self.progress_bar.set(pct / 100.0)
            self.lbl_download_meta.configure(text=f"{pct:.1f}% ({speed}) {eta}")
        else:
            self.lbl_download_title.configure(text="")
            self.lbl_download_meta.configure(text="")
            self.progress_bar.pack_forget()

    def update_steam_telemetry(self, is_running: bool, ram_mb: float) -> None:
        """Actualiza el indicador de memoria y estado de steam.exe."""
        if is_running:
            status_text = f"Steam Ultraligero: {ram_mb:.1f} MB RAM"
            self.lbl_steam_ram.configure(text=status_text, text_color=COLOR_TEXT_PRIMARY)
        else:
            self.lbl_steam_ram.configure(text="Steam: No iniciado", text_color=COLOR_TEXT_MUTED)
