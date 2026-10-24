# Steam Light Launcher

**Steam Light Launcher** es un lanzador de juegos ultraligero y cliente de optimización para Steam desarrollado en Python para Windows (compatible con Python 3.8+ y optimizado para Python 3.13). Incorpora una interfaz gráfica moderna con diseño **Monochrome UI** (escala de grises de alto contraste en CustomTkinter) y reduce el consumo de recursos de Steam al mínimo absoluto (típicamente por debajo de los 90 MB de RAM frente a los 600–1200 MB del cliente oficial con Chromium integrado).

---

## Características Principales

1. **Modo Ultraligero Transparente (< 90 MB RAM) y Telemetría de Memoria:**
   - Ejecuta `steam.exe` de forma independiente utilizando banderas optimizadas para el cliente moderno de Steam:
     `-silent -no-shared-texture -cef-disable-gpu -cef-force-occlusion -vrdisable -udp +open steam://open/minigameslist`
   - Incorpora una rutina de telemetría que invoca periódicamente la API nativa `EmptyWorkingSet` de Windows para purgar la memoria RAM no esencial de `steam.exe` y `steamwebhelper.exe`.

2. **Gestor de Rendimiento y Opciones de Steam Overlay (Shift+Tab):**
   - Modifica de forma persistente y segura el archivo `config/config.vdf` de Steam para ajustar la clave `"DisableOverlay"`.
   - Incluye un selector de fácil acceso en el panel de **Ajustes** para habilitar o deshabilitar el Steam Overlay según las preferencias del usuario.
   - Realiza un respaldo automático (`config.vdf.bak`) y gestiona el cierre ordenado y relanzamiento transparente del cliente para evitar que Steam sobreescriba los cambios en memoria.

3. **Soporte para Grupo Familiar (Steam Family Sharing) y Múltiples Cuentas:**
   - Permite ingresar tu **SteamID64 principal** junto con múltiples SteamIDs de cuentas familiares separadas por comas.
   - Unifica los catálogos en una única biblioteca combinada, identificando los juegos compartidos por el grupo familiar.

4. **Detección Dinámica de Bibliotecas Múltiples:**
   - Detecta automáticamente la ruta de instalación de Steam a través del Registro de Windows (`HKCU` y `HKLM`) y rutas predeterminadas.
   - Parsea `steamapps/libraryfolders.vdf` para encontrar juegos distribuidos en discos o unidades secundarias (D:, E:, etc.).
   - Lee todos los manifiestos `appmanifest_*.acf` para listar instantáneamente los juegos instalados y listos para jugar sin depender de llamadas de red.

5. **Integración con Steam Web API y Modo Sin Conexión (Offline Fallback):**
   - Conecta con la Web API oficial (`IPlayerService/GetOwnedGames`) para sincronizar todo el catálogo de juegos.
   - En caso de falta de conexión o errores en la API, la app activa el modo sin conexión y carga el catálogo almacenado en la base de datos local SQLite (`database.py`).
   - Descarga carátulas de forma asíncrona mediante hilos secundarios (`ThreadPoolExecutor`) y las cachea localmente en `cache/covers/` con renderizado optimizado mediante `Pillow`.

6. **Monitoreo de Descargas en Tiempo Real:**
   - Supervisa en segundo plano las carpetas `steamapps/downloading/` y los manifiestos activos.
   - Muestra una barra de progreso nativa en la barra de estado con porcentaje, velocidad de descarga en tiempo real (MB/s) y tiempo estimado restante (ETA).

7. **Minimización a la Bandeja del Sistema (System Tray) y Control de Presencia:**
   - Mientras un juego está en ejecución (detectado mediante el registro `HKCU\Software\Valve\Steam\Apps\<appid>\Running`), el launcher se minimiza a la bandeja del sistema mediante `pystray`. Al finalizar el juego, la ventana se restaura automáticamente.
   - Barra de estado interactiva para alternar presencia de amigos con un clic:
     - **En línea** (`steam://friends/status/online`)
     - **Ausente** (`steam://friends/status/away`)
     - **Invisible** (`steam://friends/status/invisible`)
     - **Desconectado** (`steam://friends/status/offline`)
     - Accesos directos para abrir la ventana de Amigos y Chat de Steam.

