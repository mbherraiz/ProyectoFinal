"""
Configuración central, constantes de estilo Monochrome UI y rutas del sistema.
"""

from pathlib import Path

# Directorio raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent

# Rutas de almacenamiento y archivos locales
LOG_FILE = BASE_DIR / "app_crash.log"
DB_FILE = BASE_DIR / "steam_launcher.db"
CACHE_DIR = BASE_DIR / "cache"
COVERS_DIR = CACHE_DIR / "covers"

# Asegurar directorios de caché locales
CACHE_DIR.mkdir(parents=True, exist_ok=True)
COVERS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# PALETA DE COLORES: MONOCHROME UI (Estilo oscuro/minimalista en escala de grises)
# ---------------------------------------------------------------------------
COLOR_BG_MAIN = "#121212"          # Fondo principal oscuro
COLOR_CONTAINER = "#1e1e1e"        # Paneles, tarjetas y modales
COLOR_CONTAINER_HOVER = "#2a2a2a"  # Contenedores al pasar el cursor
COLOR_INPUT_BG = "#161616"         # Cajas de texto y campos de entrada
COLOR_BORDER = "#2e2e2e"           # Bordes sutiles
COLOR_BORDER_FOCUS = "#4e4e4e"     # Bordes activos/en foco

COLOR_BTN_PRIMARY = "#262626"      # Botones principales
COLOR_BTN_PRIMARY_HOVER = "#383838"# Hover botones principales
COLOR_BTN_SECONDARY = "#1c1c1c"    # Botones secundarios
COLOR_BTN_SECONDARY_HOVER = "#2a2a2a"

COLOR_TEXT_PRIMARY = "#ffffff"     # Texto principal blanco de alto contraste
COLOR_TEXT_SECONDARY = "#a0a0a0"   # Texto secundario / gris claro
COLOR_TEXT_MUTED = "#606060"       # Texto atenuado / subtítulos
COLOR_TEXT_DISABLED = "#404040"    # Texto deshabilitado

# Indicadores de estado monocromáticos (gradaciones de gris/blanco sutiles)
COLOR_STATUS_ONLINE = "#d0d0d0"
COLOR_STATUS_AWAY = "#909090"
COLOR_STATUS_INVISIBLE = "#606060"
COLOR_STATUS_OFFLINE = "#383838"

# ---------------------------------------------------------------------------
# BANDERAS Y PARÁMETROS STEAM
# ---------------------------------------------------------------------------
# Banderas activas y comprobadas para el cliente moderno de Steam:
# Small Mode (+open steam://open/minigameslist) desactiva la pesada tienda web en RAM.
# -no-shared-texture y -cef-disable-gpu desactivan la sobrecarga de VRAM y Chromium.
STEAM_ULTRALIGHT_FLAGS = [
    "-silent",
    "-no-shared-texture",
    "-cef-disable-gpu",
    "-cef-force-occlusion",
    "-vrdisable",
    "-udp",
    "+open",
    "steam://open/minigameslist"
]

# URLs y endpoints
STEAM_CDN_COVER_URL = "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg"
STEAM_API_BASE_URL = "https://api.steampowered.com"

# URIs nativas de Steam
STEAM_URI_RUN = "steam://run/{appid}"
STEAM_URI_INSTALL = "steam://install/{appid}"
STEAM_URI_STATUS_ONLINE = "steam://friends/status/online"
STEAM_URI_STATUS_AWAY = "steam://friends/status/away"
STEAM_URI_STATUS_INVISIBLE = "steam://friends/status/invisible"
STEAM_URI_STATUS_OFFLINE = "steam://friends/status/offline"
STEAM_URI_FRIENDS = "steam://friends/"
STEAM_URI_CHAT = "steam://friends/players"

# Dimensiones de las carátulas (ratio 460x215)
CARD_IMG_WIDTH = 260
CARD_IMG_HEIGHT = 122

# Dimensiones de la ventana
WINDOW_TITLE = "Steam Light Launcher"
WINDOW_MIN_WIDTH = 1000
WINDOW_MIN_HEIGHT = 700
DEFAULT_WIDTH = 1180
DEFAULT_HEIGHT = 780
