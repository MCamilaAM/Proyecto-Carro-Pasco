import os
import sys
import time
import math
from pasco.pasco_bot import PascoBot
from gamepad_mapper import GamepadManager, Button, Stick, Trigger, ControllerType

# Ajustar codificación para la consola de Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# ID predeterminado del robot (se conecta automáticamente sin pedir input)
DEFAULT_PASCO_ID = "438-831"

# Configuración de Joystick y Velocidad de Motores
DEADZONE = 0.10        # Zona muerta inicial
MAX_THRESHOLD = 0.75   # Umbral máximo para alcanzar el 100% de potencia
MAX_SPEED = 720        # Velocidad máxima en grados/segundo
ACCEL = 720            # Aceleración en grados/segundo^2

# Configuración de Servomotores (Pinza y Elevación)
LIFT_MIN = -130        # Límite mínimo elevación (Servo 1)
LIFT_MAX = 130         # Límite máximo elevación (Servo 1)
PINZA_MIN = -130       # Límite mínimo para CIERRE COMPLETO TOTAL (Servo 2)
PINZA_MAX = 130        # Límite máximo apertura (Servo 2)

SERVO_STEP = 18        # Movimiento rápido de la pinza y elevación
SERVO_UPDATE_INTERVAL = 0.02 # Control de frecuencia BLE para evitar delay

# Opciones de Inversión y Puertos
INVERT_DRIVE = False   # Cambiar a True para invertir avance / retroceso
INVERT_LIFT = False    # Cambiar a True si la elevación va al revés
INVERT_PINZA = False   # Cambiar a True si la pinza abre/cierra al revés
SWAP_SERVO_PORTS = True # Cambiar a True si el Servo 1 es la pinza y el Servo 2 es la elevación

def normalize_axis(val, deadzone=0.10, max_threshold=0.75):
    abs_val = abs(val)
    if abs_val < deadzone:
        return 0.0
    sign = 1.0 if val > 0 else -1.0
    normalized = (abs_val - deadzone) / (max_threshold - deadzone)
    return sign * min(1.0, max(0.0, normalized))

def calculate_split_stick_drive(forward_val, turn_val, max_speed=720):
    if INVERT_DRIVE:
        forward_val = -forward_val

    left_power = forward_val - turn_val
    right_power = forward_val + turn_val

    max_power = max(abs(left_power), abs(right_power))
    if max_power > 1.0:
        left_power /= max_power
        right_power /= max_power

    vel_a = int(-left_power * max_speed)
    vel_b = int(right_power * max_speed)

    return vel_a, vel_b

