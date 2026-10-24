"""
Ventana emergente modal de error crítico en Monochrome UI.
Presenta el detalle del fallo y el botón de acción directa 'Abrir Registro de Logs'.
"""

import tkinter as tk
from typing import Optional

import customtkinter as ctk
from config import (
    COLOR_BG_MAIN,
    COLOR_BORDER,
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
from logger import get_logger, open_log_file

logger = get_logger("ErrorDialog")


class ErrorDialog(ctk.CTkToplevel):
    """
    Modal de error con estética monocromática minimalista.
    Permite visualizar el resumen de una excepción y abrir app_crash.log al instante.
    """

    def __init__(
        self,
        parent: Optional[ctk.CTk] = None,
        title: str = "Aviso de Error del Sistema",
        message: str = "Ha ocurrido un error inesperado en la ejecución."
    ):
        super().__init__(parent)

        self.title(title)
        self.geometry("540x360")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG_MAIN)

        # Configuración modal
        self.transient(parent)
        self.lift()
        self.attributes("-topmost", True)

        self._center_window(parent)
        self._build_ui(title, message)

        try:
            self.grab_set()
        except Exception:
            pass

    def _center_window(self, parent: Optional[ctk.CTk]) -> None:
        """Centra el modal sobre la ventana principal o en la pantalla."""
        self.update_idletasks()
        w = 540
        h = 360

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

    def _build_ui(self, title: str, message: str) -> None:
        """Construye la interfaz monocromática del modal."""
        # Contenedor principal con borde sutil
        container = ctk.CTkFrame(
            self,
            fg_color=COLOR_CONTAINER,
            corner_radius=8,
            border_width=1,
            border_color=COLOR_BORDER
        )
        container.pack(fill="both", expand=True, padx=16, pady=16)

        # Encabezado
        header_frame = ctk.CTkFrame(container, fg_color="transparent")
        header_frame.pack(fill="x", padx=16, pady=(16, 8))

        icon_label = ctk.CTkLabel(
            header_frame,
            text="[!]",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        icon_label.pack(side="left", padx=(0, 10))

        title_label = ctk.CTkLabel(
            header_frame,
            text=title,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        title_label.pack(side="left", fill="x", expand=True)

        # Separador horizontal sutil
        sep = ctk.CTkFrame(container, height=1, fg_color=COLOR_BORDER)
        sep.pack(fill="x", padx=16, pady=(0, 12))

        # Cuadro de texto con el mensaje de error y scroll
        text_box = ctk.CTkTextbox(
            container,
            fg_color=COLOR_INPUT_BG,
            text_color=COLOR_TEXT_SECONDARY,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=6,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word"
        )
        text_box.insert("1.0", message)
        text_box.configure(state="disabled")
        text_box.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        # Barra de botones de acción
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(0, 16))

        # Botón destacado: Abrir Registro de Logs
        btn_open_logs = ctk.CTkButton(
            btn_frame,
            text="Abrir Registro de Logs",
            fg_color=COLOR_BTN_PRIMARY,
            hover_color=COLOR_BTN_PRIMARY_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=6,
            height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._on_open_logs
        )
        btn_open_logs.pack(side="left", padx=(0, 10))

        # Botón secundario: Cerrar
        btn_close = ctk.CTkButton(
            btn_frame,
            text="Cerrar",
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
        btn_close.pack(side="right")

    def _on_open_logs(self) -> None:
        """Manejador para abrir app_crash.log."""
        logger.info("El usuario solicitó abrir app_crash.log desde el modal de error.")
        open_log_file()


def show_error_modal(parent: Optional[ctk.CTk], title: str, message: str) -> None:
    """Helper para instanciar el modal de error de forma segura."""
    try:
        dialog = ErrorDialog(parent=parent, title=title, message=message)
        dialog.focus()
    except Exception as e:
        logger.error(f"Error creando instancia de ErrorDialog: {e}")