8. **Despachador Thread-Safe y Captura Global de Excepciones:**
   - Incluye un despachador seguro de eventos (`dispatcher.py`) que previene errores de concurrencia en la interfaz gráfica (compatibilidad total con Python 3.13).
   - Redirige excepciones no controladas y de hilos secundarios a `app_crash.log`.
   - Modal emergente Monochrome UI con el botón **"Abrir Registro de Logs"** para consultar los detalles técnicos inmediatamente.

---

## Estructura del Proyecto

```text
├── main.py                     # Entry point, bucle CustomTkinter e inicialización del sistema
├── config.py                   # Constantes, rutas, flags de Steam y paleta de colores Monochrome UI
├── database.py                 # Gestor SQLite para la caché local de juegos y ajustes de usuario
├── logger.py                   # Módulo centralizado de logging (app_crash.log) y apertura de registros
├── core/
│   ├── __init__.py
│   ├── steam_detector.py      # Detección de VDF, Registro de Windows y carpetas de biblioteca
│   ├── process_manager.py     # Control de psutil, banderas ultraligeras, ciclo de vida de juegos y purga de RAM
│   ├── overlay_manager.py     # Modificación de config.vdf para activar/desactivar Overlay
│   ├── download_tracker.py    # Lector de progreso de descargas en steamapps/downloading/
│   ├── presence_manager.py    # Control de estados de presencia (Online, Invisible, etc.) y accesos de chat
│   └── api_client.py          # Cliente HTTP para la Steam Web API (soporte multi-cuenta) y descarga de carátulas
├── ui/
│   ├── __init__.py
│   ├── dispatcher.py          # Despachador de tareas seguro para hilos (Thread-Safe UI Dispatcher)
│   ├── main_window.py         # Ventana principal en escala de grises y control del System Tray
│   ├── game_card.py           # Componente visual para tarjetas de juegos con caché de imágenes
│   ├── error_dialog.py        # Modal emergente de error con botón "Abrir Registro de Logs"
│   ├── status_bar.py          # Barra de estado inferior (presencia, descargas y telemetría de RAM)
│   ├── settings_dialog.py     # Panel de configuración (SteamID64, Cuentas Familiares, API Key, Overlay)
│   └── tabs/
│       ├── __init__.py
│       ├── installed_tab.py   # Vista de juegos instalados localmente
│       └── library_tab.py     # Vista de catálogo completo de la biblioteca
├── requirements.txt            # Dependencias del proyecto
└── README.md                   # Documentación de instalación y uso
```

---

## Requisitos e Instalación

### 1. Requisitos Previos
- **Sistema Operativo:** Windows 10 u 11 (64-bit).
- **Python:** Python 3.8 o superior (compatible con Python 3.13).
- **Steam:** Cliente de Steam instalado en el sistema.

### 2. Instalación de Dependencias
Abre una terminal PowerShell o CMD en la carpeta del proyecto y ejecuta:

```powershell
pip install -r requirements.txt
```

El archivo `requirements.txt` contiene:
```text
customtkinter>=5.2.0
psutil>=5.9.0
pystray>=0.19.5
pillow>=10.0.0
vdf>=3.4
requests>=2.31.0
```

---

## Configuración Inicial

Al abrir la aplicación por primera vez:
1. Haz clic en el botón **Ajustes** en la esquina superior derecha.
2. Configura tus credenciales:
   - **Tu SteamID64 Principal:** Tu identificador numérico de 17 dígitos (puedes obtenerlo en [steamid.io](https://steamid.io)).
   - **SteamIDs de Familiares:** Opcional. Si utilizas el grupo familiar de Steam, ingresa los SteamID64 de las otras cuentas separados por comas para combinar sus bibliotecas.
   - **Steam Web API Key:** Tu clave de desarrollador de Steam (generable gratuitamente en [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey)).
3. Ajusta las opciones de optimización y comportamiento:
   - *Lanzar Steam en modo compacto (sin tienda pesada en RAM)*
   - *Habilitar Steam Overlay en juegos (Shift+Tab)*
   - *Minimizar el launcher a la bandeja (System Tray) al iniciar un juego*
4. Presiona **Guardar y Aplicar**.

---

## Ejecución

Para iniciar el launcher, ejecuta el archivo principal:

```powershell
python main.py
```