def main():
    print("=========================================================")
    print("=== CONTROL AUTOMÁTICO PASCO CON GAMEPADMAPPER LIB ===")
    print("=========================================================\n")

    # 1. PERMITIR INGRESAR EL ID POR CONSOLA O PRESIONAR ENTER
    try:
        user_input_id = input(f"Ingresa el ID del PASCO a conectar (ej. 438-576) o presiona ENTER: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nPrograma cancelado.")
        return

    target_id = user_input_id if user_input_id else DEFAULT_PASCO_ID

    bot = PascoBot()
    connected = False

    if target_id:
        if len(target_id) == 6 and '-' not in target_id:
            target_id = f"{target_id[:3]}-{target_id[3:]}"

        print(f"\n[1/2] Conectando al robot '{target_id}' por Bluetooth...")
        try:
            bot.connect_by_id(target_id)
            print(f"¡CONEXIÓN EXITOSA AL ROBOT PASCO ({target_id})! 🤖✅\n")
            connected = True
        except Exception:
            print(f"No se encontró directamente '{target_id}'. Escaneando dispositivos cercanos...")

    if not connected:
        try:
            devs = bot.scan()
            if devs:
                print(f"Dispositivo detectado: '{devs[0].name}'. Conectando...")
                bot.connect(devs[0])
                print("¡CONEXIÓN EXITOSA AL ROBOT PASCO! 🤖✅\n")
                connected = True
            else:
                print("❌ No se encontró ningún robot PASCO activo emitiendo Bluetooth.")
                return
        except Exception as e:
            print(f"❌ Error al conectar por Bluetooth: {e}")
            return

    # 2. INICIALIZAR GAMEPADMAPPER
    pad = GamepadManager()
    if not pad.initialize():
        print("❌ Error al inicializar GamepadMapperLib.")
        return

    pad.update()
    if pad.is_connected(0):
        print("🎮 Mando detectado y conectado correctamente.")
    else:
        print("ℹ️ Mando físico no detectado en este momento. Conecta tu mando USB/Bluetooth.")

    print("\n---------------------------------------------------------")
    print(" MAPEO UNIVERSAL DE CONTROLES (GAMEPADMAPPER):")
    print(" 🕹️ Palanca Izquierda (Eje Y):    Avance / Retroceso 100%")
    print(" 🕹️ Palanca Derecha (Eje X):      Giro 360° Continuo")
    print(" 🦾 RT / R2 / ZR:                SUBIR Pinza / Elevación")
    print(" 🦾 LT / L2 / ZL:                BAJAR Pinza / Elevación")
    print(" 🖐️ RB / R1 / R:                 ABRIR Pinza")
    print(" 🖐️ LB / L1 / L:                 CERRAR Pinza Total")
    print(" ⏹️ Presiona Ctrl+C para salir.")
    print("---------------------------------------------------------\n")

    last_vel_a = 0
    last_vel_b = 0
    is_moving = False

    lift_angle = 0        # Elevación
    pinza_angle = 0       # Pinza (Mandíbula)
    last_lift = None
    last_pinza = None
    last_servo_send = 0   # Control de frecuencia BLE

    try:
        while True:
            # Procesar eventos del GamepadMapper
            pad.update()

            vel_a = 0
            vel_b = 0

            if pad.is_connected(0):
                try:
                    # --- 1. LECTURA DE PALANCAS ANÁLOGAS (NORMALIZADAS -1.0 a 1.0) ---
                    left_stick = pad.get_stick(0, Stick.LEFT)
                    right_stick = pad.get_stick(0, Stick.RIGHT)

                    # Avance (Palanca Izquierda Y)
                    forward = normalize_axis(left_stick.y, DEADZONE, MAX_THRESHOLD)

                    # Giro (Palanca Derecha X)
                    turn = normalize_axis(right_stick.x, DEADZONE, MAX_THRESHOLD)

                    if forward != 0.0 or turn != 0.0:
                        vel_a, vel_b = calculate_split_stick_drive(forward, turn, MAX_SPEED)

                    # --- 2. LECTURA DE BOTONES Y GATILLOS ---
                    lt_state = pad.get_trigger(0, Trigger.LEFT)
                    rt_state = pad.get_trigger(0, Trigger.RIGHT)

                    # SUBIR ELEVACIÓN (RT / R2 / ZR)
                    rt_pressed = pad.is_button_pressed(0, Button.ZR) or rt_state.pressed or (rt_state.value > 0.2)
                    # BAJAR ELEVACIÓN (LT / L2 / ZL)
                    lt_pressed = pad.is_button_pressed(0, Button.ZL) or lt_state.pressed or (lt_state.value > 0.2)

                    # ABRIR PINZA (RB / R1 / R)
                    rb_pressed = pad.is_button_pressed(0, Button.R)
                    # CERRAR PINZA (LB / L1 / L)
                    lb_pressed = pad.is_button_pressed(0, Button.L)

                    step_lift = SERVO_STEP if not INVERT_LIFT else -SERVO_STEP
                    if rt_pressed:
                        lift_angle = min(LIFT_MAX, max(LIFT_MIN, lift_angle + step_lift))
                    elif lt_pressed:
                        lift_angle = min(LIFT_MAX, max(LIFT_MIN, lift_angle - step_lift))

                    step_pinza = SERVO_STEP if not INVERT_PINZA else -SERVO_STEP
                    if rb_pressed:
                        pinza_angle = min(PINZA_MAX, max(PINZA_MIN, pinza_angle + step_pinza))
                    elif lb_pressed:
                        pinza_angle = min(PINZA_MAX, max(PINZA_MIN, pinza_angle - step_pinza))

                except Exception:
                    pass

            # --- 3. ENVIAR COMANDO A SERVOMOTORES ---
            now = time.time()
            if (lift_angle != last_lift or pinza_angle != last_pinza) and (now - last_servo_send >= SERVO_UPDATE_INTERVAL):
                try:
                    s1_val = lift_angle if not SWAP_SERVO_PORTS else pinza_angle
                    s2_val = pinza_angle if not SWAP_SERVO_PORTS else lift_angle
                    bot.set_servos("standard", s1_val, "standard", s2_val)
                    last_lift = lift_angle
                    last_pinza = pinza_angle
                    last_servo_send = now
                except Exception:
                    pass

            # --- 4. ENVIAR COMANDO A LOS MOTORES PASCO ---
            if vel_a != 0 or vel_b != 0:
                if vel_a != last_vel_a or vel_b != last_vel_b or not is_moving:
                    try:
                        bot.rotate_steppers_continuously(vel_a, ACCEL, vel_b, ACCEL)
                        last_vel_a = vel_a
                        last_vel_b = vel_b
                        is_moving = True
                    except Exception:
                        pass
            else:
                if is_moving:
                    try:
                        bot.stop_steppers(ACCEL, ACCEL)
                        last_vel_a = 0
                        last_vel_b = 0
                        is_moving = False
                    except Exception:
                        pass

            time.sleep(0.01)  # 100 FPS

    except KeyboardInterrupt:
        print("\nDeteniendo robot...")
    finally:
        pad.shutdown()
        try:
            bot.disconnect()
        except Exception:
            pass
        print("Desconectado de forma segura.")

if __name__ == "__main__":
    main()