# Proyecto Carro Pasco

Proyecto para controlar el robot PASCO //control.Node con mandos de consola (Xbox, DualSense PS5, etc.) mediante Python y Pygame.

## Características

- **Control Diferencial de Tracción (Split-Stick):**
  - Palanca izquierda: Avance / Retroceso al 100% de potencia.
  - Palanca derecha: Giro continuo en los 360° del círculo.
- **Control de Servomotores (Pinza y Elevación):**
  - `RT` / `L2` (Gatillo Derecho / Botón 7): Subir pinza.
  - `LT` / `L2` (Gatillo Izquierdo / Botón 6): Bajar pinza.
  - `RB` / `R1` (Botón Frontal Derecho / Botón 5): Abrir pinza.
  - `LB` / `L1` (Botón Frontal Izquierdo / Botón 4): Cerrar pinza completa (hasta -130°).
- **Mapeo Numérico Adaptativo:** Compatible con mandos de Xbox y PlayStation (DualSense / DualShock).
- **Conexión Automática / Manual:** Detecta automáticamente el robot en el área o permite ingresar el ID (ej. `438-576`).

## Requisitos

- Python 3.10+
- Dependencias: `pasco`, `pygame`, `bleak`, `nest_asyncio`

## Instalación y Ejecución

```powershell
# Crear y activar entorno virtual
python -m venv venv
.\venv\Scripts\Activate.ps1

# Instalación de dependencias
pip install pasco pygame bleak nest_asyncio

# Ejecución del programa principal
python main.py
```
