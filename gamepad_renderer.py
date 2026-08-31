# SPDX-License-Identifier: MIT
"""
Realistic Gamepad Renderer for Python Tkinter.
Implements the topological model of the Nintendo Switch Pro Controller / Asymmetric Gamepad
with decoupled DTO ingestion, dashed circle gates, and trigonometric radial clamping.
Based on the graphical architecture research for real-time gamepad overlays.
"""

import math
import tkinter as tk
from typing import Optional, Dict, Any
from gamepad_mapper import GamepadState, Button, StickState, TriggerState

class RealisticGamepadCanvas:
    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.r_max = 28.0  # Max radial travel for analog sticks in pixels
        self.colors = {
            "bg_chassis": "#1e222b",
            "chassis_outline": "#3b4252",
            "grip_left": "#181b22",
            "grip_right": "#181b22",
            "plate_center": "#242933",
            "accent": "#434c5e",
            "btn_inactive": "#2e3440",
            "btn_inactive_text": "#7b88a1",
            "btn_active_text": "#ffffff",
            "btn_outline": "#4c566a",
            "stick_gate_dash": "#4c566a",
            "stick_cap_base": "#14171d",
            "stick_cap_top": "#2a303c",
            "stick_cap_highlight": "#384152",
            "stick_dot": "#50fa7b",
            "stick_dot_glow": "#284a32",
            "a_active": "#50fa7b",
            "b_active": "#ff5555",
            "x_active": "#8be9fd",
            "y_active": "#ffb86c",
            "shoulder_active": "#8be9fd",
            "trigger_bg": "#181b22",
            "trigger_fill": "#ff79c6",
            "text_muted": "#6272a4",
            "text_active": "#f8f8f2",
        }

    def _radial_clamp(self, x: float, y: float) -> tuple[float, float, float]:
        """
        Trigonometric radial clamping as specified in the mathematical model:
        H = sqrt(X^2 + Y^2)
        If H > 1.0 -> polar conversion theta = atan2(Y, X) -> (Rmax * cos(theta), -Rmax * sin(theta))
        """
        h = math.sqrt(x * x + y * y)
        if h > 1.0:
            theta = math.atan2(y, x)
            clamped_x = math.cos(theta)
            clamped_y = math.sin(theta)
            magnitude = 1.0
        else:
            clamped_x = x
            clamped_y = y
            magnitude = h
        return clamped_x, clamped_y, magnitude

    def render(self, state: GamepadState, width: int = 420, height: int = 340):
        c = self.canvas
        c.delete("all")

        cx = width / 2.0
        cy = height / 2.0 + 8

        # --- 1. DIBUJAR GATILLOS Y BOTONES DE HOMBRO (PARTE SUPERIOR) ---
        # ZL (Gatillo izquierdo)
        zl_val = state.left_trigger.value if state.left_trigger else 0.0
        zl_pressed = state.is_button_pressed(Button.ZL) or (zl_val > 0.2)
        self._draw_trigger_box(cx - 140, cy - 130, 48, 22, "ZL", zl_val, zl_pressed)

        # ZR (Gatillo derecho)
        zr_val = state.right_trigger.value if state.right_trigger else 0.0
        zr_pressed = state.is_button_pressed(Button.ZR) or (zr_val > 0.2)
        self._draw_trigger_box(cx + 92, cy - 130, 48, 22, "ZR", zr_val, zr_pressed)

        # L (Hombro izquierdo)
        l_pressed = state.is_button_pressed(Button.L)
        self._draw_shoulder_arc(cx - 120, cy - 102, 60, 16, "L", l_pressed)

        # R (Hombro derecho)
        r_pressed = state.is_button_pressed(Button.R)
        self._draw_shoulder_arc(cx + 60, cy - 102, 60, 16, "R", r_pressed)

        # --- 2. DIBUJAR CHASIS ERGONÓMICO ASIMÉTRICO (SWITCH PRO STYLE) ---
        self._draw_controller_chassis(cx, cy)

        # --- 3. BOTONES DEL SISTEMA CENTRALES (-, +, HOME, CAPTURE) ---
        minus_pressed = state.is_button_pressed(Button.MINUS)
        plus_pressed = state.is_button_pressed(Button.PLUS)
        home_pressed = state.is_button_pressed(Button.HOME)
        cap_pressed = state.is_button_pressed(Button.SCREENSHOT)

        # Menos (-)
        self._draw_pill_button(cx - 38, cy - 54, 18, 10, "-", minus_pressed)
        # Más (+)
        self._draw_pill_button(cx + 20, cy - 54, 18, 10, "+", plus_pressed)
        # Captura ([o])
        self._draw_square_button(cx - 26, cy - 24, 14, "⧈", cap_pressed)
        # Home (⌂)
        self._draw_circle_system_button(cx + 12, cy - 24, 14, "⌂", home_pressed)

        # --- 4. JOYSTICK ANALÓGICO PRIMARIO (IZQUIERDO - SUPERIOR) ---
        ls_x = state.left_stick.x if state.left_stick else 0.0
        ls_y = state.left_stick.y if state.left_stick else 0.0
        ls_click = state.is_button_pressed(Button.LSTICK)
        self._draw_analog_gate_and_stick(cx - 86, cy - 32, ls_x, ls_y, ls_click, "Stick L")

        # --- 5. D-PAD CRUCETA ORTOGONAL (IZQUIERDO - INFERIOR) ---
        dpad_up = state.is_button_pressed(Button.DUP)
        dpad_down = state.is_button_pressed(Button.DDOWN)
        dpad_left = state.is_button_pressed(Button.DLEFT)
        dpad_right = state.is_button_pressed(Button.DRIGHT)
        self._draw_dpad(cx - 86, cy + 48, dpad_up, dpad_down, dpad_left, dpad_right)

        # --- 6. DIAMANTE DE BOTONES DE ACCIÓN (DERECHO - SUPERIOR) ---
        btn_a = state.is_button_pressed(Button.A)
        btn_b = state.is_button_pressed(Button.B)
        btn_x = state.is_button_pressed(Button.X)
        btn_y = state.is_button_pressed(Button.Y)
        self._draw_action_diamond(cx + 86, cy - 32, btn_a, btn_b, btn_x, btn_y)

        # --- 7. JOYSTICK ANALÓGICO SECUNDARIO (DERECHO - INFERIOR) ---
        rs_x = state.right_stick.x if state.right_stick else 0.0
        rs_y = state.right_stick.y if state.right_stick else 0.0
        rs_click = state.is_button_pressed(Button.RSTICK)
        self._draw_analog_gate_and_stick(cx + 86, cy + 48, rs_x, rs_y, rs_click, "Stick R")

    def _draw_controller_chassis(self, cx: float, cy: float):
        c = self.canvas
        # Silueta principal estilizada del mando
        points = [
            cx - 130, cy - 90,   # Hombro sup izq
            cx - 60,  cy - 92,   # Centro sup izq
            cx,       cy - 85,   # Centro sup
            cx + 60,  cy - 92,   # Centro sup der
            cx + 130, cy - 90,   # Hombro sup der
            cx + 165, cy - 40,   # Borde ext der
            cx + 175, cy + 40,   # Empuñadura der
            cx + 155, cy + 115,  # Punta empuñadura der
            cx + 115, cy + 120,  # Curva base der
            cx + 65,  cy + 60,   # Entrepierna der
            cx,       cy + 55,   # Centro inf
            cx - 65,  cy + 60,   # Entrepierna izq
            cx - 115, cy + 120,  # Curva base izq
            cx - 155, cy + 115,  # Punta empuñadura izq
            cx - 175, cy + 40,   # Empuñadura izq
            cx - 165, cy - 40,   # Borde ext izq
        ]

        # Sombra y contorno del cuerpo
        c.create_polygon(points, fill=self.colors["bg_chassis"], outline=self.colors["chassis_outline"], width=3, smooth=True)

        # Placa central decorativa
        plate_pts = [
            cx - 50, cy - 70,
            cx + 50, cy - 70,
            cx + 60, cy + 20,
            cx,      cy + 45,
            cx - 60, cy + 20
        ]
        c.create_polygon(plate_pts, fill=self.colors["plate_center"], outline=self.colors["accent"], width=1, smooth=True)

    def _draw_trigger_box(self, x: float, y: float, w: float, h: float, label: str, val: float, pressed: bool):
        c = self.canvas
        # Fondo caja
        c.create_rectangle(x, y, x + w, y + h, fill=self.colors["trigger_bg"], outline=self.colors["btn_outline"], width=1)
        # Barra de progreso analógica (0..100%)
        fill_w = w * max(0.0, min(1.0, val))
        fill_col = self.colors["trigger_fill"] if pressed else self.colors["accent"]
        if fill_w > 0:
            c.create_rectangle(x + 1, y + 1, x + fill_w - 1, y + h - 1, fill=fill_col, width=0)
        # Texto
        txt_col = "#ffffff" if pressed else self.colors["btn_inactive_text"]
        c.create_text(x + w / 2.0, y + h / 2.0, text=f"{label} {int(val * 100)}%", fill=txt_col, font=("Segoe UI", 8, "bold"))

    def _draw_shoulder_arc(self, x: float, y: float, w: float, h: float, label: str, pressed: bool):
        c = self.canvas
        fill_col = self.colors["shoulder_active"] if pressed else self.colors["btn_inactive"]
        txt_col = "#000000" if pressed else self.colors["btn_inactive_text"]
        outline = self.colors["shoulder_active"] if pressed else self.colors["btn_outline"]
        
        c.create_rectangle(x, y, x + w, y + h, fill=fill_col, outline=outline, width=1.5)
        c.create_text(x + w / 2.0, y + h / 2.0, text=label, fill=txt_col, font=("Segoe UI", 9, "bold"))

    def _draw_pill_button(self, x: float, y: float, w: float, h: float, label: str, pressed: bool):
        c = self.canvas
        fill = "#50fa7b" if pressed else self.colors["btn_inactive"]
        txt_col = "#000000" if pressed else self.colors["btn_inactive_text"]
        c.create_rectangle(x, y, x + w, y + h, fill=fill, outline=self.colors["btn_outline"], width=1)
        c.create_text(x + w / 2.0, y + h / 2.0 - 1, text=label, fill=txt_col, font=("Segoe UI", 10, "bold"))

    def _draw_square_button(self, x: float, y: float, size: float, label: str, pressed: bool):
        c = self.canvas
        fill = "#8be9fd" if pressed else self.colors["btn_inactive"]
        txt_col = "#000000" if pressed else self.colors["btn_inactive_text"]
        c.create_rectangle(x, y, x + size, y + size, fill=fill, outline=self.colors["btn_outline"], width=1)
        c.create_text(x + size / 2.0, y + size / 2.0, text=label, fill=txt_col, font=("Segoe UI", 8))

    def _draw_circle_system_button(self, x: float, y: float, size: float, label: str, pressed: bool):
        c = self.canvas
        fill = "#ff79c6" if pressed else self.colors["btn_inactive"]
        txt_col = "#000000" if pressed else self.colors["btn_inactive_text"]
        c.create_oval(x, y, x + size, y + size, fill=fill, outline=self.colors["btn_outline"], width=1)
        c.create_text(x + size / 2.0, y + size / 2.0, text=label, fill=txt_col, font=("Segoe UI", 8, "bold"))

    def _draw_dpad(self, cx: float, cy: float, up: bool, down: bool, left: bool, right: bool):
        c = self.canvas
        bw = 14
        bh = 18

        # Base D-Pad
        c.create_oval(cx - 32, cy - 32, cx + 32, cy + 32, fill="#181b22", outline="#2e3440", width=1)

        # Arriba
        col_up = "#50fa7b" if up else self.colors["btn_inactive"]
        c.create_rectangle(cx - bw/2, cy - 28, cx + bw/2, cy - 10, fill=col_up, outline=self.colors["btn_outline"])
        c.create_text(cx, cy - 19, text="▲", fill="#ffffff" if up else self.colors["btn_inactive_text"], font=("Segoe UI", 7))

        # Abajo
        col_dn = "#50fa7b" if down else self.colors["btn_inactive"]
        c.create_rectangle(cx - bw/2, cy + 10, cx + bw/2, cy + 28, fill=col_dn, outline=self.colors["btn_outline"])
        c.create_text(cx, cy + 19, text="▼", fill="#ffffff" if down else self.colors["btn_inactive_text"], font=("Segoe UI", 7))

        # Izquierda
        col_lt = "#50fa7b" if left else self.colors["btn_inactive"]
        c.create_rectangle(cx - 28, cy - bw/2, cx - 10, cy + bw/2, fill=col_lt, outline=self.colors["btn_outline"])
        c.create_text(cx - 19, cy, text="◀", fill="#ffffff" if left else self.colors["btn_inactive_text"], font=("Segoe UI", 7))

        # Derecha
        col_rt = "#50fa7b" if right else self.colors["btn_inactive"]
        c.create_rectangle(cx + 10, cy - bw/2, cx + 28, cy + bw/2, fill=col_rt, outline=self.colors["btn_outline"])
        c.create_text(cx + 19, cy, text="▶", fill="#ffffff" if right else self.colors["btn_inactive_text"], font=("Segoe UI", 7))

        # Centro D-Pad
        c.create_rectangle(cx - 10, cy - 10, cx + 10, cy + 10, fill="#242933", outline="", width=0)

    def _draw_action_diamond(self, cx: float, cy: float, a: bool, b: bool, x: bool, y: bool):
        c = self.canvas
        r = 13.0
        dist = 23.0

        # Base diamante
        c.create_oval(cx - 36, cy - 36, cx + 36, cy + 36, fill="#181b22", outline="#2e3440", width=1)

        # Botón A (Derecha)
        col_a = self.colors["a_active"] if a else self.colors["btn_inactive"]
        txt_a = "#000000" if a else self.colors["btn_inactive_text"]
        c.create_oval(cx + dist - r, cy - r, cx + dist + r, cy + r, fill=col_a, outline=self.colors["btn_outline"], width=1.5)
        c.create_text(cx + dist, cy, text="A", fill=txt_a, font=("Segoe UI", 10, "bold"))

        # Botón B (Abajo)
        col_b = self.colors["b_active"] if b else self.colors["btn_inactive"]
        txt_b = "#ffffff" if b else self.colors["btn_inactive_text"]
        c.create_oval(cx - r, cy + dist - r, cx + r, cy + dist + r, fill=col_b, outline=self.colors["btn_outline"], width=1.5)
        c.create_text(cx, cy + dist, text="B", fill=txt_b, font=("Segoe UI", 10, "bold"))

        # Botón X (Izquierda / Arriba según layout Xbox vs Switch)
        col_x = self.colors["x_active"] if x else self.colors["btn_inactive"]
        txt_x = "#000000" if x else self.colors["btn_inactive_text"]
        c.create_oval(cx - dist - r, cy - r, cx - dist + r, cy + r, fill=col_x, outline=self.colors["btn_outline"], width=1.5)
        c.create_text(cx - dist, cy, text="X", fill=txt_x, font=("Segoe UI", 10, "bold"))

        # Botón Y (Arriba)
        col_y = self.colors["y_active"] if y else self.colors["btn_inactive"]
        txt_y = "#000000" if y else self.colors["btn_inactive_text"]
        c.create_oval(cx - r, cy - dist - r, cx + r, cy - dist + r, fill=col_y, outline=self.colors["btn_outline"], width=1.5)
        c.create_text(cx, cy - dist, text="Y", fill=txt_y, font=("Segoe UI", 10, "bold"))

    def _draw_analog_gate_and_stick(self, cx: float, cy: float, raw_x: float, raw_y: float, is_clicked: bool, label: str):
        c = self.canvas

        # 1. Aplicar Radial Clamping matemático estricto
        clamped_x, clamped_y, magnitude = self._radial_clamp(raw_x, raw_y)

        # 2. Compuerta circular punteada (Dashed Circle Gate)
        gate_radius = self.r_max + 14.0
        c.create_oval(cx - gate_radius, cy - gate_radius, cx + gate_radius, cy + gate_radius,
                      fill="#12151a", outline=self.colors["stick_gate_dash"], width=1.5, dash=(4, 4))

        # Ejes de cruz de referencia tenues
        c.create_line(cx - gate_radius, cy, cx + gate_radius, cy, fill="#232833", width=1)
        c.create_line(cx, cy - gate_radius, cx, cy + gate_radius, fill="#232833", width=1)

        # 3. Desplazamiento cartesiano en píxeles (Y invertido para pantalla)
        stick_px_x = cx + (clamped_x * self.r_max)
        stick_px_y = cy - (clamped_y * self.r_max)

        # 4. Casquete físico del pulgar (Thumbstick cap con sombra e inclinación)
        cap_r = 18.0
        cap_color = "#323a48" if is_clicked else self.colors["stick_cap_top"]
        cap_outline = "#50fa7b" if is_clicked else self.colors["stick_cap_highlight"]

        # Sombra del casquete
        c.create_oval(stick_px_x - cap_r + 2, stick_px_y - cap_r + 3,
                      stick_px_x + cap_r + 2, stick_px_y + cap_r + 3,
                      fill="#0d0e12", outline="", width=0)
        # Casquete base
        c.create_oval(stick_px_x - cap_r, stick_px_y - cap_r,
                      stick_px_x + cap_r, stick_px_y + cap_r,
                      fill=cap_color, outline=cap_outline, width=1.5)
        # Anillo interno texturizado
        c.create_oval(stick_px_x - (cap_r - 6), stick_px_y - (cap_r - 6),
                      stick_px_x + (cap_r - 6), stick_px_y + (cap_r - 6),
                      fill="", outline="#1e232c", width=1.5)

        # 5. Punto referencial cinestésico verde neón central
        dot_r = 4.5
        c.create_oval(stick_px_x - dot_r, stick_px_y - dot_r,
                      stick_px_x + dot_r, stick_px_y + dot_r,
                      fill=self.colors["stick_dot"], outline="#ffffff", width=1)

        # 6. Coordenadas de telemetría numérica
        c.create_text(cx, cy + gate_radius + 12,
                      text=f"{label}: ({raw_x:+.2f}, {raw_y:+.2f})",
                      fill=self.colors["text_active"] if magnitude > 0.05 else self.colors["text_muted"],
                      font=("Consolas", 8, "bold"))
