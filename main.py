import os
import sys
import time
import math
from pasco.pasco_bot import PascoBot

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
SERVO_UPDATE_INTERVAL = 0.02 # Control de frecuencia BLE (70ms) para evitar delay

# Opciones de Inversión y Puertos
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
    left_power = forward_val + turn_val
    right_power = forward_val - turn_val

    max_power = max(abs(left_power), abs(right_power))
    if max_power > 1.0:
        left_power /= max_power
        right_power /= max_power

    vel_a = int(-left_power * max_speed)
    vel_b = int(right_power * max_speed)

    return vel_a, vel_b

def main():
    print("=========================================================")
    print("=== CONTROL AUTOMÁTICO PASCO CON MAPEO NUMÉRICO DIRECTO ===")
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

    # 2. INICIALIZAR PYGAME DESPUÉS DE ESTABLECER LA CONEXIÓN BLUETOOTH
    os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
    import pygame
    pygame.init()
    pygame.joystick.init()

    joysticks = []
    for i in range(pygame.joystick.get_count()):
        joy = pygame.joystick.Joystick(i)
        joy.init()
        joysticks.append(joy)
        print(f"🎮 Mando detectado: {joy.get_name()}")

    if not joysticks:
        print("ℹ️ Mando físico no detectado en este momento. Conecta tu mando USB/Bluetooth.")

    print("\n---------------------------------------------------------")
    print(" MAPEO NUMÉRICO DIRECTO DE CONTROLES:")
    print(" 🕹️ Palanca Izquierda (Eje 1):    Avance / Retroceso 100%")
    print(" 🕹️ Palanca Derecha (Eje 2/3):   Giro 360° Continuo")
    print(" 🦾 RT / L2 / R2 (Botón 7 / Eje 5): SUBIR Pinza")
    print(" 🦾 LT / L2 / L2 (Botón 6 / Eje 4): BAJAR Pinza")
    print(" 🖐️ RB / R1 (Botón 5):            ABRIR Pinza")
    print(" 🖐️ LB / L1 (Botón 4):            CERRAR Pinza Total")
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
            # Procesar eventos de mandos en Pygame de forma aislada
            try:
                events = pygame.event.get()
            except Exception:
                events = []

            for event in events:
                if event.type == pygame.JOYDEVICEADDED:
                    try:
                        joy = pygame.joystick.Joystick(event.device_index)
                        joy.init()
                        if joy not in joysticks:
                            joysticks.append(joy)
                            print(f"🎮 Mando conectado: {joy.get_name()}")
                    except Exception:
                        pass
                elif event.type == pygame.JOYDEVICEREMOVED:
                    joysticks.clear()
                    print("🎮 Mando desconectado.")

            vel_a = 0
            vel_b = 0

            if joysticks:
                try:
                    joy = joysticks[0]
                    n_axes = joy.get_numaxes()
                    n_buttons = joy.get_numbuttons()
                    joy_name = joy.get_name().lower()

                    # Bandera para mandos PlayStation / DualSense
                    is_ps = any(k in joy_name for k in ['dualsense', 'playstation', 'ps5', 'ps4', 'dualshock', 'wireless controller'])

                    # --- 1. LECTURA POR ÍNDICES NUMÉRICOS DIRECTOS DE PALANCAS ---
                    raw_forward = joy.get_axis(1) if n_axes > 1 else 0.0
                    forward = normalize_axis(raw_forward, DEADZONE, MAX_THRESHOLD)

                    # Ejes de Palanca Derecha:
                    # En DualSense PS5: Eje 2 (X) y Eje 3 (Y)
                    # En Xbox: Eje 3 (X) y Eje 4 (Y)
                    axis_rx = 2 if (is_ps and n_axes > 2) else (3 if n_axes > 3 else (2 if n_axes > 2 else 0))
                    axis_ry = 3 if (is_ps and n_axes > 3) else (4 if n_axes > 4 else (3 if n_axes > 3 else 1))

                    raw_turn_x = joy.get_axis(axis_rx) if n_axes > axis_rx else 0.0
                    raw_turn_y = -joy.get_axis(axis_ry) if n_axes > axis_ry else 0.0

                    norm_turn_x = -normalize_axis(raw_turn_x, DEADZONE, MAX_THRESHOLD)
                    norm_turn_y = -normalize_axis(raw_turn_y, DEADZONE, MAX_THRESHOLD)

                    magnitude_right = math.hypot(norm_turn_x, norm_turn_y)
                    turn = norm_turn_x if magnitude_right > 0 else 0.0

                    if forward != 0.0 or turn != 0.0:
                        vel_a, vel_b = calculate_split_stick_drive(forward, turn, MAX_SPEED)

                    # --- 2. LECTURA POR ÍNDICES NUMÉRICOS DIRECTOS DE BOTONES Y GATILLOS ---
                    b4 = joy.get_button(9) if n_buttons > 9 else False
                    b5 = joy.get_button(10) if n_buttons > 10 else False
                    b6 = joy.get_button(6) if n_buttons > 6 else False
                    b7 = joy.get_button(7) if n_buttons > 7 else False

                    ax4 = (joy.get_axis(4) > 0.1) if n_axes > 4 else False
                    ax5 = (joy.get_axis(5) > 0.1) if n_axes > 5 else False

                    # SUBIR ELEVACIÓN (RT / R2): Botón 7 o Eje 5
                    rt_pressed = b7 or ax5
                    # BAJAR ELEVACIÓN (LT / L2): Botón 6 o Eje 4
                    lt_pressed = b6 or ax4

                    # ABRIR PINZA (RB / R1): Botón 5
                    rb_pressed = b5
                    # CERRAR PINZA COMPLETA (LB / L1): Botón 4
                    lb_pressed = b4

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
        try:
            bot.disconnect()
        except Exception:
            pass
        print("Desconectado de forma segura.")

if __name__ == "__main__":
    main()