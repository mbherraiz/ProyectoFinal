"""
Componente visual de tarjeta de juego en Monochrome UI.
Muestra portada, título, detalles y botón de acción directa (Jugar / Instalar).
"""

from pathlib import Path
from typing import Any, Callable, Dict, Optional

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk
from config import (
    COLOR_BORDER,
    COLOR_BORDER_FOCUS,
    COLOR_BTN_PRIMARY,
    COLOR_BTN_PRIMARY_HOVER,
    COLOR_CONTAINER,
    COLOR_CONTAINER_HOVER,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)
from logger import get_logger

logger = get_logger("GameCard")

# Dimensiones estándar para la imagen de cabecera de Steam (ratio 460x215)
CARD_IMG_WIDTH = 216
CARD_IMG_HEIGHT = 101

# Caché global en memoria de imágenes CTkImage para evitar duplicación y liberar RAM
_image_cache: Dict[str, ctk.CTkImage] = {}
_placeholder_cache: Optional[ctk.CTkImage] = None


def get_placeholder_image() -> ctk.CTkImage:
    """Retorna un marcador de posición monocromático compartido en memoria."""
    global _placeholder_cache
    if _placeholder_cache is None:
        img = Image.new("RGB", (CARD_IMG_WIDTH, CARD_IMG_HEIGHT), color="#181818")
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, CARD_IMG_WIDTH - 1, CARD_IMG_HEIGHT - 1], outline="#262626", width=1)
        draw.text((CARD_IMG_WIDTH // 2, CARD_IMG_HEIGHT // 2), "STEAM GAME", fill="#444444", anchor="mm")
        _placeholder_cache = ctk.CTkImage(light_image=img, dark_image=img, size=(CARD_IMG_WIDTH, CARD_IMG_HEIGHT))
    return _placeholder_cache


def get_cached_or_load_image(cover_path: Path) -> ctk.CTkImage:
    """Carga y cachea en memoria una única instancia de CTkImage para ahorrar RAM."""
    path_key = str(cover_path)
    if path_key in _image_cache:
        return _image_cache[path_key]

    try:
        with Image.open(cover_path) as pil_raw:
            pil_img = pil_raw.convert("RGB")
            # Redimensionar directamente a tamaño de tarjeta para liberar memoria
            pil_resized = pil_img.resize((CARD_IMG_WIDTH, CARD_IMG_HEIGHT), Image.Resampling.BILINEAR)
            ctk_img = ctk.CTkImage(
                light_image=pil_resized,
                dark_image=pil_resized,
                size=(CARD_IMG_WIDTH, CARD_IMG_HEIGHT)
            )
            _image_cache[path_key] = ctk_img
            return ctk_img
    except Exception as e:
        logger.debug(f"Error cargando carátula {cover_path}: {e}")
        return get_placeholder_image()


class GameCard(ctk.CTkFrame):
    """
    Tarjeta interactiva con diseño monocromático para mostrar un juego.
    """

    def __init__(
        self,
        master: Any,
        game_data: Dict[str, Any],
        is_installed: bool = True,
        on_action: Optional[Callable[[int], None]] = None,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=COLOR_CONTAINER,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=8,
            width=240,
            height=200,
            **kwargs
        )
        self.pack_propagate(False)

        self.game_data = game_data
        self.appid = int(game_data["appid"])
        self.name = game_data.get("name", f"App {self.appid}")
        self.is_installed = is_installed
        self.on_action = on_action

        self._cover_image_label: Optional[ctk.CTkLabel] = None
        self._ctk_image: Optional[ctk.CTkImage] = None

        self._build_ui()

    def _build_ui(self) -> None:
        """Construye los elementos visuales de la tarjeta."""
        # 1. Portada del juego optimizada
        cover_path_str = self.game_data.get("cover_path")
        cover_path = Path(cover_path_str) if cover_path_str else None

        if cover_path and cover_path.exists():
            self._ctk_image = get_cached_or_load_image(cover_path)
        else:
            self._ctk_image = get_placeholder_image()

        self._cover_image_label = ctk.CTkLabel(
            self,
            image=self._ctk_image,
            text="",
            corner_radius=6
        )
        self._cover_image_label.pack(padx=8, pady=(8, 4))

        # 2. Título del juego (con truncamiento para evitar desbordes)
        display_name = self.name if len(self.name) <= 24 else f"{self.name[:22]}..."
        title_label = ctk.CTkLabel(
            self,
            text=display_name,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        title_label.pack(fill="x", padx=10, pady=(2, 0))

        # 3. Subtítulo con información adicional (tamaño en disco o tiempo de juego)
        info_text = self._format_info_text()
        info_label = ctk.CTkLabel(
            self,
            text=info_text,
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        )
        info_label.pack(fill="x", padx=10, pady=(0, 4))

        # 4. Botón de acción (Jugar / Instalar)
        btn_text = "Jugar" if self.is_installed else "Instalar"
        btn_action = ctk.CTkButton(
            self,
            text=btn_text,
            fg_color=COLOR_BTN_PRIMARY,
            hover_color=COLOR_BTN_PRIMARY_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=6,
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._handle_action_click
        )
        btn_action.pack(fill="x", padx=8, pady=(0, 8), side="bottom")

    def _format_info_text(self) -> str:
        """Formatea el texto secundario de la tarjeta."""
        if self.is_installed:
            size_bytes = self.game_data.get("size_bytes", 0)
            if size_bytes > 0:
                size_gb = size_bytes / (1024 ** 3)
                if size_gb >= 1.0:
                    return f"Espacio: {size_gb:.1f} GB"
                size_mb = size_bytes / (1024 ** 2)
                return f"Espacio: {size_mb:.0f} MB"
            return "Instalado"
        else:
            playtime_min = self.game_data.get("playtime_forever", 0)
            if playtime_min > 0:
                hours = playtime_min / 60.0
                return f"Jugado: {hours:.1f} horas"
            return "En biblioteca (No instalado)"

    def set_cover_image(self, cover_path: Path) -> None:
        """Actualiza dinámicamente la portada de la tarjeta una vez descargada."""
        if not cover_path.exists() or not self._cover_image_label:
            return

        self._ctk_image = get_cached_or_load_image(cover_path)
        self._cover_image_label.configure(image=self._ctk_image)

    def _handle_action_click(self) -> None:
        """Dispara el callback con el appid."""
        if self.on_action:
            self.on_action(self.appid)
