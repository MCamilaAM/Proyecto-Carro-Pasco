# SPDX-License-Identifier: MIT
"""
Panel de Control Visual con GamepadMapperLib para el Robot PASCO.
Incluye visualizador gráfico realista de mando en tiempo real (estilo SingleGamepadMapperApp),
telemetría del robot PASCO, parada de emergencia con bloqueo seguro y acceso directo
al remapeador y calibrador visual Qt.
"""

import os
import sys
import time
import math
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from gamepad_mapper import GamepadManager, Button, Stick, Trigger, ControllerType

# Importar PascoBot si está disponible
try:
    from pasco.pasco_bot import PascoBot
    PASCO_AVAILABLE = True
except ImportError:
    PASCO_AVAILABLE = False


# Constantes de control
DEFAULT_PASCO_ID = "438-576"
DEADZONE = 0.10
MAX_THRESHOLD = 0.75
MAX_SPEED = 720
ACCEL = 720

LIFT_MIN = -130
LIFT_MAX = 130
PINZA_MIN = -130
PINZA_MAX = 130

SERVO_STEP = 12
SERVO_UPDATE_INTERVAL = 0.03

INVERT_DRIVE = False
INVERT_LIFT = False
INVERT_PINZA = False
SWAP_SERVO_PORTS = True


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


class VisualGamepadApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🎮 Panel Visual - Robot PASCO & GamepadMapper")
        self.root.geometry("1060x720")
        self.root.minsize(960, 660)
        self.root.configure(bg="#14151a")

        # Gamepad Manager
        self.pad = GamepadManager()
        self.pad_initialized = self.pad.initialize()

        # Pasco Robot
        self.bot = PascoBot() if PASCO_AVAILABLE else None
        self.bot_connected = False
        self.is_connecting = False

        # Estados de control y parada de emergencia
        self.vel_a = 0
        self.vel_b = 0
        self.last_vel_a = 0
        self.last_vel_b = 0
        self.is_moving = False
        self.emergency_latched = False

        self.lift_angle = 0
        self.pinza_angle = 0
        self.last_lift = None
        self.last_pinza = None
        self.last_servo_send = 0

        self.enable_robot_output = tk.BooleanVar(value=True)

        self._build_ui()
        self.root.bind("<space>", lambda e: self._toggle_emergency_stop())
        self.root.bind("<Escape>", lambda e: self._toggle_emergency_stop())
        self._start_poll_loop()

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Header Frame
        header = tk.Frame(self.root, bg="#1e2028", height=64)
        header.pack(fill=tk.X, side=tk.TOP)

        title_frame = tk.Frame(header, bg="#1e2028")
        title_frame.pack(side=tk.LEFT, padx=20, pady=12)

        tk.Label(
            title_frame,
            text="🎮 ROBOT PASCO // CONTROL VISUAL & GAMEPAD MAPPER",
            font=("Segoe UI", 14, "bold"),
            fg="#50fa7b",
            bg="#1e2028"
        ).pack(anchor=tk.W)

        self.status_badge = tk.Label(
            header,
            text="● ESPERANDO MANDO",
            font=("Segoe UI", 10, "bold"),
            fg="#ffb86c",
            bg="#282a36",
            padx=14,
            pady=6,
            relief=tk.FLAT
        )
        self.status_badge.pack(side=tk.RIGHT, padx=20)

        # Main Split Container
        main_container = tk.Frame(self.root, bg="#14151a")
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # Left Column: Gamepad Visualizer (Realistic Gamepad Silhouette)
        left_col = tk.LabelFrame(
            main_container,
            text=" 🕹️ Estado del Mando en Tiempo Real ",
            font=("Segoe UI", 11, "bold"),
            fg="#8be9fd",
            bg="#1e2028",
            padx=12,
            pady=10
        )
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))

        # Canvas for Gamepad
        self.canvas = tk.Canvas(left_col, bg="#101116", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Buttons Toolbar underneath canvas
        btn_bar = tk.Frame(left_col, bg="#1e2028")
        btn_bar.pack(fill=tk.X, pady=(10, 0))

        self.cfg_btn = tk.Button(
            btn_bar,
            text="⚙️ Abrir Mapeo y Calibración (Single Player Remapper)",
            font=("Segoe UI", 10, "bold"),
            bg="#bd93f9",
            fg="#14151a",
            activebackground="#ff79c6",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=16,
            pady=8,
            cursor="hand2",
            command=self._open_qt_config
        )
        self.cfg_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Right Column: PASCO Robot Controls & Telemetry
        right_col = tk.LabelFrame(
            main_container,
            text=" 🤖 Robot PASCO // Conexión y Telemetría ",
            font=("Segoe UI", 11, "bold"),
            fg="#50fa7b",
            bg="#1e2028",
            padx=14,
            pady=10,
            width=380
        )
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False)
        right_col.pack_propagate(False)

        # Connection Box
        conn_frame = tk.Frame(right_col, bg="#1e2028")
        conn_frame.pack(fill=tk.X, pady=4)

        tk.Label(conn_frame, text="ID Bluetooth:", font=("Segoe UI", 9, "bold"), fg="#f8f8f2", bg="#1e2028").pack(anchor=tk.W)
        id_box = tk.Frame(conn_frame, bg="#1e2028")
        id_box.pack(fill=tk.X, pady=4)

        self.id_entry = tk.Entry(id_box, font=("Consolas", 12, "bold"), bg="#282a36", fg="#50fa7b", insertbackground="white")
        self.id_entry.insert(0, DEFAULT_PASCO_ID)
        self.id_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=3)

        self.connect_btn = tk.Button(
            id_box,
            text="Conectar",
            font=("Segoe UI", 9, "bold"),
            bg="#50fa7b",
            fg="#14151a",
            relief=tk.FLAT,
            padx=14,
            cursor="hand2",
            command=self._toggle_connection
        )
        self.connect_btn.pack(side=tk.RIGHT)

        self.robot_status_lbl = tk.Label(
            conn_frame,
            text="● Robot Desconectado",
            font=("Segoe UI", 9, "bold"),
            fg="#ff5555",
            bg="#1e2028"
        )
        self.robot_status_lbl.pack(anchor=tk.W, pady=2)

        # Checkbox enable commands
        chk = tk.Checkbutton(
            right_col,
            text="Transmitir comandos al robot físico",
            variable=self.enable_robot_output,
            font=("Segoe UI", 9),
            fg="#f8f8f2",
            bg="#1e2028",
            selectcolor="#282a36",
            activebackground="#1e2028",
            activeforeground="#50fa7b"
        )
        chk.pack(anchor=tk.W, pady=(4, 10))

        # Telemetry Gauges
        sep = ttk.Separator(right_col, orient="horizontal")
        sep.pack(fill=tk.X, pady=6)

        tk.Label(right_col, text="TELEMETRÍA DE MOTORES:", font=("Segoe UI", 9, "bold"), fg="#8be9fd", bg="#1e2028").pack(anchor=tk.W)

        self.lbl_vel_a = tk.Label(right_col, text="Motor Izquierdo (A):   +0 deg/s", font=("Consolas", 10), fg="#f8f8f2", bg="#1e2028")
        self.lbl_vel_a.pack(anchor=tk.W, pady=1)
        self.lbl_vel_b = tk.Label(right_col, text="Motor Derecho (B):     +0 deg/s", font=("Consolas", 10), fg="#f8f8f2", bg="#1e2028")
        self.lbl_vel_b.pack(anchor=tk.W, pady=1)

        sep2 = ttk.Separator(right_col, orient="horizontal")
        sep2.pack(fill=tk.X, pady=8)

        tk.Label(right_col, text="POSICIÓN DE SERVOMOTORES:", font=("Segoe UI", 9, "bold"), fg="#ffb86c", bg="#1e2028").pack(anchor=tk.W)

        self.lbl_lift = tk.Label(right_col, text="Elevación:     +0° [RT/LT]", font=("Consolas", 10), fg="#f8f8f2", bg="#1e2028")
        self.lbl_lift.pack(anchor=tk.W, pady=1)

        self.lbl_pinza = tk.Label(right_col, text="Pinza:         +0° [RB/LB]", font=("Consolas", 10), fg="#f8f8f2", bg="#1e2028")
        self.lbl_pinza.pack(anchor=tk.W, pady=1)

        # Emergency Stop Banner / Button
        self.stop_btn = tk.Button(
            right_col,
            text="🛑 PARADA DE EMERGENCIA",
            font=("Segoe UI", 11, "bold"),
            bg="#ff5555",
            fg="#ffffff",
            activebackground="#ff3333",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            pady=12,
            cursor="hand2",
            command=self._toggle_emergency_stop
        )
        self.stop_btn.pack(side=tk.BOTTOM, fill=tk.X, pady=(12, 0))

        self.emergency_hint = tk.Label(
            right_col,
            text="Presiona ESPACIO o ESC para parada de emergencia",
            font=("Segoe UI", 8),
            fg="#6272a4",
            bg="#1e2028"
        )
        self.emergency_hint.pack(side=tk.BOTTOM, pady=(0, 4))

    def _open_qt_config(self):
        """Abre la interfaz moderna de mapeo (SingleGamepadMapperApp) de forma segura y repetible."""
        def run_task():
            try:
                # 1. Cerrar cualquier instancia previa huérfana de SingleGamepadMapperApp
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/IM", "SingleGamepadMapperApp.exe"],
                        capture_output=True,
                        creationflags=0x08000000
                    )
                except Exception:
                    pass

                # 2. Pausar temporalmente para que libere puertos o archivos
                time.sleep(0.1)

                # 3. Lanzar SingleGamepadMapperApp.exe con entorno completo
                current_dir = os.path.dirname(os.path.abspath(__file__))
                exe_path = os.path.join(current_dir, "SingleGamepadMapperApp.exe")
                if not os.path.exists(exe_path):
                    exe_path = os.path.join(current_dir, "GamepadMapperLib", "build", "SingleGamepadMapperApp.exe")

                env = os.environ.copy()
                extra_paths = [
                    r"C:\Qt\6.8.2\msvc2022_64\bin",
                    current_dir,
                    os.path.join(current_dir, "GamepadMapperLib", "build", "_deps", "sdl3-build"),
                    os.path.join(current_dir, "GamepadMapperLib", "build"),
                ]
                env["PATH"] = ";".join([p for p in extra_paths if os.path.exists(p)]) + ";" + env.get("PATH", "")
                if os.path.exists(r"C:\Qt\6.8.2\msvc2022_64\plugins"):
                    env["QT_PLUGIN_PATH"] = r"C:\Qt\6.8.2\msvc2022_64\plugins"

                proc = subprocess.Popen([exe_path], cwd=current_dir, env=env)
                # Esperar a que el usuario termine el mapeo para recargar automáticamente
                proc.wait()

                # 4. Al cerrar el diálogo, recargar configuración en el GamepadManager
                self.pad.update()
            except Exception as e:
                print(f"Error al abrir SingleGamepadMapperApp: {e}")
                # Fallback al diálogo C-ABI directo
                try:
                    self.pad.show_single_config_dialog()
                except Exception as e2:
                    print(f"Fallback C-ABI también falló: {e2}")

        threading.Thread(target=run_task, daemon=True).start()

    def _toggle_emergency_stop(self):
        """Activa o desactiva la parada de emergencia y detiene los motores de inmediato."""
        if not self.emergency_latched:
            # ACTIVAR PARADA
            self.emergency_latched = True
            self.vel_a = 0
            self.vel_b = 0
            if self.bot and self.bot_connected:
                try:
                    self.bot.stop_steppers(9999, 9999)
                except Exception:
                    pass
                self.is_moving = False

            self.stop_btn.config(
                text="⚠️ MOTORES BLOQUEADOS\n(Click para Reanudar Control)",
                bg="#ffb86c",
                fg="#14151a"
            )
        else:
            # DESACTIVAR PARADA Y REANUDAR
            self.emergency_latched = False
            self.stop_btn.config(
                text="🛑 PARADA DE EMERGENCIA",
                bg="#ff5555",
                fg="#ffffff"
            )

    def _toggle_connection(self):
        if self.bot_connected:
            self._disconnect_robot()
        else:
            self._connect_robot()

    def _connect_robot(self):
        if not PASCO_AVAILABLE:
            messagebox.showerror("Error", "El paquete pasco no está instalado.")
            return

        target_id = self.id_entry.get().strip()
        if not target_id:
            target_id = DEFAULT_PASCO_ID

        if len(target_id) == 6 and '-' not in target_id:
            target_id = f"{target_id[:3]}-{target_id[3:]}"

        self.is_connecting = True
        self.connect_btn.config(text="Conectando...", state=tk.DISABLED, bg="#ffb86c", fg="#14151a")
        self.robot_status_lbl.config(text="● Conectando por Bluetooth...", fg="#ffb86c")

        def task():
            try:
                self.bot.connect_by_id(target_id)
                self.bot_connected = True
                self.root.after(0, self._on_connect_success, target_id)
            except Exception as e:
                # Intentar escanear
                try:
                    devs = self.bot.scan()
                    if devs:
                        self.bot.connect(devs[0])
                        self.bot_connected = True
                        self.root.after(0, self._on_connect_success, devs[0].name)
                        return
                except Exception:
                    pass
                self.root.after(0, self._on_connect_fail, str(e))

        threading.Thread(target=task, daemon=True).start()

    def _on_connect_success(self, dev_name):
        self.is_connecting = False
        self.connect_btn.config(text="Desconectar", state=tk.NORMAL, bg="#ff5555", fg="#ffffff")
        self.robot_status_lbl.config(text=f"● Conectado a {dev_name}", fg="#50fa7b")

    def _on_connect_fail(self, err):
        self.is_connecting = False
        self.bot_connected = False
        self.connect_btn.config(text="Conectar", state=tk.NORMAL, bg="#50fa7b", fg="#14151a")
        self.robot_status_lbl.config(text="❌ Error de conexión", fg="#ff5555")
        messagebox.showerror("Error Bluetooth", f"No se pudo conectar al robot PASCO:\n{err}")

    def _disconnect_robot(self):
        if self.bot and self.bot_connected:
            try:
                self.bot.stop_steppers(9999, 9999)
                self.bot.disconnect()
            except Exception:
                pass
        self.bot_connected = False
        self.connect_btn.config(text="Conectar", state=tk.NORMAL, bg="#50fa7b", fg="#14151a")
        self.robot_status_lbl.config(text="● Robot Desconectado", fg="#ff5555")

    def _start_poll_loop(self):
        self._poll_step()

    def _poll_step(self):
        # 1. Actualizar GamepadMapper
        self.pad.update()
        is_pad_connected = self.pad.is_connected(0)

        # 2. Leer estado del mando
        left_stick = self.pad.get_stick(0, Stick.LEFT) if is_pad_connected else StickState()
        right_stick = self.pad.get_stick(0, Stick.RIGHT) if is_pad_connected else StickState()
        lt = self.pad.get_trigger(0, Trigger.LEFT) if is_pad_connected else TriggerState()
        rt = self.pad.get_trigger(0, Trigger.RIGHT) if is_pad_connected else TriggerState()

        # Botones
        btns = {}
        for btn in Button:
            btns[btn] = self.pad.is_button_pressed(0, btn) if is_pad_connected else False

        # 3. Lógica de Control PASCO
        if is_pad_connected and not self.emergency_latched:
            forward = normalize_axis(left_stick.y, DEADZONE, MAX_THRESHOLD)
            turn = normalize_axis(right_stick.x, DEADZONE, MAX_THRESHOLD)

            if forward != 0.0 or turn != 0.0:
                self.vel_a, self.vel_b = calculate_split_stick_drive(forward, turn, MAX_SPEED)
            else:
                self.vel_a = 0
                self.vel_b = 0

            # Gatillos / Pinza
            rt_pressed = btns[Button.ZR] or rt.pressed or (rt.value > 0.2)
            lt_pressed = btns[Button.ZL] or lt.pressed or (lt.value > 0.2)
            rb_pressed = btns[Button.R]
            lb_pressed = btns[Button.L]

            step_lift = SERVO_STEP if not INVERT_LIFT else -SERVO_STEP
            if rt_pressed:
                self.lift_angle = min(LIFT_MAX, max(LIFT_MIN, self.lift_angle + step_lift))
            elif lt_pressed:
                self.lift_angle = min(LIFT_MAX, max(LIFT_MIN, self.lift_angle - step_lift))

            step_pinza = SERVO_STEP if not INVERT_PINZA else -SERVO_STEP
            if rb_pressed:
                self.pinza_angle = min(PINZA_MAX, max(PINZA_MIN, self.pinza_angle + step_pinza))
            elif lb_pressed:
                self.pinza_angle = min(PINZA_MAX, max(PINZA_MIN, self.pinza_angle - step_pinza))

            # Enviar a Robot PASCO si está conectado y habilitado
            if self.bot_connected and self.enable_robot_output.get() and self.bot:
                # Servos
                now = time.time()
                if (self.lift_angle != self.last_lift or self.pinza_angle != self.last_pinza) and (now - self.last_servo_send >= SERVO_UPDATE_INTERVAL):
                    try:
                        s1 = self.lift_angle if not SWAP_SERVO_PORTS else self.pinza_angle
                        s2 = self.pinza_angle if not SWAP_SERVO_PORTS else self.lift_angle
                        self.bot.set_servos("standard", s1, "standard", s2)
                        self.last_lift = self.lift_angle
                        self.last_pinza = self.pinza_angle
                        self.last_servo_send = now
                    except Exception:
                        pass

                # Motores paso a paso
                if self.vel_a != 0 or self.vel_b != 0:
                    if self.vel_a != self.last_vel_a or self.vel_b != self.last_vel_b or not self.is_moving:
                        try:
                            self.bot.rotate_steppers_continuously(self.vel_a, ACCEL, self.vel_b, ACCEL)
                            self.last_vel_a = self.vel_a
                            self.last_vel_b = self.vel_b
                            self.is_moving = True
                        except Exception:
                            pass
                else:
                    if self.is_moving:
                        try:
                            self.bot.stop_steppers(ACCEL, ACCEL)
                            self.last_vel_a = 0
                            self.last_vel_b = 0
                            self.is_moving = False
                        except Exception:
                            pass
        elif self.emergency_latched:
            self.vel_a = 0
            self.vel_b = 0

        # 4. Actualizar UI y Dibujar Canvas Realista del Mando
        self._update_telemetry_ui(is_pad_connected)
        self._draw_realistic_gamepad(left_stick, right_stick, lt, rt, btns, is_pad_connected)

        # Repetir a ~60 FPS (16 ms)
        self.root.after(16, self._poll_step)

    def _update_telemetry_ui(self, is_pad_connected):
        if is_pad_connected:
            self.status_badge.config(text="● MANDO CONECTADO (JUGADOR 1)", fg="#50fa7b", bg="#1e2028")
        else:
            self.status_badge.config(text="● ESPERANDO MANDO", fg="#ffb86c", bg="#1e2028")

        self.lbl_vel_a.config(text=f"Motor Izquierdo (A): {self.vel_a:+4d} deg/s")
        self.lbl_vel_b.config(text=f"Motor Derecho (B):   {self.vel_b:+4d} deg/s")
        self.lbl_lift.config(text=f"Elevación:   {self.lift_angle:+4d}° [RT/LT]")
        self.lbl_pinza.config(text=f"Pinza:       {self.pinza_angle:+4d}° [RB/LB]")

    def _draw_realistic_gamepad(self, ls, rs, lt, rt, btns, connected):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 20 or h < 20:
            return

        cx = w / 2
        cy = h / 2 + 10

        # Dimensiones del Mando Estilo SingleGamepadMapperApp / Pro Controller
        # 1. Silueta de la Carcasa Exterior del Mando
        body_points = [
            # Top center
            (cx - 70, cy - 120),
            (cx + 70, cy - 120),
            # Right shoulder top
            (cx + 140, cy - 105),
            (cx + 175, cy - 80),
            # Right grip upper
            (cx + 200, cy - 30),
            (cx + 215, cy + 50),
            (cx + 205, cy + 135),
            (cx + 170, cy + 160),
            # Right grip bottom tip & inner arch
            (cx + 130, cy + 140),
            (cx + 105, cy + 85),
            (cx + 50, cy + 55),
            # Center bottom arch
            (cx, cy + 50),
            (cx - 50, cy + 55),
            # Left grip inner arch & bottom tip
            (cx - 105, cy + 85),
            (cx - 130, cy + 140),
            (cx - 170, cy + 160),
            (cx - 205, cy + 135),
            (cx - 215, cy + 50),
            (cx - 200, cy - 30),
            # Left shoulder top
            (cx - 175, cy - 80),
            (cx - 140, cy - 105),
        ]

        # Sombra y Cuerpo del Mando
        self.canvas.create_polygon(body_points, fill="#2a2c35", outline="#44475a", width=3, smooth=True)

        # Panel frontal central más claro (Texture Plate)
        inner_plate = [
            (cx - 55, cy - 105),
            (cx + 55, cy - 105),
            (cx + 135, cy - 70),
            (cx + 155, cy + 10),
            (cx + 105, cy + 65),
            (cx, cy + 40),
            (cx - 105, cy + 65),
            (cx - 155, cy + 10),
            (cx - 135, cy - 70),
        ]
        self.canvas.create_polygon(inner_plate, fill="#323440", outline="#3d4050", width=1, smooth=True)

        # 2. Gatillos y Bumpers Superiores
        # LB & LT (Izquierda)
        lb_active = btns[Button.L]
        lt_active = btns[Button.ZL] or lt.pressed or (lt.value > 0.15)
        self._draw_shoulder_widget(cx - 145, cy - 135, "LT", lt.value, lt_active, is_trigger=True)
        self._draw_bumper_widget(cx - 105, cy - 128, 56, 18, "LB", lb_active)

        # RB & RT (Derecha)
        rb_active = btns[Button.R]
        rt_active = btns[Button.ZR] or rt.pressed or (rt.value > 0.15)
        self._draw_bumper_widget(cx + 50, cy - 128, 56, 18, "RB", rb_active)
        self._draw_shoulder_widget(cx + 115, cy - 135, "RT", rt.value, rt_active, is_trigger=True)

        # 3. Stick Izquierdo (Arriba a la Izquierda)
        sl_cx = cx - 95
        sl_cy = cy - 40
        self._draw_pro_stick(sl_cx, sl_cy, 40, ls.x, ls.y, "Stick L (Avance)", btns[Button.LSTICK])

        # 4. Cruceta Direccional D-Pad (Abajo a la Izquierda)
        dpad_cx = cx - 60
        dpad_cy = cy + 45
        self._draw_realistic_dpad(dpad_cx, dpad_cy, 22, btns)

        # 5. Botones de Acción (A, B, X, Y) (Arriba a la Derecha - Formación Diamante)
        abxy_cx = cx + 95
        abxy_cy = cy - 40
        b_rad = 14
        self._draw_action_button(abxy_cx, abxy_cy + 24, b_rad, "A", btns[Button.A], "#50fa7b")   # Verde
        self._draw_action_button(abxy_cx + 24, abxy_cy, b_rad, "B", btns[Button.B], "#ff5555")   # Rojo
        self._draw_action_button(abxy_cx - 24, abxy_cy, b_rad, "X", btns[Button.X], "#8be9fd")   # Azul/Cyan
        self._draw_action_button(abxy_cx, abxy_cy - 24, b_rad, "Y", btns[Button.Y], "#ffb86c")   # Amarillo/Naranja

        # 6. Stick Derecho (Abajo a la Derecha)
        sr_cx = cx + 60
        sr_cy = cy + 45
        self._draw_pro_stick(sr_cx, sr_cy, 40, rs.x, rs.y, "Stick R (Giro)", btns[Button.RSTICK])

        # 7. Botones Centrales (- / + / Home / Capture)
        # Minus (-)
        self._draw_mini_button(cx - 32, cy - 60, 10, "-", btns[Button.MINUS])
        # Plus (+)
        self._draw_mini_button(cx + 32, cy - 60, 10, "+", btns[Button.PLUS])
        # Home (Centro abajo)
        self._draw_mini_button(cx + 16, cy - 30, 8, "⌂", btns[Button.HOME])
        # Capture (Centro izquierda)
        self._draw_mini_button(cx - 16, cy - 30, 8, "◻", btns[Button.SCREENSHOT])

        # 8. Si no está conectado, mostrar cortina semitransparente con mensaje
        if not connected:
            self.canvas.create_rectangle(0, 0, w, h, fill="#101116", stipple="gray50")
            self.canvas.create_text(
                cx, cy,
                text="⚠️ ESPERANDO MANDO USB / BLUETOOTH\nConecta tu mando para visualizar sus controles en tiempo real",
                fill="#ffb86c",
                font=("Segoe UI", 12, "bold"),
                justify=tk.CENTER
            )

    def _draw_pro_stick(self, x, y, radius, sx, sy, label, clicked):
        # Cavidad exterior cóncava
        self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill="#1e2028", outline="#44475a", width=2)
        self.canvas.create_oval(x - radius + 5, y - radius + 5, x + radius - 5, y + radius - 5, fill="#232530", outline="#2b2d3a", width=1)
        # Cruz de referencia
        self.canvas.create_line(x - radius + 10, y, x + radius - 10, y, fill="#2f3140", width=1)
        self.canvas.create_line(x, y - radius + 10, x, y + radius - 10, fill="#2f3140", width=1)

        # Límite circular de desplazamiento
        max_dist = radius - 14
        dist = math.hypot(sx, sy)
        if dist > 1.0:
            nx = sx / dist
            ny = sy / dist
        else:
            nx = sx
            ny = sy

        dot_x = x + (nx * max_dist)
        dot_y = y - (ny * max_dist)  # sy > 0 es arriba

        # Sombrero del stick
        cap_rad = 16
        cap_fill = "#ff79c6" if clicked else ("#3b3e4f" if (dist < 0.1) else "#50fa7b")
        self.canvas.create_oval(dot_x - cap_rad, dot_y - cap_rad, dot_x + cap_rad, dot_y + cap_rad, fill="#2d303e", outline=cap_fill, width=2)

        # Punto brillante central
        p_color = "#ffffff" if clicked else ("#50fa7b" if (dist > 0.1) else "#6272a4")
        self.canvas.create_oval(dot_x - 5, dot_y - 5, dot_x + 5, dot_y + 5, fill=p_color, width=0)

        # Etiqueta debajo
        self.canvas.create_text(x, y + radius + 12, text=f"{label}\n({sx:+.2f}, {sy:+.2f})", fill="#f8f8f2", font=("Consolas", 8), justify=tk.CENTER)

    def _draw_realistic_dpad(self, x, y, arm_len, btns):
        # Fondo de la cruz
        arm_w = 14
        # Arriba
        u_active = btns[Button.DUP]
        self.canvas.create_rectangle(x - arm_w/2, y - arm_len - 6, x + arm_w/2, y - arm_w/2,
                                     fill="#50fa7b" if u_active else "#282a36", outline="#44475a", width=1)
        self.canvas.create_text(x, y - arm_len + 2, text="▲", fill="#14151a" if u_active else "#8be9fd", font=("Segoe UI", 7, "bold"))

        # Abajo
        d_active = btns[Button.DDOWN]
        self.canvas.create_rectangle(x - arm_w/2, y + arm_w/2, x + arm_w/2, y + arm_len + 6,
                                     fill="#50fa7b" if d_active else "#282a36", outline="#44475a", width=1)
        self.canvas.create_text(x, y + arm_len - 2, text="▼", fill="#14151a" if d_active else "#8be9fd", font=("Segoe UI", 7, "bold"))

        # Izquierda
        l_active = btns[Button.DLEFT]
        self.canvas.create_rectangle(x - arm_len - 6, y - arm_w/2, x - arm_w/2, y + arm_w/2,
                                     fill="#50fa7b" if l_active else "#282a36", outline="#44475a", width=1)
        self.canvas.create_text(x - arm_len + 2, y, text="◀", fill="#14151a" if l_active else "#8be9fd", font=("Segoe UI", 7, "bold"))

        # Derecha
        r_active = btns[Button.DRIGHT]
        self.canvas.create_rectangle(x + arm_w/2, y - arm_w/2, x + arm_len + 6, y + arm_w/2,
                                     fill="#50fa7b" if r_active else "#282a36", outline="#44475a", width=1)
        self.canvas.create_text(x + arm_len - 2, y, text="▶", fill="#14151a" if r_active else "#8be9fd", font=("Segoe UI", 7, "bold"))

        # Centro
        self.canvas.create_rectangle(x - arm_w/2, y - arm_w/2, x + arm_w/2, y + arm_w/2, fill="#232530", outline="#3d4050", width=0)

    def _draw_action_button(self, x, y, radius, label, pressed, active_color):
        bg = active_color if pressed else "#282a36"
        fg = "#14151a" if pressed else active_color
        outline = active_color if pressed else "#44475a"

        self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=bg, outline=outline, width=2)
        self.canvas.create_text(x, y, text=label, fill=fg, font=("Segoe UI", 9, "bold"))

    def _draw_bumper_widget(self, x, y, w, h, label, pressed):
        bg = "#50fa7b" if pressed else "#282a36"
        fg = "#14151a" if pressed else "#f8f8f2"
        outline = "#50fa7b" if pressed else "#44475a"

        self.canvas.create_rectangle(x, y, x + w, y + h, fill=bg, outline=outline, width=1)
        self.canvas.create_text(x + w/2, y + h/2, text=label, fill=fg, font=("Segoe UI", 8, "bold"))

    def _draw_shoulder_widget(self, x, y, label, value, pressed, is_trigger=True):
        w = 34
        h = 24
        bg = "#ff79c6" if pressed else ("#50fa7b" if value > 0.1 else "#21222c")
        fg = "#14151a" if (pressed or value > 0.1) else "#f8f8f2"

        self.canvas.create_rectangle(x, y, x + w, y + h, fill=bg, outline="#44475a", width=1)
        txt = f"{label}\n{int(value*100)}%" if is_trigger else label
        self.canvas.create_text(x + w/2, y + h/2, text=txt, fill=fg, font=("Segoe UI", 7, "bold"), justify=tk.CENTER)

    def _draw_mini_button(self, x, y, radius, label, pressed):
        bg = "#50fa7b" if pressed else "#282a36"
        fg = "#14151a" if pressed else "#8be9fd"
        self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=bg, outline="#44475a", width=1)
        self.canvas.create_text(x, y, text=label, fill=fg, font=("Segoe UI", 8, "bold"))

    def on_close(self):
        self._disconnect_robot()
        self.pad.shutdown()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = VisualGamepadApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
