"""
Componentes visuales de juego: GameCard (bloques/cuadrícula) y GameListItem (fila de lista) en Monochrome UI.
Muestra portada, título, horas de juego, logros, espacio en disco y botón de acción directa (Jugar / Instalar).
"""

from pathlib import Path
from typing import Any, Callable, Dict, Optional

import customtkinter as ctk
from PIL import Image, ImageDraw
from config import (
    CARD_IMG_HEIGHT,
    CARD_IMG_WIDTH,
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

# Dimensiones compactas para la vista en lista
LIST_IMG_WIDTH = 120
LIST_IMG_HEIGHT = 56

# Caché global en memoria de imágenes CTkImage para evitar duplicación y liberar RAM
_image_cache: Dict[str, ctk.CTkImage] = {}
_placeholder_cache: Optional[ctk.CTkImage] = None
_placeholder_list_cache: Optional[ctk.CTkImage] = None


def get_placeholder_image(width: int = CARD_IMG_WIDTH, height: int = CARD_IMG_HEIGHT) -> ctk.CTkImage:
    """Retorna un marcador de posición monocromático compartido en memoria."""
    global _placeholder_cache, _placeholder_list_cache
    if width == CARD_IMG_WIDTH:
        if _placeholder_cache is None:
            img = Image.new("RGB", (width, height), color="#1a1a1a")
            draw = ImageDraw.Draw(img)
            draw.rectangle([0, 0, width - 1, height - 1], outline="#2a2a2a", width=1)
            draw.text((width // 2, height // 2), "STEAM GAME", fill="#555555", anchor="mm")
            _placeholder_cache = ctk.CTkImage(light_image=img, dark_image=img, size=(width, height))
        return _placeholder_cache
    else:
        if _placeholder_list_cache is None:
            img = Image.new("RGB", (width, height), color="#1a1a1a")
            draw = ImageDraw.Draw(img)
            draw.rectangle([0, 0, width - 1, height - 1], outline="#2a2a2a", width=1)
            draw.text((width // 2, height // 2), "STEAM", fill="#555555", anchor="mm")
            _placeholder_list_cache = ctk.CTkImage(light_image=img, dark_image=img, size=(width, height))
        return _placeholder_list_cache


def get_cached_or_load_image(cover_path: Path, width: int = CARD_IMG_WIDTH, height: int = CARD_IMG_HEIGHT) -> ctk.CTkImage:
    """Carga y cachea en memoria una única instancia de CTkImage para ahorrar RAM."""
    path_key = f"{cover_path}_{width}x{height}"
    if path_key in _image_cache:
        return _image_cache[path_key]

    try:
        with Image.open(cover_path) as pil_raw:
            pil_img = pil_raw.convert("RGB")
            pil_resized = pil_img.resize((width, height), Image.Resampling.BILINEAR)
            ctk_img = ctk.CTkImage(
                light_image=pil_resized,
                dark_image=pil_resized,
                size=(width, height)
            )
            _image_cache[path_key] = ctk_img
            return ctk_img
    except Exception as e:
        logger.debug(f"Error cargando carátula {cover_path}: {e}")
        return get_placeholder_image(width, height)


def format_game_details(game_data: Dict[str, Any], is_installed: bool) -> str:
    """Genera el texto de detalles: horas de juego, logros (si los hay) y espacio en disco."""
    parts = []

    # 1. Horas de juego
    playtime_min = game_data.get("playtime_forever", 0)
    if playtime_min and playtime_min > 0:
        hours = playtime_min / 60.0
        parts.append(f"{hours:.1f} hrs")
    elif is_installed:
        parts.append("0 hrs")

    # 2. Logros (si se han obtenido de la API)
    achievements = game_data.get("achievements")
    if achievements and isinstance(achievements, dict) and achievements.get("total", 0) > 0:
        unlocked = achievements.get("unlocked", 0)
        total = achievements.get("total", 0)
        parts.append(f"Logros: {unlocked}/{total}")

    # 3. Espacio en disco si está instalado
    if is_installed:
        size_bytes = game_data.get("size_bytes", 0)
        if size_bytes > 0:
            size_gb = size_bytes / (1024 ** 3)
            if size_gb >= 1.0:
                parts.append(f"{size_gb:.1f} GB")
            else:
                size_mb = size_bytes / (1024 ** 2)
                parts.append(f"{size_mb:.0f} MB")
    elif not parts:
        parts.append("No instalado")

    return " • ".join(parts)


class GameCard(ctk.CTkFrame):
    """
    Tarjeta interactiva ampliada y llamativa para vista en Bloques (Grid).
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
            corner_radius=10,
            width=280,
            height=250,
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
        self._lbl_details: Optional[ctk.CTkLabel] = None

        self._build_ui()

    def _build_ui(self) -> None:
        cover_path_str = self.game_data.get("cover_path")
        cover_path = Path(cover_path_str) if cover_path_str else None

        if cover_path and cover_path.exists():
            self._ctk_image = get_cached_or_load_image(cover_path, CARD_IMG_WIDTH, CARD_IMG_HEIGHT)
        else:
            self._ctk_image = get_placeholder_image(CARD_IMG_WIDTH, CARD_IMG_HEIGHT)

        self._cover_image_label = ctk.CTkLabel(
            self,
            image=self._ctk_image,
            text="",
            corner_radius=8
        )
        self._cover_image_label.pack(padx=10, pady=(10, 6))

        display_name = self.name if len(self.name) <= 26 else f"{self.name[:24]}..."
        title_label = ctk.CTkLabel(
            self,
            text=display_name,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        title_label.pack(fill="x", padx=12, pady=(0, 2))

        info_text = format_game_details(self.game_data, self.is_installed)
        self._lbl_details = ctk.CTkLabel(
            self,
            text=info_text,
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        )
        self._lbl_details.pack(fill="x", padx=12, pady=(0, 6))

        btn_text = "Jugar" if self.is_installed else "Instalar"
        btn_action = ctk.CTkButton(
            self,
            text=btn_text,
            fg_color=COLOR_BTN_PRIMARY,
            hover_color=COLOR_BTN_PRIMARY_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_color=COLOR_BORDER_FOCUS,
            border_width=1,
            corner_radius=8,
            height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._handle_action_click
        )
        btn_action.pack(fill="x", padx=10, pady=(0, 10), side="bottom")

    def update_details(self, game_data: Dict[str, Any]) -> None:
        self.game_data.update(game_data)
        if self._lbl_details:
            self._lbl_details.configure(text=format_game_details(self.game_data, self.is_installed))

    def set_cover_image(self, cover_path: Path) -> None:
        if not cover_path.exists() or not self._cover_image_label:
            return
        self._ctk_image = get_cached_or_load_image(cover_path, CARD_IMG_WIDTH, CARD_IMG_HEIGHT)
        self._cover_image_label.configure(image=self._ctk_image)

    def _handle_action_click(self) -> None:
        if self.on_action:
            self.on_action(self.appid)


class GameListItem(ctk.CTkFrame):
    """
    Componente visual horizontal para vista en Lista.
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
            height=72,
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
        self._lbl_details: Optional[ctk.CTkLabel] = None

        self._build_ui()

    def _build_ui(self) -> None:
        cover_path_str = self.game_data.get("cover_path")
        cover_path = Path(cover_path_str) if cover_path_str else None

        if cover_path and cover_path.exists():
            self._ctk_image = get_cached_or_load_image(cover_path, LIST_IMG_WIDTH, LIST_IMG_HEIGHT)
        else:
            self._ctk_image = get_placeholder_image(LIST_IMG_WIDTH, LIST_IMG_HEIGHT)

        # Portada a la izquierda
        self._cover_image_label = ctk.CTkLabel(
            self,
            image=self._ctk_image,
            text="",
            corner_radius=6
        )
        self._cover_image_label.pack(side="left", padx=10, pady=8)

        # Columna de texto central (Título + Detalles)
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=(8, 12), pady=10)

        lbl_title = ctk.CTkLabel(
            info_frame,
            text=self.name,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        lbl_title.pack(fill="x", side="top")

        info_text = format_game_details(self.game_data, self.is_installed)
        self._lbl_details = ctk.CTkLabel(
            info_frame,
            text=info_text,
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        )
        self._lbl_details.pack(fill="x", side="bottom")

        # Botón de acción a la derecha
        btn_text = "Jugar" if self.is_installed else "Instalar"
        btn_action = ctk.CTkButton(
            self,
            text=btn_text,
            fg_color=COLOR_BTN_PRIMARY,
            hover_color=COLOR_BTN_PRIMARY_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_color=COLOR_BORDER_FOCUS,
            border_width=1,
            corner_radius=8,
            width=110,
            height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._handle_action_click
        )
        btn_action.pack(side="right", padx=16, pady=16)

    def update_details(self, game_data: Dict[str, Any]) -> None:
        self.game_data.update(game_data)
        if self._lbl_details:
            self._lbl_details.configure(text=format_game_details(self.game_data, self.is_installed))

    def set_cover_image(self, cover_path: Path) -> None:
        if not cover_path.exists() or not self._cover_image_label:
            return
        self._ctk_image = get_cached_or_load_image(cover_path, LIST_IMG_WIDTH, LIST_IMG_HEIGHT)
        self._cover_image_label.configure(image=self._ctk_image)

    def _handle_action_click(self) -> None:
        if self.on_action:
            self.on_action(self.appid)
