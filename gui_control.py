# SPDX-License-Identifier: MIT
"""
Panel de Control Visual Multijugador y Multi-Robot PASCO con GamepadMapperLib.
Soporta hasta 5 mandos (Jugadores 1 a 5) y hasta 5 robots PASCO //control.Node en simultaneo.
Incorpora el renderizador de mando ultra-realista con compuertas radiales punteadas,
acotacion trigonometrica (radial clamping) y telemetria independiente.
"""

import os
import sys
import time
import math
import tkinter as tk
from tkinter import ttk, messagebox

from gamepad_mapper import GamepadManager, Button, Stick, Trigger, ControllerType, StickState, TriggerState, GamepadState
from gamepad_renderer import RealisticGamepadCanvas
from multi_pasco import MultiPascoManager, MAX_ROBOTS

# Parametros de cinemática de los robots
DEADZONE = 0.10
MAX_THRESHOLD = 0.75
MAX_SPEED = 720
ACCEL = 720

LIFT_MIN = -130
LIFT_MAX = 130
PINZA_MIN = -130
PINZA_MAX = 130

SERVO_STEP = 14
SWAP_SERVO_PORTS = True
INVERT_DRIVE = False
INVERT_LIFT = False
INVERT_PINZA = False

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
        self.root.title("🎮 Robot PASCO // Control Visual & Gamepad Mapper (5 Jugadores - 5 Robots)")
        self.root.geometry("1180x740")
        self.root.minsize(1050, 680)
        self.root.configure(bg="#181a1f")

        # Subsystems
        self.pad = GamepadManager()
        self.pad_initialized = self.pad.initialize()
        self.pasco_mgr = MultiPascoManager(num_robots=MAX_ROBOTS)

        # UI Selected Player for Gamepad View (0..4)
        self.active_view_player = 0

        # Robot UI Elements cache
        self.robot_ui_widgets = {}

        self._build_ui()
        self._start_poll_loop()

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Configurar colores ttk oscuros
        style.configure("TCombobox", fieldbackground="#21252b", background="#282c34", foreground="#ffffff", arrowcolor="#50fa7b")
        style.configure("TCheckbutton", background="#21252b", foreground="#abb2bf")

        # 1. Header Bar
        header = tk.Frame(self.root, bg="#21252b", height=55)
        header.pack(fill=tk.X, side=tk.TOP)

        title_lbl = tk.Label(
            header,
            text="🎮 ROBOT PASCO // SISTEMA MULTI-ROBOT & MAPPER 5 PLAYERS",
            font=("Segoe UI", 13, "bold"),
            fg="#50fa7b",
            bg="#21252b"
        )
        title_lbl.pack(side=tk.LEFT, padx=20, pady=12)

        self.global_status_badge = tk.Label(
            header,
            text="● SISTEMA LISTO",
            font=("Segoe UI", 10, "bold"),
            fg="#61afef",
            bg="#21252b",
            padx=15
        )
        self.global_status_badge.pack(side=tk.RIGHT, padx=20)

        # 2. Main Split Container
        main_container = tk.Frame(self.root, bg="#181a1f")
        main_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # Left Column: Gamepad Visualizer (45% width)
        left_col = tk.LabelFrame(
            main_container,
            text=" 🕹️ Visualizador de Mandos en Tiempo Real ",
            font=("Segoe UI", 11, "bold"),
            fg="#8be9fd",
            bg="#21252b",
            padx=10,
            pady=8
        )
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        # Selector de Jugador activo en la vista
        player_sel_frame = tk.Frame(left_col, bg="#21252b")
        player_sel_frame.pack(fill=tk.X, pady=(0, 8))

        tk.Label(player_sel_frame, text="Ver Mando:", font=("Segoe UI", 9, "bold"), fg="#abb2bf", bg="#21252b").pack(side=tk.LEFT, padx=(0, 6))
        self.player_tabs_frame = tk.Frame(player_sel_frame, bg="#21252b")
        self.player_tabs_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.player_tab_btns = []
        for p in range(MAX_ROBOTS):
            btn = tk.Button(
                self.player_tabs_frame,
                text=f"P{p+1}",
                font=("Segoe UI", 9, "bold"),
                bg="#50fa7b" if p == 0 else "#282c34",
                fg="#000000" if p == 0 else "#abb2bf",
                activebackground="#61afef",
                relief=tk.FLAT,
                width=4,
                command=lambda p_idx=p: self._select_view_player(p_idx)
            )
            btn.pack(side=tk.LEFT, padx=3)
            self.player_tab_btns.append(btn)

        self.pad_status_lbl = tk.Label(
            player_sel_frame,
            text="● Conectado",
            font=("Segoe UI", 9, "bold"),
            fg="#50fa7b",
            bg="#21252b"
        )
        self.pad_status_lbl.pack(side=tk.RIGHT, padx=5)

        # Canvas del Mando Ultra-Realista
        self.gamepad_canvas = tk.Canvas(
            left_col,
            bg="#181a1f",
            highlightthickness=1,
            highlightbackground="#3b4252",
            height=370
        )
        self.gamepad_canvas.pack(fill=tk.BOTH, expand=True, pady=4)
        self.renderer = RealisticGamepadCanvas(self.gamepad_canvas)

        # Botón de Configuración Qt
        cfg_btn = tk.Button(
            left_col,
            text="⚙️ Configurar y Calibrar Mandos (Mapper 5 Players)",
            font=("Segoe UI", 10, "bold"),
            bg="#bd93f9",
            fg="#000000",
            activebackground="#ff79c6",
            relief=tk.FLAT,
            height=2,
            command=self._open_qt_config
        )
        cfg_btn.pack(fill=tk.X, pady=(8, 2))

        # Right Column: Multi-Robot Management (55% width)
        right_col = tk.LabelFrame(
            main_container,
            text=" 🤖 Gestión y Telemetría Multi-Robot (5 //control.Node) ",
            font=("Segoe UI", 11, "bold"),
            fg="#50fa7b",
            bg="#21252b",
            padx=10,
            pady=8
        )
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(8, 0))

        # Scrollable container for robots
        robots_scroll_frame = tk.Frame(right_col, bg="#21252b")
        robots_scroll_frame.pack(fill=tk.BOTH, expand=True)

        for slot_idx in range(MAX_ROBOTS):
            self._create_robot_slot_card(robots_scroll_frame, slot_idx)

        # Emergency & Global Action Bar
        action_bar = tk.Frame(right_col, bg="#21252b")
        action_bar.pack(fill=tk.X, pady=(10, 0))

        self.btn_stop_all = tk.Button(
            action_bar,
            text="🛑 PARADA DE EMERGENCIA TOTAL",
            font=("Segoe UI", 11, "bold"),
            bg="#ff5555",
            fg="#ffffff",
            activebackground="#ff6e6e",
            relief=tk.FLAT,
            height=2,
            command=self._emergency_stop
        )
        self.btn_stop_all.pack(fill=tk.X)

    def _create_robot_slot_card(self, parent, slot_idx: int):
        slot = self.pasco_mgr.get_slot(slot_idx)
        card = tk.Frame(parent, bg="#282c34", highlightthickness=1, highlightbackground="#3b4252", padx=8, pady=6)
        card.pack(fill=tk.X, pady=4)

        # Header fila
        top_row = tk.Frame(card, bg="#282c34")
        top_row.pack(fill=tk.X)

        title_lbl = tk.Label(
            top_row,
            text=f"Robot #{slot_idx + 1}",
            font=("Segoe UI", 10, "bold"),
            fg="#61afef",
            bg="#282c34"
        )
        title_lbl.pack(side=tk.LEFT)

        status_lbl = tk.Label(
            top_row,
            text="● Desconectado",
            font=("Segoe UI", 8, "bold"),
            fg="#7b88a1",
            bg="#282c34"
        )
        status_lbl.pack(side=tk.LEFT, padx=10)

        # Enable Checkbox
        enable_var = tk.BooleanVar(value=True)
        def _on_enable_toggle():
            self.pasco_mgr.set_enabled(slot_idx, enable_var.get())
        
        chk = tk.Checkbutton(
            top_row,
            text="Tx Habilitada",
            variable=enable_var,
            font=("Segoe UI", 8),
            bg="#282c34",
            fg="#abb2bf",
            activebackground="#282c34",
            selectcolor="#21252b",
            command=_on_enable_toggle
        )
        chk.pack(side=tk.RIGHT)

        # Controles fila
        ctrl_row = tk.Frame(card, bg="#282c34")
        ctrl_row.pack(fill=tk.X, pady=(4, 2))

        tk.Label(ctrl_row, text="ID BLE:", font=("Segoe UI", 8), fg="#abb2bf", bg="#282c34").pack(side=tk.LEFT)
        id_entry = tk.Entry(ctrl_row, width=8, font=("Consolas", 9, "bold"), bg="#181a1f", fg="#50fa7b", insertbackground="#ffffff", relief=tk.FLAT)
        id_entry.insert(0, slot.pasco_id if slot else f"438-00{slot_idx+1}")
        id_entry.pack(side=tk.LEFT, padx=(4, 10))

        tk.Label(ctrl_row, text="Mando:", font=("Segoe UI", 8), fg="#abb2bf", bg="#282c34").pack(side=tk.LEFT)
        player_combo = ttk.Combobox(ctrl_row, values=[f"Jugador {i+1}" for i in range(MAX_ROBOTS)], width=9, state="readonly")
        player_combo.current(slot_idx)
        def _on_player_change(event):
            self.pasco_mgr.set_player_mapping(slot_idx, player_combo.current())
        player_combo.bind("<<ComboboxSelected>>", _on_player_change)
        player_combo.pack(side=tk.LEFT, padx=(4, 10))

        # Connect / Disconnect button
        conn_btn = tk.Button(
            ctrl_row,
            text="Conectar",
            font=("Segoe UI", 8, "bold"),
            bg="#50fa7b",
            fg="#000000",
            activebackground="#8be9fd",
            relief=tk.FLAT,
            padx=8,
            command=lambda s_idx=slot_idx: self._toggle_robot_connect(s_idx)
        )
        conn_btn.pack(side=tk.RIGHT)

        # Telemetría fila
        telem_row = tk.Frame(card, bg="#282c34")
        telem_row.pack(fill=tk.X, pady=(2, 0))

        mot_lbl = tk.Label(telem_row, text="Motores: A=0 deg/s | B=0 deg/s", font=("Consolas", 8), fg="#6272a4", bg="#282c34")
        mot_lbl.pack(side=tk.LEFT)

        servo_lbl = tk.Label(telem_row, text="Elev: -98° | Pinza: +70°", font=("Consolas", 8), fg="#6272a4", bg="#282c34")
        servo_lbl.pack(side=tk.RIGHT)

        self.robot_ui_widgets[slot_idx] = {
            "status_lbl": status_lbl,
            "id_entry": id_entry,
            "player_combo": player_combo,
            "conn_btn": conn_btn,
            "mot_lbl": mot_lbl,
            "servo_lbl": servo_lbl,
            "enable_var": enable_var
        }

    def _select_view_player(self, player_idx: int):
        self.active_view_player = player_idx
        for i, btn in enumerate(self.player_tab_btns):
            if i == player_idx:
                btn.config(bg="#50fa7b", fg="#000000")
            else:
                btn.config(bg="#282c34", fg="#abb2bf")

    def _toggle_robot_connect(self, slot_idx: int):
        slot = self.pasco_mgr.get_slot(slot_idx)
        w = self.robot_ui_widgets.get(slot_idx)
        if not slot or not w:
            return

        if slot.connected:
            w["conn_btn"].config(text="Desconectando...", state=tk.DISABLED)
            def _on_disconn(s_id):
                self.root.after(0, lambda: self._update_slot_ui_after_conn(s_id))
            self.pasco_mgr.disconnect_async(slot_idx, _on_disconn)
        else:
            pasco_id = w["id_entry"].get().strip()
            self.pasco_mgr.set_pasco_id(slot_idx, pasco_id)
            w["conn_btn"].config(text="Conectando...", state=tk.DISABLED, bg="#ffb86c")
            w["status_lbl"].config(text="● Conectando...", fg="#ffb86c")
            def _on_conn(s_id, success, msg):
                self.root.after(0, lambda: self._update_slot_ui_after_conn(s_id))
            self.pasco_mgr.connect_async(slot_idx, _on_conn)

    def _update_slot_ui_after_conn(self, slot_idx: int):
        slot = self.pasco_mgr.get_slot(slot_idx)
        w = self.robot_ui_widgets.get(slot_idx)
        if not slot or not w:
            return

        w["conn_btn"].config(state=tk.NORMAL)
        if slot.connected:
            w["conn_btn"].config(text="Desconectar", bg="#ff5555", fg="#ffffff")
            w["status_lbl"].config(text=f"● Conectado ({slot.pasco_id})", fg="#50fa7b")
        else:
            w["conn_btn"].config(text="Conectar", bg="#50fa7b", fg="#000000")
            w["status_lbl"].config(text=f"● {slot.status_msg}", fg="#ff5555" if "Error" in slot.status_msg else "#7b88a1")

    def _open_qt_config(self):
        proc = GamepadManager.launch_config_process("multi")
        import threading
        def _wait_and_reload():
            if proc:
                proc.wait()
            self.root.after(0, self.pad.reload)
        threading.Thread(target=_wait_and_reload, daemon=True).start()

    def _emergency_stop(self):
        self.pasco_mgr.emergency_stop_all()

    def _start_poll_loop(self):
        self._poll_step()

    def _poll_step(self):
        try:
            # 1. Actualizar estado del GamepadManager
            self.pad.update()

            self._frame_count = getattr(self, "_frame_count", 0) + 1
            if self._frame_count % 30 == 0:
                self.pad.reload()

            # 2. Procesar cada uno de los 5 Jugadores
            player_states = {}
            for p in range(MAX_ROBOTS):
                state = self.pad.get_state(p)
                player_states[p] = state

            # 3. Enrutar y transmitir a los robots asignados
            for slot_idx in range(MAX_ROBOTS):
                slot = self.pasco_mgr.get_slot(slot_idx)
                if not slot:
                    continue

                assigned_player = slot.player_idx
                p_state = player_states.get(assigned_player, GamepadState())

                if slot.connected and slot.enabled and p_state.is_connected:
                    ls_y = p_state.left_stick.y if p_state.left_stick else 0.0
                    rs_x = p_state.right_stick.x if p_state.right_stick else 0.0

                    forward = normalize_axis(ls_y, DEADZONE, MAX_THRESHOLD)
                    turn = normalize_axis(rs_x, DEADZONE, MAX_THRESHOLD)

                    if forward != 0.0 or turn != 0.0:
                        vel_a, vel_b = calculate_split_stick_drive(forward, turn, MAX_SPEED)
                    else:
                        vel_a = 0
                        vel_b = 0

                    self.pasco_mgr.send_drive(slot_idx, vel_a, vel_b, ACCEL)

                    # Servos
                    rt_val = p_state.right_trigger.value if p_state.right_trigger else 0.0
                    lt_val = p_state.left_trigger.value if p_state.left_trigger else 0.0
                    rt_pressed = p_state.is_button_pressed(Button.ZR) or (rt_val > 0.2)
                    lt_pressed = p_state.is_button_pressed(Button.ZL) or (lt_val > 0.2)
                    rb_pressed = p_state.is_button_pressed(Button.R)
                    lb_pressed = p_state.is_button_pressed(Button.L)

                    step_lift = SERVO_STEP if not INVERT_LIFT else -SERVO_STEP
                    if rt_pressed:
                        slot.lift_angle = min(LIFT_MAX, max(LIFT_MIN, slot.lift_angle + step_lift))
                    elif lt_pressed:
                        slot.lift_angle = min(LIFT_MAX, max(LIFT_MIN, slot.lift_angle - step_lift))

                    step_pinza = SERVO_STEP if not INVERT_PINZA else -SERVO_STEP
                    if rb_pressed:
                        slot.pinza_angle = min(PINZA_MAX, max(PINZA_MIN, slot.pinza_angle + step_pinza))
                    elif lb_pressed:
                        slot.pinza_angle = min(PINZA_MAX, max(PINZA_MIN, slot.pinza_angle - step_pinza))

                    self.pasco_mgr.send_servos(slot_idx, slot.lift_angle, slot.pinza_angle, SWAP_SERVO_PORTS)

                # Actualizar telemetría en la UI del robot
                w = self.robot_ui_widgets.get(slot_idx)
                if w:
                    if slot.connected:
                        w["mot_lbl"].config(text=f"Motores: A={slot.last_vel_a:+d} | B={slot.last_vel_b:+d} deg/s", fg="#50fa7b" if slot.is_moving else "#abb2bf")
                        w["servo_lbl"].config(text=f"Elev: {int(slot.lift_angle):+d}° | Pinza: {int(slot.pinza_angle):+d}°", fg="#8be9fd")
                    else:
                        w["mot_lbl"].config(text="Motores: A=0 | B=0 deg/s", fg="#6272a4")
                        w["servo_lbl"].config(text="Elev: -- | Pinza: --", fg="#6272a4")

            # 4. Renderizar el mando seleccionado actualmente
            active_p_state = player_states.get(self.active_view_player, GamepadState())
            cw = self.gamepad_canvas.winfo_width()
            ch = self.gamepad_canvas.winfo_height()
            if cw > 50 and ch > 50:
                self.renderer.render(active_p_state, cw, ch)

            # 5. Actualizar indicadores de conexión de mandos en la barra
            conn_count = 0
            for p in range(MAX_ROBOTS):
                is_p_conn = player_states[p].is_connected
                if is_p_conn:
                    conn_count += 1
                dot = "●" if is_p_conn else ""
                bg_col = "#50fa7b" if p == self.active_view_player else ("#282c34" if is_p_conn else "#1e222b")
                fg_col = "#000000" if p == self.active_view_player else ("#50fa7b" if is_p_conn else "#6272a4")
                self.player_tab_btns[p].config(text=f"P{p+1} {dot}".strip(), bg=bg_col, fg=fg_col)
                if p == self.active_view_player:
                    self.pad_status_lbl.config(
                        text=f"Mando Jugador {p+1}: {'CONECTADO' if is_p_conn else 'DESCONECTADO'}",
                        fg="#50fa7b" if is_p_conn else "#ff5555"
                    )
                dot = "●" if is_p_conn else "○"
                col = "#50fa7b" if is_p_conn else "#4c566a"
                if p == self.active_view_player:
                    self.pad_status_lbl.config(
                        text=f"Mando Jugador {p+1}: {'CONECTADO' if is_p_conn else 'DESCONECTADO'}",
                        fg="#50fa7b" if is_p_conn else "#ffb86c"
                    )

        except Exception as e:
            print(f"Error en _poll_step: {e}")
        finally:
            self.root.after(16, self._poll_step)

def main():
    root = tk.Tk()
    app = VisualGamepadApp(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.pasco_mgr.disconnect_all(), app.pad.shutdown(), root.destroy()))
    root.mainloop()

if __name__ == "__main__":
    main()
