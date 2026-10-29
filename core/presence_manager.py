"""
Control de estados de presencia en Steam (En línea, Ausente, Invisible, Desconectado)
y accesos directos a la lista de amigos y chat mediante el cliente nativo de Steam.
"""

import os
import subprocess
from typing import Dict, Optional
from config import (
    STEAM_URI_CHAT,
    STEAM_URI_FRIENDS,
    STEAM_URI_STATUS_AWAY,
    STEAM_URI_STATUS_INVISIBLE,
    STEAM_URI_STATUS_OFFLINE,
    STEAM_URI_STATUS_ONLINE,
)
from core import steam_detector
from logger import get_logger

logger = get_logger("PresenceManager")

PRESENCE_URIS: Dict[str, str] = {
    "online": STEAM_URI_STATUS_ONLINE,
    "away": STEAM_URI_STATUS_AWAY,
    "invisible": STEAM_URI_STATUS_INVISIBLE,
    "offline": STEAM_URI_STATUS_OFFLINE,
}


def _invoke_steam_command(command_arg: str) -> bool:
    """
    Ejecuta un comando en el cliente nativo de Steam (vía steam.exe o URI nativa).
    Prioriza invocar directamente el ejecutable steam.exe para garantizar que se abra
    el cliente de escritorio y no el navegador web.
    """
    try:
        steam_path = steam_detector.get_steam_install_path()
        steam_exe = steam_detector.get_steam_executable(steam_path) if steam_path else None

        if steam_exe and steam_exe.exists():
            logger.info(f"Invocando comando Steam mediante ejecutable nativo: {steam_exe} {command_arg}")
            subprocess.Popen([str(steam_exe), command_arg])
            return True
        elif hasattr(os, "startfile"):
            logger.info(f"Invocando mediante startfile: {command_arg}")
            os.startfile(command_arg)
            return True
        else:
            subprocess.Popen(["cmd.exe", "/c", "start", command_arg])
            return True
    except Exception as e:
        logger.error(f"Error al invocar comando Steam '{command_arg}': {e}")
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
    return _invoke_steam_command(uri)


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
    """Abre la ventana nativa de lista de amigos del cliente de Steam."""
    # Invocar con steam.exe steam://open/friends para garantizar que se abra la ventana nativa del cliente
    return _invoke_steam_command("steam://open/friends")


def open_chat_window() -> bool:
    """Abre la ventana nativa de chat de amigos del cliente de Steam."""
    # Invocar con steam.exe steam://open/chat o steam://open/friends
    return _invoke_steam_command("steam://open/chat")
