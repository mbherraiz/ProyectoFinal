"""
Pestaña de biblioteca completa de Steam (Steam Web API + Soporte de Familia y Caché SQLite).
Incluye sincronización con múltiples cuentas familiares, fusión de juegos compartidos instalados,
alternancia entre vista de Bloques y Lista, y paginación fluida de alto rendimiento.
"""

import gc
import math
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

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
import database
from core import api_client, steam_detector
from logger import get_logger
from ui.dispatcher import dispatch_to_main
from ui.game_card import GameCard, GameListItem

logger = get_logger("LibraryTab")

PAGE_SIZE = 24  # Elementos por página


class LibraryTab(ctk.CTkFrame):
    """
    Vista del catálogo completo del usuario conectado con Steam Web API,
    soporte para bibliotecas familiares compartidas, alternancia entre vista de cuadrícula y lista.
    """

    def __init__(
        self,
        master: Any,
        on_launch_game: Optional[Callable[[int], None]] = None,
        on_install_game: Optional[Callable[[int], None]] = None,
        on_notify_fallback: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        super().__init__(master, fg_color=COLOR_BG_MAIN, **kwargs)

        self.on_launch_game = on_launch_game
        self.on_install_game = on_install_game
        self.on_notify_fallback = on_notify_fallback

        self._games: List[Dict[str, Any]] = []
        self._filtered_games: List[Dict[str, Any]] = []
        self._installed_appids: Set[int] = set()
        self._card_widgets: Dict[int, Union[GameCard, GameListItem]] = {}
        self._is_syncing = False

        self._view_mode = "grid"
        self._current_page = 1
        self._total_pages = 1

        self._build_ui()
        self.load_initial_data()

    def _build_ui(self) -> None:
        """Construye la barra superior, el área desplazable y la barra de paginación."""
        # 1. Barra superior
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

        # Buscador
        self.entry_search = ctk.CTkEntry(
            top_bar,
            placeholder_text="Buscar en toda la biblioteca...",
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

        # Indicador de estado / contador
        self.lbl_status = ctk.CTkLabel(
            top_bar,
            text="Cargando catálogo...",
            font=ctk.CTkFont(size=13),
            text_color=COLOR_TEXT_MUTED
        )
        self.lbl_status.pack(side="left", padx=12)

        # Botón sincronizar con Steam
        self.btn_sync = ctk.CTkButton(
            top_bar,
            text="Sincronizar",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_BTN_PRIMARY,
            hover_color=COLOR_BTN_PRIMARY_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=6,
            height=34,
            width=105,
            command=self.sync_with_steam_async
        )
        self.btn_sync.pack(side="right", padx=(0, 14), pady=9)

        # 2. Contenedor con scroll para las tarjetas
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=16, pady=(0, 6))

        self.grid_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.grid_container.pack(fill="both", expand=True)

        # 3. Barra inferior de paginación fluida
        self.pag_bar = ctk.CTkFrame(
            self,
            fg_color=COLOR_CONTAINER,
            height=46,
            corner_radius=8,
            border_color=COLOR_BORDER,
            border_width=1
        )
        self.pag_bar.pack(fill="x", padx=16, pady=(0, 10), side="bottom")
        self.pag_bar.pack_propagate(False)

        self.btn_prev_page = ctk.CTkButton(
            self.pag_bar,
            text="◀ Anterior",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_BTN_SECONDARY,
            hover_color=COLOR_BTN_SECONDARY_HOVER,
            text_color=COLOR_TEXT_SECONDARY,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=6,
            height=32,
            width=95,
            command=self._prev_page
        )
        self.btn_prev_page.pack(side="left", padx=(14, 8), pady=7)

        self.lbl_page_info = ctk.CTkLabel(
            self.pag_bar,
            text="Página 1 de 1",
            font=ctk.CTkFont(size=13),
            text_color=COLOR_TEXT_PRIMARY
        )
        self.lbl_page_info.pack(side="left", padx=10, pady=7)

        self.btn_next_page = ctk.CTkButton(
            self.pag_bar,
            text="Siguiente ▶",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_BTN_SECONDARY,
            hover_color=COLOR_BTN_SECONDARY_HOVER,
            text_color=COLOR_TEXT_SECONDARY,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=6,
            height=32,
            width=95,
            command=self._next_page
        )
        self.btn_next_page.pack(side="left", padx=8, pady=7)

    def _toggle_view_mode(self) -> None:
        """Alterna entre vista en Bloques (cuadrícula) y Lista."""
        if self._view_mode == "grid":
            self._view_mode = "list"
            self.btn_view_toggle.configure(text="Bloques")
        else:
            self._view_mode = "grid"
            self.btn_view_toggle.configure(text="Lista")
        self._render_page()

    def load_initial_data(self) -> None:
        """Carga la lista en caché local (SQLite) al iniciar la pestaña y sincroniza instalados."""
        cached_games = database.get_library_games()
        installed = database.get_installed_games()
        self._installed_appids = {int(g["appid"]) for g in installed}

        if cached_games:
            cached_ids = {int(g["appid"]) for g in cached_games}
            for inst in installed:
                inst_id = int(inst["appid"])
                if inst_id not in cached_ids:
                    cached_games.append({
                        "appid": inst_id,
                        "name": inst.get("name", f"App {inst_id}"),
                        "playtime_forever": 0,
                        "img_icon_url": "",
                        "cover_path": inst.get("cover_path", ""),
                        "is_installed": 1
                    })
            self._games = cached_games
            self._apply_filter()
            self.lbl_status.configure(text=f"Caché local: {len(self._games)} juegos")
        else:
            self.sync_with_steam_async()

    def sync_with_steam_async(self) -> None:
        """Sincroniza el catálogo con la Steam Web API y fusiona los instalados."""
        if self._is_syncing:
            return

        self._is_syncing = True
        self.btn_sync.configure(state="disabled")
        self.lbl_status.configure(text="Conectando con Steam Web API...")

        def _worker():
            steamid = database.get_setting("steamid64", "")
            family_ids_raw = database.get_setting("family_steamids", "")
            apikey = database.get_setting("api_key", "")

            query_ids = []
            if steamid:
                query_ids.append(steamid)
            if family_ids_raw:
                query_ids.extend([s.strip() for s in family_ids_raw.replace("\n", ",").split(",") if s.strip()])

            if not query_ids or not apikey:
                logger.info("Credenciales incompletas; recurriendo a caché local SQLite.")
                cached = database.get_library_games()
                msg = "Para sincronizar, ingresa tu SteamID64 y la API Key en Ajustes."
                dispatch_to_main(lambda: self._on_fallback(cached, msg))
                return

            try:
                raw_games = api_client.fetch_owned_games(query_ids, apikey)
                installed_list = steam_detector.get_installed_games()
                installed_ids = {int(g["appid"]) for g in installed_list}

                processed_games = []
                seen_appids: Set[int] = set()

                for g in raw_games:
                    appid = int(g["appid"])
                    seen_appids.add(appid)
                    cached_cover = api_client.get_cached_cover_path(appid)
                    processed_games.append({
                        "appid": appid,
                        "name": g.get("name", f"App {appid}"),
                        "playtime_forever": g.get("playtime_forever", 0),
                        "img_icon_url": g.get("img_icon_url", ""),
                        "cover_path": str(cached_cover) if cached_cover else "",
                        "is_installed": appid in installed_ids
                    })

                for inst in installed_list:
                    appid = int(inst["appid"])
                    if appid not in seen_appids:
                        seen_appids.add(appid)
                        cached_cover = api_client.get_cached_cover_path(appid)
                        processed_games.append({
                            "appid": appid,
                            "name": inst.get("name", f"App {appid}"),
                            "playtime_forever": 0,
                            "img_icon_url": "",
                            "cover_path": str(cached_cover) if cached_cover else "",
                            "is_installed": True
                        })

                database.save_library_games(processed_games)
                dispatch_to_main(lambda: self._on_sync_completed(processed_games, installed_ids))

                missing_covers = [g["appid"] for g in processed_games if not g.get("cover_path")]
                if missing_covers:
                    api_client.download_covers_pool(
                        missing_covers,
                        on_cover_ready=lambda appid, path: dispatch_to_main(lambda: self._on_cover_downloaded(appid, path))
                    )

            except Exception as e:
                logger.error(f"Fallo en la sincronización con Steam Web API: {e}")
                cached = database.get_library_games()
                dispatch_to_main(lambda: self._on_fallback(cached, f"Error sincronizando: {e}"))

        threading.Thread(target=_worker, name="SyncLibraryWorker", daemon=True).start()

    def _on_sync_completed(self, games: List[Dict[str, Any]], installed_ids: Set[int]) -> None:
        self._games = games
        self._installed_appids = installed_ids
        self._is_syncing = False
        self.btn_sync.configure(state="normal")
        self.lbl_status.configure(text=f"Total catálogo: {len(games)} juegos")
        self._current_page = 1
        self._apply_filter()

    def _on_fallback(self, cached_games: List[Dict[str, Any]], reason_message: str) -> None:
        self._games = cached_games
        self._is_syncing = False
        self.btn_sync.configure(state="normal")
        self.lbl_status.configure(text=f"Modo Sin Conexión ({len(cached_games)} juegos)")
        self._current_page = 1
        self._apply_filter()

        if self.on_notify_fallback:
            self.on_notify_fallback(reason_message)

    def _on_search_changed(self, event=None) -> None:
        self._current_page = 1
        self._apply_filter()

    def _apply_filter(self) -> None:
        query = self.entry_search.get().lower().strip()
        if query:
            self._filtered_games = [g for g in self._games if query in g.get("name", "").lower()]
        else:
            self._filtered_games = list(self._games)

        total_count = len(self._filtered_games)
        self._total_pages = max(1, math.ceil(total_count / PAGE_SIZE))
        if self._current_page > self._total_pages:
            self._current_page = self._total_pages

        if query:
            self.lbl_status.configure(text=f"Filtrados {total_count} de {len(self._games)} juegos")

        self._render_page()

    def _prev_page(self) -> None:
        if self._current_page > 1:
            self._current_page -= 1
            self._render_page()

    def _next_page(self) -> None:
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._render_page()

    def _render_page(self) -> None:
        """Renderiza las tarjetas o filas correspondientes a la página actual."""
        for widget in self.grid_container.winfo_children():
            widget.destroy()
        self._card_widgets.clear()

        # Resetear configuración de columnas para evitar que la cuadrícula interfiera con la lista
        for col_idx in range(10):
            self.grid_container.columnconfigure(col_idx, weight=0, pad=0)

        gc.collect()

        total_count = len(self._filtered_games)
        self._total_pages = max(1, math.ceil(total_count / PAGE_SIZE))

        self.lbl_page_info.configure(text=f"Página {self._current_page} de {self._total_pages} ({total_count} juegos)")
        self.btn_prev_page.configure(state="normal" if self._current_page > 1 else "disabled")
        self.btn_next_page.configure(state="normal" if self._current_page < self._total_pages else "disabled")

        if not self._filtered_games:
            lbl_empty = ctk.CTkLabel(
                self.grid_container,
                text="No hay juegos que coincidan con la búsqueda.\nPresiona 'Sincronizar' o añade cuentas de tu familia en Ajustes.",
                font=ctk.CTkFont(size=14),
                text_color=COLOR_TEXT_MUTED
            )
            lbl_empty.pack(pady=60)
            return

        start_idx = (self._current_page - 1) * PAGE_SIZE
        end_idx = min(start_idx + PAGE_SIZE, total_count)
        page_games = self._filtered_games[start_idx:end_idx]

        if self._view_mode == "grid":
            cols = 3
            for i in range(cols):
                self.grid_container.columnconfigure(i, weight=1, pad=12)

            for idx, game in enumerate(page_games):
                r = idx // cols
                c = idx % cols
                appid = int(game["appid"])
                is_installed = appid in self._installed_appids or bool(game.get("is_installed"))

                card = GameCard(
                    self.grid_container,
                    game_data=game,
                    is_installed=is_installed,
                    on_action=self._handle_card_action
                )
                card.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")
                self._card_widgets[appid] = card
        else:
            self.grid_container.columnconfigure(0, weight=1)
            for idx, game in enumerate(page_games):
                appid = int(game["appid"])
                is_installed = appid in self._installed_appids or bool(game.get("is_installed"))

                item = GameListItem(
                    self.grid_container,
                    game_data=game,
                    is_installed=is_installed,
                    on_action=self._handle_card_action
                )
                item.grid(row=idx, column=0, padx=8, pady=4, sticky="ew")
                self._card_widgets[appid] = item

        try:
            self.scroll_frame._parent_canvas.yview_moveto(0.0)
        except Exception:
            pass

    def _handle_card_action(self, appid: int) -> None:
        is_installed = appid in self._installed_appids
        if is_installed:
            if self.on_launch_game:
                self.on_launch_game(appid)
        else:
            if self.on_install_game:
                self.on_install_game(appid)

    def _on_cover_downloaded(self, appid: int, path: Path) -> None:
        database.update_cover_path(appid, str(path))
        if appid in self._card_widgets:
            self._card_widgets[appid].set_cover_image(path)
