"""
Pestaña de biblioteca completa de Steam (Steam Web API + Soporte de Familia y Caché SQLite).
Incluye sincronización con múltiples cuentas familiares, fusión de juegos compartidos instalados,
paginación fluida de alto rendimiento (sin tirones de scroll) y bajo consumo de memoria RAM.
"""

import gc
import math
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

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
from ui.game_card import GameCard

logger = get_logger("LibraryTab")

PAGE_SIZE = 24  # Tarjetas por página para garantizar 60 FPS y consumo mínimo de RAM


class LibraryTab(ctk.CTkFrame):
    """
    Vista del catálogo completo del usuario conectado con Steam Web API,
    soporte para bibliotecas familiares compartidas y paginación optimizada.
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
        self._card_widgets: Dict[int, GameCard] = {}
        self._is_syncing = False

        self._current_page = 1
        self._total_pages = 1

        self._build_ui()
        self.load_initial_data()

    def _build_ui(self) -> None:
        """Construye la barra superior, el área de cuadrícula y la barra de paginación."""
        # 1. Barra superior
        top_bar = ctk.CTkFrame(self, fg_color=COLOR_CONTAINER, height=44, corner_radius=6, border_color=COLOR_BORDER, border_width=1)
        top_bar.pack(fill="x", padx=16, pady=(12, 6))
        top_bar.pack_propagate(False)

        # Buscador
        self.entry_search = ctk.CTkEntry(
            top_bar,
            placeholder_text="Buscar en toda la biblioteca...",
            font=ctk.CTkFont(size=11),
            fg_color=COLOR_INPUT_BG,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            height=28,
            width=260
        )
        self.entry_search.pack(side="left", padx=(12, 10), pady=8)
        self.entry_search.bind("<KeyRelease>", self._on_search_changed)

        # Indicador de estado / contador
        self.lbl_status = ctk.CTkLabel(
            top_bar,
            text="Cargando catálogo...",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_MUTED
        )
        self.lbl_status.pack(side="left", padx=4)

        # Botón sincronizar con Steam
        self.btn_sync = ctk.CTkButton(
            top_bar,
            text="Sincronizar",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=COLOR_BTN_PRIMARY,
            hover_color=COLOR_BTN_PRIMARY_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=4,
            height=28,
            width=95,
            command=self.sync_with_steam_async
        )
        self.btn_sync.pack(side="right", padx=(0, 12), pady=8)

        # 2. Contenedor con scroll para las tarjetas
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=16, pady=(0, 4))

        self.grid_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.grid_container.pack(fill="both", expand=True)

        # 3. Barra inferior de paginación fluida
        self.pag_bar = ctk.CTkFrame(self, fg_color=COLOR_CONTAINER, height=38, corner_radius=6, border_color=COLOR_BORDER, border_width=1)
        self.pag_bar.pack(fill="x", padx=16, pady=(0, 8), side="bottom")
        self.pag_bar.pack_propagate(False)

        self.btn_prev_page = ctk.CTkButton(
            self.pag_bar,
            text="◀ Anterior",
            font=ctk.CTkFont(size=11),
            fg_color=COLOR_BTN_SECONDARY,
            hover_color=COLOR_BTN_SECONDARY_HOVER,
            text_color=COLOR_TEXT_SECONDARY,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=4,
            height=26,
            width=85,
            command=self._prev_page
        )
        self.btn_prev_page.pack(side="left", padx=(12, 8), pady=6)

        self.lbl_page_info = ctk.CTkLabel(
            self.pag_bar,
            text="Página 1 de 1",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_MUTED
        )
        self.lbl_page_info.pack(side="left", padx=8, pady=6)

        self.btn_next_page = ctk.CTkButton(
            self.pag_bar,
            text="Siguiente ▶",
            font=ctk.CTkFont(size=11),
            fg_color=COLOR_BTN_SECONDARY,
            hover_color=COLOR_BTN_SECONDARY_HOVER,
            text_color=COLOR_TEXT_SECONDARY,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=4,
            height=26,
            width=85,
            command=self._next_page
        )
        self.btn_next_page.pack(side="left", padx=8, pady=6)

    def load_initial_data(self) -> None:
        """Carga la lista en caché local (SQLite) al iniciar la pestaña y sincroniza instalados."""
        cached_games = database.get_library_games()
        installed = database.get_installed_games()
        self._installed_appids = {int(g["appid"]) for g in installed}

        if cached_games:
            # Asegurar que cualquier juego instalado en disco esté presente en la lista
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
        """
        Sincroniza el catálogo con la Steam Web API (incluyendo cuentas familiares)
        y fusiona todos los juegos instalados localmente.
        """
        if self._is_syncing:
            return

        self._is_syncing = True
        self.btn_sync.configure(state="disabled")
        self.lbl_status.configure(text="Conectando con Steam Web API...")

        def _worker():
            steamid = database.get_setting("steamid64", "")
            family_ids_raw = database.get_setting("family_steamids", "")
            apikey = database.get_setting("api_key", "")

            # Construir lista de SteamIDs a consultar (personal + familia)
            query_ids = []
            if steamid:
                query_ids.append(steamid)
            if family_ids_raw:
                query_ids.extend([s.strip() for s in family_ids_raw.replace("\n", ",").split(",") if s.strip()])

            if not query_ids or not apikey:
                logger.info("Credenciales incompletas; recurriendo a caché local SQLite.")
                cached = database.get_library_games()
                msg = "Para sincronizar, ingresa tu SteamID64 (y de tu familia si aplica) y la API Key en Ajustes."
                dispatch_to_main(lambda: self._on_fallback(cached, msg))
                return

            try:
                # 1. Consultar la API para todas las cuentas configuradas
                raw_games = api_client.fetch_owned_games(query_ids, apikey)

                # 2. Detectar juegos instalados localmente
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

                # 3. FUSIÓN DE JUEGOS DE FAMILIA INSTALADOS EN DISCO:
                # Si hay juegos instalados de cuentas familiares que no devuelve la API, agregarlos
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

                # 4. Guardar en SQLite
                database.save_library_games(processed_games)

                # 5. Actualizar UI
                dispatch_to_main(lambda: self._on_sync_success(processed_games, installed_ids))

                # 6. Descargar carátulas faltantes
                missing_appids = [g["appid"] for g in processed_games if not g.get("cover_path")]
                if missing_appids:
                    api_client.download_covers_pool(
                        missing_appids,
                        on_cover_ready=lambda appid, path: dispatch_to_main(lambda: self._on_cover_downloaded(appid, path))
                    )

            except (api_client.SteamAPIError, api_client.SteamNetworkError) as err:
                logger.warning(f"Fallo de sincronización ({err}). Activando modo sin conexión.")
                cached = database.get_library_games()
                msg = f"Aviso: {err}\nMostrando catálogo local guardado."
                dispatch_to_main(lambda: self._on_fallback(cached, msg))

            except Exception as e:
                logger.error(f"Error inesperado al sincronizar biblioteca: {e}")
                cached = database.get_library_games()
                msg = "No se pudo conectar con la API de Steam. Se restauró el catálogo local."
                dispatch_to_main(lambda: self._on_fallback(cached, msg))

        threading.Thread(target=_worker, name="SyncLibraryGames", daemon=True).start()

    def _on_sync_success(self, games: List[Dict[str, Any]], installed_ids: Set[int]) -> None:
        """Callback cuando la sincronización finaliza con éxito."""
        self._games = games
        self._installed_appids = installed_ids
        self._is_syncing = False
        self.btn_sync.configure(state="normal")
        self.lbl_status.configure(text=f"Total catálogo: {len(games)} juegos")
        self._current_page = 1
        self._apply_filter()

    def _on_fallback(self, cached_games: List[Dict[str, Any]], reason_message: str) -> None:
        """Maneja el modo sin conexión."""
        self._games = cached_games
        self._is_syncing = False
        self.btn_sync.configure(state="normal")
        self.lbl_status.configure(text=f"Modo Sin Conexión ({len(cached_games)} juegos)")
        self._current_page = 1
        self._apply_filter()

        if self.on_notify_fallback:
            self.on_notify_fallback(reason_message)

    def _on_search_changed(self, event=None) -> None:
        """Filtra y reinicia a la primera página."""
        self._current_page = 1
        self._apply_filter()

    def _apply_filter(self) -> None:
        """Aplica el texto de búsqueda y recalcula páginas."""
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

        self._render_grid()

    def _prev_page(self) -> None:
        """Navega a la página anterior."""
        if self._current_page > 1:
            self._current_page -= 1
            self._render_grid()

    def _next_page(self) -> None:
        """Navega a la página siguiente."""
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._render_grid()

    def _render_grid(self) -> None:
        """
        Renderiza ÚNICAMENTE las tarjetas de la página actual (máximo 24).
        Esto elimina el lag de scroll y mantiene la RAM en niveles mínimos.
        """
        # Limpiar tarjetas de la página anterior
        for widget in self.grid_container.winfo_children():
            widget.destroy()
        self._card_widgets.clear()
        gc.collect()

        total_count = len(self._filtered_games)
        self._total_pages = max(1, math.ceil(total_count / PAGE_SIZE))

        # Actualizar controles de paginación
        self.lbl_page_info.configure(text=f"Página {self._current_page} de {self._total_pages} ({total_count} juegos)")
        self.btn_prev_page.configure(state="normal" if self._current_page > 1 else "disabled")
        self.btn_next_page.configure(state="normal" if self._current_page < self._total_pages else "disabled")

        if not self._filtered_games:
            lbl_empty = ctk.CTkLabel(
                self.grid_container,
                text="No hay juegos que coincidan con la búsqueda.\nPresiona 'Sincronizar' o añade cuentas de tu familia en Ajustes.",
                font=ctk.CTkFont(size=13),
                text_color=COLOR_TEXT_MUTED
            )
            lbl_empty.pack(pady=60)
            return

        # Slicing de la página actual
        start_idx = (self._current_page - 1) * PAGE_SIZE
        end_idx = min(start_idx + PAGE_SIZE, total_count)
        page_games = self._filtered_games[start_idx:end_idx]

        cols = 4
        for i in range(cols):
            self.grid_container.columnconfigure(i, weight=1, pad=10)

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

        # Resetear scroll al inicio de la página
        try:
            self.scroll_frame._parent_canvas.yview_moveto(0)
        except Exception:
            pass

    def _handle_card_action(self, appid: int) -> None:
        """Lanza el juego si está instalado, o inicia la instalación si no lo está."""
        is_installed = appid in self._installed_appids
        if is_installed:
            if self.on_launch_game:
                self.on_launch_game(appid)
        else:
            if self.on_install_game:
                self.on_install_game(appid)

    def _on_cover_downloaded(self, appid: int, path: Path) -> None:
        """Actualiza la carátula en la tarjeta visible."""
        database.update_cover_path(appid, str(path))
        if appid in self._card_widgets:
            self._card_widgets[appid].set_cover_image(path)
