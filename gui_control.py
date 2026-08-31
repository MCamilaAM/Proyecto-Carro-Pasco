# SPDX-License-Identifier: MIT
"""
Panel de Control Visual con GamepadMapperLib para el Robot PASCO.
Incluye visualizador gráfico en tiempo real de mandos (palancas, gatillos, botones),
telemetría del robot PASCO y acceso directo a la ventana de calibración/mapeo Qt.
"""

import sys
import time
import math
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from gamepad_mapper import GamepadManager, Button, Stick, Trigger, ControllerType, StickState, TriggerState

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
        self.root.geometry("980x680")
        self.root.minsize(880, 620)
        self.root.configure(bg="#1e1e24")

        # Gamepad Manager
        self.pad = GamepadManager()
        self.pad_initialized = self.pad.initialize()

        # Pasco Robot
        self.bot = PascoBot() if PASCO_AVAILABLE else None
        self.bot_connected = False
        self.is_connecting = False

        # Estados de control
        self.vel_a = 0
        self.vel_b = 0
        self.last_vel_a = 0
        self.last_vel_b = 0
        self.is_moving = False

        self.lift_angle = 0
        self.pinza_angle = 0
        self.last_lift = None
        self.last_pinza = None
        self.last_servo_send = 0

        self.enable_robot_output = tk.BooleanVar(value=True)

        self._build_ui()
        self._start_poll_loop()

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Header Frame
        header = tk.Frame(self.root, bg="#282a36", height=60)
        header.pack(fill=tk.X, side=tk.TOP)

        title_lbl = tk.Label(
            header,
            text="🎮 ROBOT PASCO // CONTROL VISUAL & GAMEPAD MAPPER",
            font=("Segoe UI", 14, "bold"),
            fg="#50fa7b",
            bg="#282a36"
        )
        title_lbl.pack(side=tk.LEFT, padx=20, pady=15)

        self.status_badge = tk.Label(
            header,
            text="● ESPERANDO MANDO",
            font=("Segoe UI", 10, "bold"),
            fg="#ffb86c",
            bg="#282a36",
            padx=10
        )
        self.status_badge.pack(side=tk.RIGHT, padx=20)

        # Main Split Container
        main_container = tk.Frame(self.root, bg="#1e1e24")
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # Left Column: Gamepad Visualizer (60% width)
        left_col = tk.LabelFrame(
            main_container,
            text=" 🕹️ Estado del Mando en Tiempo Real ",
            font=("Segoe UI", 11, "bold"),
            fg="#8be9fd",
            bg="#282a36",
            padx=10,
            pady=10
        )
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Canvas for Gamepad
        self.canvas = tk.Canvas(left_col, bg="#191a21", highlightthickness=0, height=360)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Buttons Toolbar underneath canvas
        btn_bar = tk.Frame(left_col, bg="#282a36")
        btn_bar.pack(fill=tk.X, pady=(10, 0))

        cfg_multi_btn = tk.Button(
            btn_bar,
            text="⚙️ Configurar y Calibrar Mandos (Multi-Mando)",
            font=("Segoe UI", 10, "bold"),
            bg="#bd93f9",
            fg="#ffffff",
            activebackground="#ff79c6",
            relief=tk.FLAT,
            padx=10,
            pady=6,
            command=lambda: self._open_qt_config("multi")
        )
        cfg_multi_btn.pack(fill=tk.X, expand=True)

        # Right Column: PASCO Robot Controls & Telemetry
        right_col = tk.LabelFrame(
            main_container,
            text=" 🤖 Robot PASCO // Conexión y Telemetría ",
            font=("Segoe UI", 11, "bold"),
            fg="#50fa7b",
            bg="#282a36",
            padx=12,
            pady=10,
            width=360
        )
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False)
        right_col.pack_propagate(False)

        # Connection Box
        conn_frame = tk.Frame(right_col, bg="#282a36")
        conn_frame.pack(fill=tk.X, pady=5)

        tk.Label(conn_frame, text="ID Bluetooth:", font=("Segoe UI", 9, "bold"), fg="#f8f8f2", bg="#282a36").pack(anchor=tk.W)
        id_box = tk.Frame(conn_frame, bg="#282a36")
        id_box.pack(fill=tk.X, pady=4)

        self.id_entry = tk.Entry(id_box, font=("Segoe UI", 11), bg="#44475a", fg="#ffffff", insertbackground="white")
        self.id_entry.insert(0, DEFAULT_PASCO_ID)
        self.id_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.connect_btn = tk.Button(
            id_box,
            text="Conectar",
            font=("Segoe UI", 9, "bold"),
            bg="#50fa7b",
            fg="#282a36",
            relief=tk.FLAT,
            padx=10,
            command=self._toggle_connection
        )
        self.connect_btn.pack(side=tk.RIGHT)

        self.robot_status_lbl = tk.Label(
            conn_frame,
            text="● Robot Desconectado",
            font=("Segoe UI", 9),
            fg="#ff5555",
            bg="#282a36"
        )
        self.robot_status_lbl.pack(anchor=tk.W, pady=2)

        # Checkbox enable commands
        chk = tk.Checkbutton(
            right_col,
            text="Transmitir comandos al robot físico",
            variable=self.enable_robot_output,
            font=("Segoe UI", 9),
            fg="#f8f8f2",
            bg="#282a36",
            selectcolor="#44475a",
            activebackground="#282a36",
            activeforeground="#50fa7b"
        )
        chk.pack(anchor=tk.W, pady=(5, 10))

        # Telemetry Gauges
        sep = ttk.Separator(right_col, orient="horizontal")
        sep.pack(fill=tk.X, pady=6)

        tk.Label(right_col, text="TELEMETRÍA DE MOTORES:", font=("Segoe UI", 9, "bold"), fg="#8be9fd", bg="#282a36").pack(anchor=tk.W)

        self.lbl_vel_a = tk.Label(right_col, text="Motor Izquierdo (A): 0 deg/s", font=("Consolas", 10), fg="#f8f8f2", bg="#282a36")
        self.lbl_vel_a.pack(anchor=tk.W, pady=1)
        self.lbl_vel_b = tk.Label(right_col, text="Motor Derecho (B):   0 deg/s", font=("Consolas", 10), fg="#f8f8f2", bg="#282a36")
        self.lbl_vel_b.pack(anchor=tk.W, pady=1)

        sep2 = ttk.Separator(right_col, orient="horizontal")
        sep2.pack(fill=tk.X, pady=8)

        tk.Label(right_col, text="POSICIÓN DE SERVOMOTORES:", font=("Segoe UI", 9, "bold"), fg="#ffb86c", bg="#282a36").pack(anchor=tk.W)

        self.lbl_lift = tk.Label(right_col, text="Elevación:   0° [RT/LT]", font=("Consolas", 10), fg="#f8f8f2", bg="#282a36")
        self.lbl_lift.pack(anchor=tk.W, pady=1)

        self.lbl_pinza = tk.Label(right_col, text="Pinza:       0° [RB/LB]", font=("Consolas", 10), fg="#f8f8f2", bg="#282a36")
        self.lbl_pinza.pack(anchor=tk.W, pady=1)

        # Emergency Stop
        stop_btn = tk.Button(
            right_col,
            text="🛑 PARADA DE EMERGENCIA",
            font=("Segoe UI", 10, "bold"),
            bg="#ff5555",
            fg="#ffffff",
            relief=tk.FLAT,
            pady=8,
            command=self._emergency_stop
        )
        stop_btn.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

    def _open_qt_config(self, mode="multi"):
        """Lanza la ventana Qt de mapeo multimando en un subproceso independiente y recarga la configuracion al terminar."""
        def run_and_reload():
            try:
                proc = GamepadManager.launch_config_process(mode)
                if proc:
                    proc.wait()
                    # Recargar la configuracion en GamepadMapper inmediatamente
                    self.root.after(0, self.pad.reload)
            except Exception as e:
                print(f"Error al abrir configurador Qt: {e}")

        threading.Thread(target=run_and_reload, daemon=True).start()

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
        self.connect_btn.config(text="Conectando...", state=tk.DISABLED, bg="#ffb86c")
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
        self.connect_btn.config(text="Conectar", state=tk.NORMAL, bg="#50fa7b", fg="#282a36")
        self.robot_status_lbl.config(text="❌ Error de conexión", fg="#ff5555")
        messagebox.showerror("Error Bluetooth", f"No se pudo conectar al robot PASCO:\n{err}")

    def _disconnect_robot(self):
        if self.bot and self.bot_connected:
            try:
                self.bot.disconnect()
            except Exception:
                pass
        self.bot_connected = False
        self.connect_btn.config(text="Conectar", state=tk.NORMAL, bg="#50fa7b", fg="#282a36")
        self.robot_status_lbl.config(text="● Robot Desconectado", fg="#ff5555")

    def _emergency_stop(self):
        self.vel_a = 0
        self.vel_b = 0
        if self.bot and self.bot_connected:
            try:
                self.bot.stop_steppers(ACCEL, ACCEL)
                self.is_moving = False
            except Exception:
                pass

    def _start_poll_loop(self):
        self._poll_step()

    def _poll_step(self):
        try:
            # 1. Actualizar GamepadMapper
            self.pad.update()

            # Detectar si hay algún jugador (0 a 7) conectado
            active_player = 0
            is_pad_connected = False
            for p in range(8):
                if self.pad.is_connected(p):
                    active_player = p
                    is_pad_connected = True
                    break

            # 2. Leer estado del mando
            left_stick = self.pad.get_stick(active_player, Stick.LEFT) if is_pad_connected else StickState()
            right_stick = self.pad.get_stick(active_player, Stick.RIGHT) if is_pad_connected else StickState()
            lt = self.pad.get_trigger(active_player, Trigger.LEFT) if is_pad_connected else TriggerState()
            rt = self.pad.get_trigger(active_player, Trigger.RIGHT) if is_pad_connected else TriggerState()

            # Botones
            btns = {}
            for btn in Button:
                btns[btn] = self.pad.is_button_pressed(active_player, btn) if is_pad_connected else False

            # 3. Lógica de Control PASCO
            if is_pad_connected:
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

            # 4. Actualizar UI y Dibujar Canvas del Mando
            self._update_telemetry_ui(is_pad_connected, active_player)
            self._draw_gamepad_canvas(left_stick, right_stick, lt, rt, btns, is_pad_connected)

        except Exception as e:
            print(f"Error en _poll_step: {e}")
        finally:
            # Repetir a ~60 FPS (16 ms) de forma garantizada
            self.root.after(16, self._poll_step)

    def _update_telemetry_ui(self, is_pad_connected, player_idx=0):
        if is_pad_connected:
            self.status_badge.config(text=f"● MANDO CONECTADO (JUGADOR {player_idx + 1})", fg="#50fa7b")
        else:
            self.status_badge.config(text="● ESPERANDO MANDO", fg="#ffb86c")

        self.lbl_vel_a.config(text=f"Motor Izquierdo (A): {self.vel_a:+4d} deg/s")
        self.lbl_vel_b.config(text=f"Motor Derecho (B):   {self.vel_b:+4d} deg/s")
        self.lbl_lift.config(text=f"Elevación:   {self.lift_angle:+4d}° [RT/LT]")
        self.lbl_pinza.config(text=f"Pinza:       {self.pinza_angle:+4d}° [RB/LB]")

    def _draw_gamepad_canvas(self, ls, rs, lt, rt, btns, connected):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10 or h < 10:
            return

        cx = w / 2
        cy = h / 2

        # 1. Dibujar Sticks Analógicos (Izquierdo y Derecho)
        stick_radius = 55
        # Stick L (Avance / Retroceso)
        sl_cx = cx - 140
        sl_cy = cy + 40
        self._draw_analog_stick(sl_cx, sl_cy, stick_radius, ls.x, ls.y, "Stick L (Avance)", btns[Button.LSTICK])

        # Stick R (Giro)
        sr_cx = cx + 140
        sr_cy = cy + 40
        self._draw_analog_stick(sr_cx, sr_cy, stick_radius, rs.x, rs.y, "Stick R (Giro)", btns[Button.RSTICK])

        # 2. Dibujar Gatillos Analógicos (LT / RT)
        # LT Bar
        self._draw_trigger_gauge(sl_cx - 80, cy - 90, 26, 120, lt.value, "LT / L2\n(Bajar)", btns[Button.ZL])
        # RT Bar
        self._draw_trigger_gauge(sr_cx + 54, cy - 90, 26, 120, rt.value, "RT / R2\n(Subir)", btns[Button.ZR])

        # 3. Dibujar Bumpers (LB / RB)
        self._draw_button_badge(sl_cx - 50, cy - 110, 50, 24, "LB (Cerrar)", btns[Button.L])
        self._draw_button_badge(sr_cx, cy - 110, 50, 24, "RB (Abrir)", btns[Button.R])

        # 4. Dibujar Botones de Acción (A, B, X, Y)
        abxy_cx = sr_cx + 10
        abxy_cy = cy - 35
        b_rad = 14
        self._draw_circle_button(abxy_cx, abxy_cy + 24, b_rad, "A", btns[Button.A], "#50fa7b")
        self._draw_circle_button(abxy_cx + 24, abxy_cy, b_rad, "B", btns[Button.B], "#ff5555")
        self._draw_circle_button(abxy_cx - 24, abxy_cy, b_rad, "X", btns[Button.X], "#8be9fd")
        self._draw_circle_button(abxy_cx, abxy_cy - 24, b_rad, "Y", btns[Button.Y], "#ffb86c")

        # 5. Dibujar D-Pad
        dpad_cx = sl_cx - 10
        dpad_cy = cy - 35
        self._draw_dpad_button(dpad_cx, dpad_cy - 24, 18, 14, "▲", btns[Button.DUP])
        self._draw_dpad_button(dpad_cx, dpad_cy + 24, 18, 14, "▼", btns[Button.DDOWN])
        self._draw_dpad_button(dpad_cx - 24, dpad_cy, 14, 18, "◀", btns[Button.DLEFT])
        self._draw_dpad_button(dpad_cx + 24, dpad_cy, 14, 18, "▶", btns[Button.DRIGHT])

        # 6. Botones Centrales (+ / - / Home)
        self._draw_button_badge(cx - 35, cy - 60, 24, 18, "-", btns[Button.MINUS])
        self._draw_button_badge(cx + 11, cy - 60, 24, 18, "+", btns[Button.PLUS])

        if not connected:
            self.canvas.create_rectangle(0, 0, w, h, fill="#191a21", stipple="gray50")
            self.canvas.create_text(
                cx, cy,
                text="⚠️ Conecta tu mando (USB / Bluetooth)\npara comenzar a visualizar",
                fill="#ffb86c",
                font=("Segoe UI", 12, "bold"),
                justify=tk.CENTER
            )

    def _draw_analog_stick(self, x, y, radius, sx, sy, label, pressed):
        # Base circle
        self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, outline="#44475a", width=2, fill="#21222c")
        self.canvas.create_line(x - radius, y, x + radius, y, fill="#282a36", width=1)
        self.canvas.create_line(x, y - radius, x, y + radius, fill="#282a36", width=1)

        # Animated dot
        dot_x = x + (sx * (radius - 12))
        dot_y = y - (sy * (radius - 12))  # Note: sy > 0 is up
        dot_color = "#ff79c6" if pressed else "#50fa7b"
        self.canvas.create_oval(dot_x - 10, dot_y - 10, dot_x + 10, dot_y + 10, fill=dot_color, outline="#ffffff", width=1)

        # Label
        self.canvas.create_text(x, y + radius + 15, text=f"{label}\n({sx:+.2f}, {sy:+.2f})", fill="#f8f8f2", font=("Consolas", 8), justify=tk.CENTER)

    def _draw_trigger_gauge(self, x, y, width, height, value, label, pressed):
        # Background bar
        self.canvas.create_rectangle(x, y, x + width, y + height, fill="#21222c", outline="#44475a", width=1)
        # Fill bar from bottom to top
        fill_h = int(height * max(0.0, min(1.0, value)))
        fill_color = "#50fa7b" if not pressed else "#ff79c6"
        if fill_h > 0:
            self.canvas.create_rectangle(x + 2, y + height - fill_h, x + width - 2, y + height - 2, fill=fill_color, width=0)

        # Text
        self.canvas.create_text(x + width / 2, y + height + 15, text=f"{label}\n{int(value*100)}%", fill="#f8f8f2", font=("Segoe UI", 7), justify=tk.CENTER)

    def _draw_button_badge(self, x, y, width, height, label, pressed):
        bg = "#50fa7b" if pressed else "#44475a"
        fg = "#282a36" if pressed else "#f8f8f2"
        self.canvas.create_rectangle(x, y, x + width, y + height, fill=bg, outline="#6272a4", width=1)
        self.canvas.create_text(x + width / 2, y + height / 2, text=label, fill=fg, font=("Segoe UI", 7, "bold"))

    def _draw_circle_button(self, x, y, radius, label, pressed, active_color):
        bg = active_color if pressed else "#44475a"
        fg = "#282a36" if pressed else "#f8f8f2"
        self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=bg, outline="#6272a4", width=1)
        self.canvas.create_text(x, y, text=label, fill=fg, font=("Segoe UI", 8, "bold"))

    def _draw_dpad_button(self, x, y, w, h, label, pressed):
        bg = "#8be9fd" if pressed else "#44475a"
        fg = "#282a36" if pressed else "#f8f8f2"
        self.canvas.create_rectangle(x - w / 2, y - h / 2, x + w / 2, y + h / 2, fill=bg, outline="#6272a4", width=1)
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
