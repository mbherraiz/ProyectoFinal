"""
Pestaña de juegos instalados localmente en disco (appmanifest_*.acf).
Muestra catálogo listo para jugar, alternancia entre vista de Bloques (Cuadrícula) y Lista,
scroll infinito optimizado por bloques sin tirones/bucles, y soporte para horas de juego y logros.
"""

import gc
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

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
from core import api_client, steam_detector
from logger import get_logger
from ui.dispatcher import dispatch_to_main
from ui.game_card import GameCard, GameListItem

logger = get_logger("InstalledTab")

BATCH_SIZE = 16  # Elementos a añadir por lote en scroll infinito


class InstalledTab(ctk.CTkFrame):
    """
    Vista de juegos instalados con alternancia de vista (Bloques / Lista)
    y scroll infinito optimizado.
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
        self._card_widgets: Dict[int, Union[GameCard, GameListItem]] = {}
        self._is_loading = False

        # Modo de visualización: "grid" o "list"
        self._view_mode = "grid"

        # Control del scroll infinito
        self._rendered_count = 0
        self._is_rendering_batch = False

        self._build_ui()
        self.load_games_async()

    def _build_ui(self) -> None:
        """Construye la barra superior con buscador, botón de vista, contador y área con scroll."""
        # Barra superior de control
        top_bar = ctk.CTkFrame(
            self,
            fg_color=COLOR_CONTAINER,
            height=54,
            corner_radius=8,
            border_color=COLOR_BORDER,
            border_width=1
        )
        top_bar.pack(fill="x", padx=16, pady=(12, 8))
        top_bar.pack_propagate(False)

        # Campo de búsqueda
        self.entry_search = ctk.CTkEntry(
            top_bar,
            placeholder_text="Buscar en juegos instalados...",
            font=ctk.CTkFont(size=13),
            fg_color=COLOR_INPUT_BG,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            height=36,
            width=280
        )
        self.entry_search.pack(side="left", padx=(14, 8), pady=9)
        self.entry_search.bind("<KeyRelease>", self._on_search_changed)

        # Botón para cambiar vista (Bloques / Lista) al lado de buscar
        self.btn_view_toggle = ctk.CTkButton(
            top_bar,
            text="Lista",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_BTN_SECONDARY,
            hover_color=COLOR_BTN_SECONDARY_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=6,
            height=34,
            width=78,
            command=self._toggle_view_mode
        )
        self.btn_view_toggle.pack(side="left", padx=4, pady=9)

        # Contador de juegos
        self.lbl_count = ctk.CTkLabel(
            top_bar,
            text="Cargando juegos instalados...",
            font=ctk.CTkFont(size=13),
            text_color=COLOR_TEXT_MUTED
        )
        self.lbl_count.pack(side="left", padx=12)

        # Botón de refrescar
        self.btn_refresh = ctk.CTkButton(
            top_bar,
            text="Actualizar",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_BTN_PRIMARY,
            hover_color=COLOR_BTN_PRIMARY_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=6,
            height=34,
            width=95,
            command=self.load_games_async
        )
        self.btn_refresh.pack(side="right", padx=(0, 14), pady=9)

        # Contenedor desplazable optimizado
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        # Enlace del scrollbar para disparar la carga progresiva al aproximarse al final
        try:
            scrollbar = self.scroll_frame._parent_canvas.yview
            # Monitorear movimiento de scroll mediante un callback periódico liviano
            self._check_scroll_position()
        except Exception:
            pass

        # Contenedor interno
        self.grid_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.grid_container.pack(fill="both", expand=True)

    def _check_scroll_position(self) -> None:
        """Comprueba periódicamente si el usuario está cerca del fondo para cargar más elementos."""
        try:
            if not self.winfo_exists():
                return
            canvas = getattr(self.scroll_frame, "_parent_canvas", None)
            if canvas:
                y_view = canvas.yview()
                # y_view es una tupla (top_pct, bottom_pct), ej. (0.7, 0.95)
                if len(y_view) >= 2 and y_view[1] >= 0.88:
                    if self._rendered_count < len(self._filtered_games):
                        self._render_next_batch()
        except Exception:
            pass
        self.after(300, self._check_scroll_position)

    def _toggle_view_mode(self) -> None:
        """Alterna entre modo Bloques (Cuadrícula) y Lista."""
        if self._view_mode == "grid":
            self._view_mode = "list"
            self.btn_view_toggle.configure(text="Bloques")
        else:
            self._view_mode = "grid"
            self.btn_view_toggle.configure(text="Lista")

        self._reset_and_render()

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

                # 2. Enriquecer con horas de juego de la base de datos local (library_games)
                library_cache = {int(g["appid"]): g for g in database.get_library_games()}
                for g in games:
                    aid = int(g["appid"])
                    if aid in library_cache:
                        g["playtime_forever"] = library_cache[aid].get("playtime_forever", 0)

                    cached_cover = api_client.get_cached_cover_path(aid)
                    if cached_cover:
                        g["cover_path"] = str(cached_cover)

                # 3. Guardar en SQLite
                database.save_installed_games(games)

                # 4. Actualizar interfaz en el hilo principal
                dispatch_to_main(lambda: self._on_games_loaded(games))

                # 5. Descargar carátulas faltantes
                missing_appids = [g["appid"] for g in games if not g.get("cover_path")]
                if missing_appids:
                    api_client.download_covers_pool(
                        missing_appids,
                        on_cover_ready=lambda appid, path: dispatch_to_main(lambda: self._on_cover_downloaded(appid, path))
                    )

                # 6. Consultar logros de forma asíncrona si hay API Key
                self._fetch_achievements_async(games)

            except Exception as e:
                logger.error(f"Error escaneando juegos instalados: {e}")
                cached_games = database.get_installed_games()
                dispatch_to_main(lambda: self._on_games_loaded(cached_games))

        threading.Thread(target=_worker, name="ScanInstalledGames", daemon=True).start()

    def _fetch_achievements_async(self, games: List[Dict[str, Any]]) -> None:
        """Obtiene logros en segundo plano para cada juego si el usuario configuró API Key."""
        steamid = database.get_setting("steamid64", "")
        apikey = database.get_setting("api_key", "")
        if not steamid or not apikey:
            return

        def _achievements_worker():
            for g in games:
                aid = int(g["appid"])
                ach = api_client.get_game_achievements(steamid, aid, apikey)
                if ach:
                    g["achievements"] = ach
                    dispatch_to_main(lambda a=aid, ach_data=ach: self._on_achievements_loaded(a, ach_data))

        threading.Thread(target=_achievements_worker, name="InstalledAchievementsWorker", daemon=True).start()

    def _on_achievements_loaded(self, appid: int, achievements: Dict[str, int]) -> None:
        """Actualiza el widget si está montado actualmente."""
        if appid in self._card_widgets:
            self._card_widgets[appid].update_details({"achievements": achievements})

    def _on_games_loaded(self, games: List[Dict[str, Any]]) -> None:
        self._games = games
        self._is_loading = False
        self.btn_refresh.configure(state="normal")
        self._apply_filter()

    def _on_search_changed(self, event=None) -> None:
        self._apply_filter()

    def _apply_filter(self) -> None:
        query = self.entry_search.get().lower().strip()
        if query:
            self._filtered_games = [g for g in self._games if query in g.get("name", "").lower()]
        else:
            self._filtered_games = list(self._games)

        count = len(self._filtered_games)
        total = len(self._games)
        if query:
            self.lbl_count.configure(text=f"Mostrando {count} de {total} instalados")
        else:
            self.lbl_count.configure(text=f"{total} juegos listos para jugar")

        self._reset_and_render()

    def _reset_and_render(self) -> None:
        """Reinicia el scroll y empieza a renderizar el primer lote."""
        for widget in self.grid_container.winfo_children():
            widget.destroy()
        self._card_widgets.clear()

        # Resetear configuración de columnas para evitar que la cuadrícula interfiera con la lista
        for col_idx in range(10):
            self.grid_container.columnconfigure(col_idx, weight=0, pad=0)

        gc.collect()

        self._rendered_count = 0

        # Reiniciar posición del canvas a arriba
        try:
            self.scroll_frame._parent_canvas.yview_moveto(0.0)
        except Exception:
            pass

        if not self._filtered_games:
            lbl_empty = ctk.CTkLabel(
                self.grid_container,
                text="No se encontraron juegos instalados.",
                font=ctk.CTkFont(size=14),
                text_color=COLOR_TEXT_MUTED
            )
            lbl_empty.pack(pady=60)
            return

        # Renderizar primer lote
        self._render_next_batch()

    def _render_next_batch(self) -> None:
        """Renderiza el siguiente lote de tarjetas o filas de forma progresiva sin congelar."""
        if self._is_rendering_batch or self._rendered_count >= len(self._filtered_games):
            return

        self._is_rendering_batch = True
        start_idx = self._rendered_count
        end_idx = min(start_idx + BATCH_SIZE, len(self._filtered_games))
        batch = self._filtered_games[start_idx:end_idx]

        if self._view_mode == "grid":
            cols = 3  # 3 columnas para tarjetas más anchas y legibles
            for i in range(cols):
                self.grid_container.columnconfigure(i, weight=1, pad=12)

            for i, game in enumerate(batch):
                curr_idx = start_idx + i
                r = curr_idx // cols
                c = curr_idx % cols

                card = GameCard(
                    self.grid_container,
                    game_data=game,
                    is_installed=True,
                    on_action=self._handle_launch_click
                )
                card.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")
                self._card_widgets[int(game["appid"])] = card
        else:
            # Modo Lista
            self.grid_container.columnconfigure(0, weight=1)
            for i, game in enumerate(batch):
                curr_idx = start_idx + i
                item = GameListItem(
                    self.grid_container,
                    game_data=game,
                    is_installed=True,
                    on_action=self._handle_launch_click
                )
                item.grid(row=curr_idx, column=0, padx=8, pady=4, sticky="ew")
                self._card_widgets[int(game["appid"])] = item

        self._rendered_count = end_idx
        self._is_rendering_batch = False

    def _on_cover_downloaded(self, appid: int, path: Path) -> None:
        database.update_cover_path(appid, str(path))
        if appid in self._card_widgets:
            self._card_widgets[appid].set_cover_image(path)

    def _handle_launch_click(self, appid: int) -> None:
        if self.on_launch_game:
            self.on_launch_game(appid)
