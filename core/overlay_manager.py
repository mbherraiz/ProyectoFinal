"""
Gestión y modificación segura del archivo config/config.vdf de Steam.
Permite activar/desactivar la interfaz superpuesta (Steam Overlay / Shift+Tab)
con respaldo previo (.bak) y reinicio ordenado del cliente Steam.
"""

import shutil
from pathlib import Path
from typing import Optional

import vdf
from core import process_manager
from logger import get_logger

logger = get_logger("OverlayManager")


def get_config_vdf_path(steam_path: Path) -> Path:
    """Retorna la ruta al archivo config/config.vdf dentro de la instalación de Steam."""
    return steam_path / "config" / "config.vdf"


def is_overlay_disabled(steam_path: Path) -> bool:
    """
    Comprueba si DisableOverlay está configurado en "1" dentro de config.vdf.
    """
    vdf_file = get_config_vdf_path(steam_path)
    if not vdf_file.exists():
        logger.warning(f"No existe el archivo {vdf_file}")
        return False

    try:
        with open(vdf_file, "r", encoding="utf-8", errors="ignore") as f:
            data = vdf.load(f)

        # Buscar en las ubicaciones habituales de Valve
        # 1. InstallConfigStore -> Software -> Valve -> Steam -> DisableOverlay
        steam_section = (
            data.get("InstallConfigStore", {})
            .get("Software", {})
            .get("Valve", {})
            .get("Steam", {})
        )
        if str(steam_section.get("DisableOverlay", "0")) == "1":
            return True

        # 2. InstallConfigStore -> system -> DisableOverlay
        system_section = data.get("InstallConfigStore", {}).get("system", {})
        if str(system_section.get("DisableOverlay", "0")) == "1":
            return True

        # 3. UserLocalConfigStore -> system -> DisableOverlay
        user_system = data.get("UserLocalConfigStore", {}).get("system", {})
        if str(user_system.get("DisableOverlay", "0")) == "1":
            return True

        return False
    except Exception as e:
        logger.error(f"Error comprobando estado de DisableOverlay en {vdf_file}: {e}")
        return False


def is_overlay_enabled(steam_path: Path) -> bool:
    """
    Comprueba si el Steam Overlay está activo (DisableOverlay == '0' o no establecido).
    """
    return not is_overlay_disabled(steam_path)


def set_overlay_enabled(
    steam_path: Path,
    enabled: bool = True,
    restart_steam_if_running: bool = True
) -> bool:
    """
    Habilita (DisableOverlay = '0') o deshabilita (DisableOverlay = '1') la interfaz superpuesta de Steam.
    """
    return set_overlay_disabled(
        steam_path=steam_path,
        disable=(not enabled),
        restart_steam_if_running=restart_steam_if_running
    )


def set_overlay_disabled(
    steam_path: Path,
    disable: bool = False,
    restart_steam_if_running: bool = True
) -> bool:
    """
    Modifica 'config/config.vdf' para establecer DisableOverlay a '1' (desactivado)
    o '0' (activado). Realiza copia de seguridad previa (.bak) y reinicia
    Steam si estaba en ejecución para garantizar que el archivo no sea sobreescrito en memoria.
    """
    vdf_file = get_config_vdf_path(steam_path)
    if not vdf_file.exists():
        logger.error(f"Archivo {vdf_file} no encontrado. No se puede configurar el overlay.")
        return False

    was_running = process_manager.is_steam_running()
    steam_exe = steam_path / "steam.exe"

    # 1. Si Steam está corriendo, cerrarlo limpiamente antes de editar
    if was_running:
        logger.info("Steam está en ejecución; procediendo a cerrarlo para modificar config.vdf de forma persistente.")
        killed = process_manager.kill_steam_cleanly(steam_exe_path=steam_exe, timeout_sec=7.0)
        if not killed:
            logger.warning("No se pudo cerrar Steam completamente, procediendo con precaución...")

    # 2. Realizar copia de respaldo config.vdf.bak
    bak_file = vdf_file.with_suffix(".vdf.bak")
    try:
        shutil.copy2(vdf_file, bak_file)
        logger.info(f"Copia de seguridad generada en: {bak_file}")
    except Exception as e:
        logger.error(f"No se pudo crear copia de respaldo de config.vdf: {e}")

    # 3. Cargar, modificar e inyectar el valor
    target_val = "1" if disable else "0"
    try:
        with open(vdf_file, "r", encoding="utf-8", errors="ignore") as f:
            data = vdf.load(f)

        # Inyectar en InstallConfigStore -> Software -> Valve -> Steam
        if "InstallConfigStore" not in data:
            data["InstallConfigStore"] = {}
        if "Software" not in data["InstallConfigStore"]:
            data["InstallConfigStore"]["Software"] = {}
        if "Valve" not in data["InstallConfigStore"]["Software"]:
            data["InstallConfigStore"]["Software"]["Valve"] = {}
        if "Steam" not in data["InstallConfigStore"]["Software"]["Valve"]:
            data["InstallConfigStore"]["Software"]["Valve"]["Steam"] = {}

        steam_node = data["InstallConfigStore"]["Software"]["Valve"]["Steam"]
        steam_node["DisableOverlay"] = target_val
        steam_node["LowPerfMode"] = "1"
        steam_node["LowBandwidth"] = "1"
        steam_node["MiniListEnabled"] = "1"

        # Inyectar también en system por compatibilidad
        if "system" not in data["InstallConfigStore"]:
            data["InstallConfigStore"]["system"] = {}
        data["InstallConfigStore"]["system"]["DisableOverlay"] = target_val

        # Guardar archivo modificado
        with open(vdf_file, "w", encoding="utf-8") as f:
            vdf.dump(data, f, pretty=True)

        logger.info(f"config.vdf actualizado con éxito: DisableOverlay = {target_val}")

    except Exception as e:
        logger.error(f"Fallo al modificar config.vdf: {e}")
        # Intentar restaurar respaldo si falló la escritura
        if bak_file.exists():
            shutil.copy2(bak_file, vdf_file)
            logger.info("Restaurado config.vdf desde respaldo tras fallo.")
        return False

    # 4. Si Steam estaba corriendo y se solicitó reinicio, relanzarlo en modo ultraligero
    if was_running and restart_steam_if_running and steam_exe.exists():
        logger.info("Relanzando Steam en modo ultraligero tras aplicar ajustes de Overlay...")
        process_manager.launch_steam_ultralight(steam_exe)

    return True
