"""
Control de estados de presencia en Steam (En línea, Ausente, Invisible, Desconectado)
y accesos directos a la lista de amigos y chat mediante URIs nativas.
"""

import os
import subprocess
from typing import Dict
from config import (
    STEAM_URI_CHAT,
    STEAM_URI_FRIENDS,
    STEAM_URI_STATUS_AWAY,
    STEAM_URI_STATUS_INVISIBLE,
    STEAM_URI_STATUS_OFFLINE,
    STEAM_URI_STATUS_ONLINE,
)
from logger import get_logger

logger = get_logger("PresenceManager")

PRESENCE_URIS: Dict[str, str] = {
    "online": STEAM_URI_STATUS_ONLINE,
    "away": STEAM_URI_STATUS_AWAY,
    "invisible": STEAM_URI_STATUS_INVISIBLE,
    "offline": STEAM_URI_STATUS_OFFLINE,
}


def _invoke_steam_uri(uri: str) -> bool:
    """Ejecuta una URI de Steam de forma segura en Windows."""
    logger.info(f"Invocando URI de presencia Steam: {uri}")
    try:
        if hasattr(os, "startfile"):
            os.startfile(uri)
        else:
            subprocess.Popen(["cmd.exe", "/c", "start", uri])
        return True
    except Exception as e:
        logger.error(f"Error al invocar URI '{uri}': {e}")
        return False


def set_presence(status: str) -> bool:
    """
    Cambia el estado de amigos en Steam.
    Valores válidos: 'online', 'away', 'invisible', 'offline'.
    """
    clean_status = status.lower().strip()
    uri = PRESENCE_URIS.get(clean_status)
    if not uri:
        logger.warning(f"Estado de presencia desconocido: {status}")
        return False
    return _invoke_steam_uri(uri)


def set_online() -> bool:
    """Establece estado En línea."""
    return set_presence("online")


def set_away() -> bool:
    """Establece estado Ausente."""
    return set_presence("away")


def set_invisible() -> bool:
    """Establece estado Invisible."""
    return set_presence("invisible")


def set_offline() -> bool:
    """Establece estado Desconectado."""
    return set_presence("offline")


def open_friends_list() -> bool:
    """Abre la ventana de lista de amigos de Steam."""
    return _invoke_steam_uri(STEAM_URI_FRIENDS)


def open_chat_window() -> bool:
    """Abre la ventana de chat de Steam."""
    return _invoke_steam_uri(STEAM_URI_CHAT)
