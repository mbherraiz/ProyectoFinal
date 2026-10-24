"""
Pestaña de juegos instalados localmente en disco (appmanifest_*.acf).
Muestra catálogo listo para jugar, filtrado dinámico por texto y descarga asíncrona de portadas.
"""

import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk
from config import (
    COLOR_BG_MAIN,
    COLOR_BORDER,
    COLOR_BORDER_FOCUS,
    COLOR_BTN_PRIMARY,
    COLOR_BTN_PRIMARY_HOVER,
    COLOR_CONTAINER,
    COLOR_INPUT_BG,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)
import database
from core import api_client, steam_detector
from logger import get_logger
from ui.dispatcher import dispatch_to_main
from ui.game_card import GameCard

logger = get_logger("InstalledTab")


class InstalledTab(ctk.CTkFrame):
    """
    Vista de juegos instalados listos para ejecutar.
    """

    def __init__(
        self,
        master: Any,
        on_launch_game: Optional[Callable[[int], None]] = None,
        **kwargs
    ):
        super().__init__(master, fg_color=COLOR_BG_MAIN, **kwargs)

        self.on_launch_game = on_launch_game
        self._games: List[Dict[str, Any]] = []
        self._filtered_games: List[Dict[str, Any]] = []
        self._card_widgets: Dict[int, GameCard] = {}
        self._is_loading = False

        self._build_ui()
        self.load_games_async()

    def _build_ui(self) -> None:
        """Construye la barra superior de búsqueda y la cuadrícula desplazable."""
        # Barra superior de control
        top_bar = ctk.CTkFrame(self, fg_color=COLOR_CONTAINER, height=44, corner_radius=6, border_color=COLOR_BORDER, border_width=1)
        top_bar.pack(fill="x", padx=16, pady=(12, 8))
        top_bar.pack_propagate(False)

        # Campo de búsqueda
        self.entry_search = ctk.CTkEntry(
            top_bar,
            placeholder_text="Buscar en juegos instalados...",
            font=ctk.CTkFont(size=11),
            fg_color=COLOR_INPUT_BG,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            height=28,
            width=260
        )
        self.entry_search.pack(side="left", padx=(12, 10), pady=8)
        self.entry_search.bind("<KeyRelease>", self._on_search_changed)

        # Contador de juegos
        self.lbl_count = ctk.CTkLabel(
            top_bar,
            text="Cargando juegos instalados...",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_MUTED
        )
        self.lbl_count.pack(side="left", padx=4)

        # Botón de refrescar
        self.btn_refresh = ctk.CTkButton(
            top_bar,
            text="Actualizar",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=COLOR_BTN_PRIMARY,
            hover_color=COLOR_BTN_PRIMARY_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=4,
            height=28,
            width=85,
            command=self.load_games_async
        )
        self.btn_refresh.pack(side="right", padx=(0, 12), pady=8)

        # Contenedor desplazable para la cuadrícula
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        # Cuadrícula interna
        self.grid_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.grid_container.pack(fill="both", expand=True)

    def load_games_async(self) -> None:
        """Inicia la detección de juegos instalados en un hilo secundario sin congelar la GUI."""
        if self._is_loading:
            return

        self._is_loading = True
        self.lbl_count.configure(text="Escaneando bibliotecas de Steam...")
        self.btn_refresh.configure(state="disabled")

        def _worker():
            try:
                # 1. Buscar en disco todos los appmanifest_*.acf
                games = steam_detector.get_installed_games()

                # 2. Vincular con carátulas cacheadas
                for g in games:
                    cached_cover = api_client.get_cached_cover_path(g["appid"])
                    if cached_cover:
                        g["cover_path"] = str(cached_cover)

                # 3. Guardar en SQLite para modo sin conexión
                database.save_installed_games(games)

                # 4. Actualizar interfaz en el hilo principal
                dispatch_to_main(lambda: self._on_games_loaded(games))

                # 5. Descargar carátulas faltantes en segundo plano
                missing_appids = [g["appid"] for g in games if not g.get("cover_path")]
                if missing_appids:
                    api_client.download_covers_pool(
                        missing_appids,
                        on_cover_ready=lambda appid, path: dispatch_to_main(lambda: self._on_cover_downloaded(appid, path))
                    )

            except Exception as e:
                logger.error(f"Error escaneando juegos instalados: {e}")
                # Fallback: leer de la base de datos local
                cached_games = database.get_installed_games()
                dispatch_to_main(lambda: self._on_games_loaded(cached_games))

        threading.Thread(target=_worker, name="ScanInstalledGames", daemon=True).start()

    def _on_games_loaded(self, games: List[Dict[str, Any]]) -> None:
        """Callback ejecutado en el hilo principal cuando la lista de juegos está lista."""
        self._games = games
        self._is_loading = False
        self.btn_refresh.configure(state="normal")
        self._apply_filter()

    def _on_search_changed(self, event=None) -> None:
        """Filtra la lista de juegos al escribir en el campo de búsqueda."""
        self._apply_filter()

    def _apply_filter(self) -> None:
        """Aplica el texto de búsqueda y re-renderiza la cuadrícula."""
        query = self.entry_search.get().lower().strip()
        if query:
            self._filtered_games = [g for g in self._games if query in g.get("name", "").lower()]
        else:
            self._filtered_games = list(self._games)

        count = len(self._filtered_games)
        total = len(self._games)
        if query:
            self.lbl_count.configure(text=f"Mostrando {count} de {total} juegos instalados")
        else:
            self.lbl_count.configure(text=f"{total} juegos listos para jugar")

        self._render_grid()

    def _render_grid(self) -> None:
        """Renderiza las tarjetas en una cuadrícula responsiva."""
        # Limpiar tarjetas existentes
        for widget in self.grid_container.winfo_children():
            widget.destroy()
        self._card_widgets.clear()
        import gc
        gc.collect()

        if not self._filtered_games:
            lbl_empty = ctk.CTkLabel(
                self.grid_container,
                text="No se encontraron juegos instalados en las bibliotecas de Steam detectadas.",
                font=ctk.CTkFont(size=13),
                text_color=COLOR_TEXT_MUTED
            )
            lbl_empty.pack(pady=60)
            return

        # Número de columnas (3 o 4 según ancho típico)
        cols = 4
        for i in range(cols):
            self.grid_container.columnconfigure(i, weight=1, pad=10)

        for idx, game in enumerate(self._filtered_games):
            r = idx // cols
            c = idx % cols

            card = GameCard(
                self.grid_container,
                game_data=game,
                is_installed=True,
                on_action=self._handle_launch_click
            )
            card.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")
            self._card_widgets[int(game["appid"])] = card

    def _on_cover_downloaded(self, appid: int, path: Path) -> None:
        """Actualiza la carátula de una tarjeta cuando su descarga finaliza."""
        database.update_cover_path(appid, str(path))
        if appid in self._card_widgets:
            self._card_widgets[appid].set_cover_image(path)

    def _handle_launch_click(self, appid: int) -> None:
        """Delega la ejecución del juego al manejador principal."""
        if self.on_launch_game:
            self.on_launch_game(appid)
