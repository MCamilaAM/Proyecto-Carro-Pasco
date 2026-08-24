# SPDX-License-Identifier: MIT
"""
Script de prueba para verificar GamepadMapperLib desde Python.
Muestra en tiempo real la lectura de sticks, gatillos y botones.
"""

import time
import sys
from gamepad_mapper import GamepadManager, Button, Stick, Trigger, ControllerType

# Ajustar codificación para consola de Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    print("==================================================")
    print("   TEST GAMEPAD MAPPER LIB (C++20 / CTYPES)")
    print("==================================================\n")

    pad = GamepadManager()
    if not pad.initialize():
        print("❌ Error al inicializar GamepadMapper.")
        return

    print("✅ GamepadMapper inicializado exitosamente.")
    print("Leyendo mando en tiempo real durante 10 segundos...")
    print("Mueve las palancas o presiona botones (Ctrl+C para salir).\n")

    try:
        start_time = time.time()
        while time.time() - start_time < 10:
            pad.update()

            if pad.is_connected(0):
                left_stick = pad.get_stick(0, Stick.LEFT)
                right_stick = pad.get_stick(0, Stick.RIGHT)
                lt = pad.get_trigger(0, Trigger.LEFT)
                rt = pad.get_trigger(0, Trigger.RIGHT)

                # Comprobar botones comunes
                pressed_btns = []
                for btn_name in ["A", "B", "X", "Y", "L", "R", "ZL", "ZR", "PLUS", "MINUS", "DUP", "DDOWN", "DLEFT", "DRIGHT"]:
                    btn_enum = getattr(Button, btn_name)
                    if pad.is_button_pressed(0, btn_enum):
                        pressed_btns.append(btn_name)

                btns_str = ", ".join(pressed_btns) if pressed_btns else "Ninguno"

                sys.stdout.write(
                    f"\r🕹️ Stick L: ({left_stick.x:+.2f}, {left_stick.y:+.2f}) | "
                    f"Stick R: ({right_stick.x:+.2f}, {right_stick.y:+.2f}) | "
                    f"LT: {lt.value:.2f} RT: {rt.value:.2f} | "
                    f"Botones: [{btns_str}]     "
                )
                sys.stdout.flush()
            else:
                sys.stdout.write("\r⚠️ Esperando conexión de mando...                              ")
                sys.stdout.flush()

            time.sleep(0.02)  # 50 Hz

    except KeyboardInterrupt:
        pass
    finally:
        pad.shutdown()
        print("\n\nGamepadMapper cerrado correctamente.")

if __name__ == "__main__":
    main()
