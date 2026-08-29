# 🤖 Proyecto Carro PASCO & GamepadMapper

Control universal de precisión para el robot **PASCO //control.Node** con mandos de consola (Xbox, PlayStation 4/5 DualSense, Nintendo Switch Pro Controller / Joy-Cons, y genéricos) mediante **Python** y **GamepadMapperLib (C++20)**.

---

## 🌟 Características

- **🕹️ Mapeo Universal de Mandos (GamepadMapperLib C++20):**
  - Compatible de forma nativa con cualquier mando USB o Bluetooth sin necesidad de hacks de números de eje.
  - Soporte de remapeo visual interactivo y calibración de zonas muertas.
- **🖥️ Panel Gráfico en Tiempo Real (`gui_control.py`):**
  - Visualizador a 60 FPS con animación en vivo de palancas analógicas, porcentaje de gatillos y botones iluminados.
  - Telemetría en tiempo real de velocidad de motores y ángulos de elevación y pinza.
  - Conexión por ID Bluetooth con reconexión en segundo plano sin congelar la ventana.
  - Botón de **Parada de Emergencia** y modo seguro de prueba sin mover el robot.
- **🦾 Control de Tracción y Servomotores:**
  - **Palanca Izquierda (Eje Y):** Avance / Retroceso suave con aceleración controlada.
  - **Palanca Derecha (Eje X):** Giro continuo de precisión en 360°.
  - **`RT` / `R2` / `ZR`:** Subir elevación / pinza.
  - **`LT` / `L2` / `ZL`:** Bajar elevación / pinza.
  - **`RB` / `R1` / `R`:** Abrir pinza.
  - **`LB` / `L1` / `L`:** Cerrar pinza completa (hasta -130°).

---

## 🚀 Instalación en Nuevos Dispositivos

### Opción 1: Instalación Rápida (1 solo clic en Windows) ⭐
1. Clona o descarga el repositorio en tu ordenador:
   ```bash
   git clone --recurse-submodules https://github.com/MCamilaAM/Proyecto-Carro-Pasco.git
   ```
2. Haz doble clic en **`setup.bat`**.
   - El script verificará Python e instalará todas las librerías necesarias automáticamente.

### Opción 2: Instalación Manual por Terminal
```powershell
# Instalar dependencias requeridas
pip install -r requirements.txt
```

---

## 🎮 Ejecución

Puedes iniciar el proyecto usando los archivos ejecutables por lotes o directamente por terminal:

| Lanzador | Descripción | Comando por Terminal |
| :--- | :--- | :--- |
| **`iniciar_panel_visual.bat`** | **Panel gráfico completo** con visualizador de mando y telemetría | `python gui_control.py` |
| **`iniciar_control_consola.bat`** | Control ligero directo por consola de comandos | `python main.py` |
| **`configurar_mando.bat`** | Herramienta gráfica para remapear botones y calibrar palancas | `SingleSwitchMapperApp.exe` |

---

## 📁 Estructura del Repositorio

```
Proyecto-Carro-Pasco/
├── gui_control.py            # Panel de control gráfico interactivo
├── main.py                   # Script de control por consola
├── gamepad_mapper.py         # Wrapper en Python (ctypes) para GamepadMapperLib
├── scan_devices.py           # Escáner de diagnóstico Bluetooth BLE
├── requirements.txt          # Dependencias de Python (pasco, bleak, nest_asyncio)
├── setup.bat                 # Instalador automático en 1 clic
├── iniciar_panel_visual.bat  # Lanzador de la interfaz visual
├── iniciar_control_consola.bat # Lanzador del modo consola
├── configurar_mando.bat      # Lanzador del remapeador Qt
├── GamepadMapper.dll         # Librería C++ precompilada
├── SDL3.dll                  # Motor de hardware y controladores
├── platforms/                # Plugin de plataforma Qt (qwindows.dll)
└── GamepadMapperLib/         # Código fuente C++20 de la librería (Submódulo)
```
