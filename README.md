# Steam Light Launcher

Lanzador y gestor ultraligero de juegos para Steam desarrollado en Python con interfaz oscura de alto contraste (**CustomTkinter**). Permite lanzar juegos consumiendo el mínimo de recursos y manteniendo el control de presencia y bibliotecas de Steam.

---

## Características

- **Consumo Mínimo de Recursos:** Ejecuta Steam sin cargar la tienda web Chromium en memoria y purga RAM no esencial.
- **Vista en Bloques y Lista:** Botón para alternar instantáneamente la visualización de tus juegos en cuadrícula o en lista compacta.
- **Scroll Infinito Fluido:** Carga progresiva y optimizada de juegos sin rebotes ni tirones de rueda de ratón.
- **Detalles de Juego:** Horas jugadas, espacio ocupado en disco y recuento de logros desbloqueados (mediante Steam Web API).
- **Gestión de Presencia:** Cambia tu estado a En línea, Ausente, Invisible o Desconectado con un solo clic.
- **Soporte Familiar y Modo Offline:** Unifica cuentas familiares y almacena el catálogo en SQLite local para acceder sin conexión.
- **Bandeja del Sistema (Tray):** Oculta la consola y minimiza automáticamente la ventana mientras juegas.

---

## Instalación y Uso

### 1. Requisitos
- Windows 10 u 11 (64-bit)
- Python 3.8+ instalado
- Cliente oficial de Steam instalado

### 2. Instalar Librerías
Abre PowerShell o CMD en la carpeta del proyecto y ejecuta:

```powershell
python -m pip install -r requirements.txt
```

### 3. Configuración (Opcional para Catálogo Web y Logros)
1. Inicia la app y presiona el botón **Ajustes** (arriba a la derecha).
2. Ingresa tu **SteamID64** y tu **Steam Web API Key** (generable gratis en [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey)).
3. Si juegas con Steam Family, puedes ingresar los IDs de tus familiares para ver sus juegos compartidos.
4. Pulsa **Guardar y Aplicar**.

### 4. Iniciar la Aplicación

```powershell
python main.py
```
*(También puedes ejecutar `pythonw main.py` para arrancar directamente sin ventana de terminal).*
