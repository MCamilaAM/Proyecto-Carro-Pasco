# SPDX-License-Identifier: MIT
"""
GamepadMapper Python ctypes wrapper.
Provides clean Pythonic access to GamepadMapperLib (C++20 Gamepad Subsystem).
"""

import os
import sys
import ctypes
import subprocess
from enum import IntEnum
from dataclasses import dataclass
from typing import Optional, Tuple, List


# --- CONFIGURAR RUTAS DE PLUGINS QT ---
current_dir = os.path.dirname(os.path.abspath(__file__))
qt_plugin_dirs = [
    os.path.join(current_dir, "platforms"),
    r"C:\Qt\6.8.2\msvc2022_64\plugins\platforms",
]
for p in qt_plugin_dirs:
    if os.path.exists(p):
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = p
        break

if os.path.exists(r"C:\Qt\6.8.2\msvc2022_64\plugins"):
    os.environ["QT_PLUGIN_PATH"] = r"C:\Qt\6.8.2\msvc2022_64\plugins"


# --- ENUMS ---

class Button(IntEnum):
    A = 0
    B = 1
    X = 2
    Y = 3
    LSTICK = 4
    RSTICK = 5
    L = 6
    R = 7
    ZL = 8
    ZR = 9
    PLUS = 10
    MINUS = 11
    DLEFT = 12
    DUP = 13
    DRIGHT = 14
    DDOWN = 15
    SL_LEFT = 16
    SR_LEFT = 17
    HOME = 18
    SCREENSHOT = 19
    SL_RIGHT = 20
    SR_RIGHT = 21


class Stick(IntEnum):
    LEFT = 0
    RIGHT = 1


class Trigger(IntEnum):
    LEFT = 0
    RIGHT = 1


class ControllerType(IntEnum):
    PRO_CONTROLLER = 0
    DUAL_JOYCON = 1
    LEFT_JOYCON = 2
    RIGHT_JOYCON = 3
    HANDHELD = 4
    GAMECUBE = 5


# --- CTYPES STRUCTURES ---

class _CStickState(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("x", ctypes.c_float),
        ("y", ctypes.c_float),
    ]


class _CTriggerState(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("value", ctypes.c_float),
        ("pressed", ctypes.c_bool),
    ]


class _CMotionState(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("accel_x", ctypes.c_float),
        ("accel_y", ctypes.c_float),
        ("accel_z", ctypes.c_float),
        ("gyro_x", ctypes.c_float),
        ("gyro_y", ctypes.c_float),
        ("gyro_z", ctypes.c_float),
        ("quat_w", ctypes.c_float),
        ("quat_x", ctypes.c_float),
        ("quat_y", ctypes.c_float),
        ("quat_z", ctypes.c_float),
    ]


class _CFullState(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("is_connected", ctypes.c_bool),
        ("type", ctypes.c_uint32),
        ("buttons", ctypes.c_uint32),
        ("left_stick", _CStickState),
        ("right_stick", _CStickState),
        ("left_trigger", _CTriggerState),
        ("right_trigger", _CTriggerState),
        ("motion", _CMotionState),
        ("battery_percentage", ctypes.c_uint8),
        ("is_charging", ctypes.c_bool),
    ]


# --- PYTHON DATA CLASSES ---

@dataclass
class StickState:
    x: float = 0.0  # -1.0 (left) to 1.0 (right)
    y: float = 0.0  # -1.0 (down) to 1.0 (up)


@dataclass
class TriggerState:
    value: float = 0.0  # 0.0 to 1.0
    pressed: bool = False


@dataclass
class MotionState:
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 0.0
    gyro_x: float = 0.0
    gyro_y: float = 0.0
    gyro_z: float = 0.0
    quat_w: float = 1.0
    quat_x: float = 0.0
    quat_y: float = 0.0
    quat_z: float = 0.0


@dataclass
class GamepadState:
    is_connected: bool = False
    type: ControllerType = ControllerType.PRO_CONTROLLER
    buttons: int = 0
    left_stick: StickState = None
    right_stick: StickState = None
    left_trigger: TriggerState = None
    right_trigger: TriggerState = None
    motion: MotionState = None
    battery_percentage: int = 100
    is_charging: bool = False

    def is_button_pressed(self, button: Button | int) -> bool:
        return bool(self.buttons & (1 << int(button)))


# --- DLL LOADER ---

def _load_gamepad_dll():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    possible_dll_paths = [
        os.path.join(root_dir, "GamepadMapper.dll"),
        os.path.join(root_dir, "GamepadMapperLib", "build", "GamepadMapper.dll"),
        os.path.join(root_dir, "GamepadMapperLib", "build", "Release", "GamepadMapper.dll"),
    ]

    # Additional directories for dependencies (Qt6, SDL3)
    extra_dirs = [
        r"C:\Qt\6.8.2\msvc2022_64\bin",
        os.path.join(root_dir, "GamepadMapperLib", "build", "_deps", "sdl3-build"),
        os.path.join(root_dir, "GamepadMapperLib", "build"),
        root_dir,
    ]

    dll_dirs = []
    if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
        for d in extra_dirs:
            if os.path.exists(d):
                try:
                    dll_dirs.append(os.add_dll_directory(d))
                except Exception:
                    pass

    target_dll = None
    for p in possible_dll_paths:
        if os.path.exists(p):
            target_dll = p
            break

    if not target_dll:
        raise FileNotFoundError(
            f"No se encontró GamepadMapper.dll en las rutas buscadas:\n" +
            "\n".join(possible_dll_paths) +
            "\nAsegúrate de haber ejecutado build.bat en GamepadMapperLib."
        )

    return ctypes.CDLL(target_dll)


# --- MAIN MANAGER CLASS ---

class GamepadManager:
    _instance = None
    _dll = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GamepadManager, cls).__new__(cls)
            cls._instance._init_dll()
        return cls._instance

    def _init_dll(self):
        self._dll = _load_gamepad_dll()

        # Define argtypes and restypes
        self._dll.gamepad_initialize.argtypes = []
        self._dll.gamepad_initialize.restype = ctypes.c_bool

        self._dll.gamepad_shutdown.argtypes = []
        self._dll.gamepad_shutdown.restype = None

        self._dll.gamepad_update.argtypes = []
        self._dll.gamepad_update.restype = None

        self._dll.gamepad_reload.argtypes = []
        self._dll.gamepad_reload.restype = None

        self._dll.gamepad_is_connected.argtypes = [ctypes.c_int]
        self._dll.gamepad_is_connected.restype = ctypes.c_bool

        self._dll.gamepad_get_type.argtypes = [ctypes.c_int]
        self._dll.gamepad_get_type.restype = ctypes.c_int

        self._dll.gamepad_is_button_pressed.argtypes = [ctypes.c_int, ctypes.c_int]
        self._dll.gamepad_is_button_pressed.restype = ctypes.c_bool

        self._dll.gamepad_get_stick.argtypes = [
            ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float)
        ]
        self._dll.gamepad_get_stick.restype = ctypes.c_bool

        self._dll.gamepad_get_trigger.argtypes = [
            ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_bool)
        ]
        self._dll.gamepad_get_trigger.restype = ctypes.c_bool

        self._dll.gamepad_get_motion.argtypes = [
            ctypes.c_int, ctypes.POINTER(_CMotionState)
        ]
        self._dll.gamepad_get_motion.restype = ctypes.c_bool

        self._dll.gamepad_get_state.argtypes = [
            ctypes.c_int, ctypes.POINTER(_CFullState)
        ]
        self._dll.gamepad_get_state.restype = ctypes.c_bool

        self._dll.gamepad_set_vibration.argtypes = [
            ctypes.c_int, ctypes.c_float, ctypes.c_float
        ]
        self._dll.gamepad_set_vibration.restype = None

        self._dll.gamepad_save_profile.argtypes = [ctypes.c_int, ctypes.c_char_p]
        self._dll.gamepad_save_profile.restype = ctypes.c_bool

        self._dll.gamepad_load_profile.argtypes = [ctypes.c_int, ctypes.c_char_p]
        self._dll.gamepad_load_profile.restype = ctypes.c_bool

        self._dll.gamepad_show_config_dialog.argtypes = [ctypes.c_void_p]
        self._dll.gamepad_show_config_dialog.restype = ctypes.c_bool

        self._dll.gamepad_show_single_config_dialog.argtypes = [ctypes.c_void_p]
        self._dll.gamepad_show_single_config_dialog.restype = ctypes.c_bool

        self._dll.gamepad_show_single_switch_config_dialog.argtypes = [ctypes.c_void_p]
        self._dll.gamepad_show_single_switch_config_dialog.restype = ctypes.c_bool

    def initialize(self) -> bool:
        """Inicializa los controladores de entrada y hardware (SDL3/Joy-Cons)."""
        return bool(self._dll.gamepad_initialize())

    def shutdown(self):
        """Libera todos los recursos y controladores."""
        self._dll.gamepad_shutdown()

    def update(self):
        """Procesa eventos de hardware y actualiza el estado de los mandos. Llamar en cada iteración."""
        self._dll.gamepad_update()

    def reload(self):
        """Recarga todas las configuraciones guardadas en disco y actualiza los dispositivos inmediatamente."""
        self._dll.gamepad_reload()

    def is_connected(self, player: int = 0) -> bool:
        """Verifica si el jugador (0..7) tiene un mando conectado."""
        return bool(self._dll.gamepad_is_connected(player))

    def get_type(self, player: int = 0) -> ControllerType:
        """Obtiene el tipo de controlador del jugador (0..7)."""
        return ControllerType(self._dll.gamepad_get_type(player))

    def is_button_pressed(self, player: int, button: Button | int) -> bool:
        """Verifica si un botón específico está presionado."""
        return bool(self._dll.gamepad_is_button_pressed(player, int(button)))

    def get_stick(self, player: int, stick: Stick | int) -> StickState:
        """Obtiene la posición (-1.0 a 1.0) del stick izquierdo o derecho."""
        x = ctypes.c_float()
        y = ctypes.c_float()
        success = self._dll.gamepad_get_stick(player, int(stick), ctypes.byref(x), ctypes.byref(y))
        if success:
            return StickState(x=x.value, y=y.value)
        return StickState()

    def get_trigger(self, player: int, trigger: Trigger | int) -> TriggerState:
        """Obtiene el estado de un gatillo analógico (0.0 a 1.0 y booleano)."""
        val = ctypes.c_float()
        pressed = ctypes.c_bool()
        success = self._dll.gamepad_get_trigger(player, int(trigger), ctypes.byref(val), ctypes.byref(pressed))
        if success:
            return TriggerState(value=val.value, pressed=pressed.value)
        return TriggerState()

    def get_motion(self, player: int = 0) -> MotionState:
        """Obtiene datos del sensor de movimiento (acelerómetro/giroscopio)."""
        m = _CMotionState()
        if self._dll.gamepad_get_motion(player, ctypes.byref(m)):
            return MotionState(
                accel_x=m.accel_x, accel_y=m.accel_y, accel_z=m.accel_z,
                gyro_x=m.gyro_x, gyro_y=m.gyro_y, gyro_z=m.gyro_z,
                quat_w=m.quat_w, quat_x=m.quat_x, quat_y=m.quat_y, quat_z=m.quat_z
            )
        return MotionState()

    def get_state(self, player: int = 0) -> GamepadState:
        """Obtiene una captura completa de todos los botones, palancas, gatillos y batería."""
        s = _CFullState()
        if self._dll.gamepad_get_state(player, ctypes.byref(s)):
            return GamepadState(
                is_connected=s.is_connected,
                type=ControllerType(s.type),
                buttons=s.buttons,
                left_stick=StickState(x=s.left_stick.x, y=s.left_stick.y),
                right_stick=StickState(x=s.right_stick.x, y=s.right_stick.y),
                left_trigger=TriggerState(value=s.left_trigger.value, pressed=s.left_trigger.pressed),
                right_trigger=TriggerState(value=s.right_trigger.value, pressed=s.right_trigger.pressed),
                motion=MotionState(
                    accel_x=s.motion.accel_x, accel_y=s.motion.accel_y, accel_z=s.motion.accel_z,
                    gyro_x=s.motion.gyro_x, gyro_y=s.motion.gyro_y, gyro_z=s.motion.gyro_z,
                    quat_w=s.motion.quat_w, quat_x=s.motion.quat_x, quat_y=s.motion.quat_y,
                    quat_z=s.motion.quat_z
                ),
                battery_percentage=s.battery_percentage,
                is_charging=s.is_charging
            )
        return GamepadState()

    def set_vibration(self, player: int = 0, low_frequency: float = 0.0, high_frequency: float = 0.0):
        """Activa la vibración/rumble en el mando (amplitudes de 0.0 a 1.0)."""
        self._dll.gamepad_set_vibration(player, float(low_frequency), float(high_frequency))

    def save_profile(self, player: int, profile_name: str) -> bool:
        """Guarda la configuración actual en un perfil con nombre."""
        return bool(self._dll.gamepad_save_profile(player, profile_name.encode('utf-8')))

    def load_profile(self, player: int, profile_name: str) -> bool:
        """Carga un perfil guardado previamente."""
        return bool(self._dll.gamepad_load_profile(player, profile_name.encode('utf-8')))

    def show_config_dialog(self, parent=None) -> bool:
        """Abre la ventana modal Qt completa de configuración y calibración."""
        return bool(self._dll.gamepad_show_config_dialog(None))

    def show_single_config_dialog(self, parent=None) -> bool:
        """Abre la ventana modal Qt de mapeo para 1 solo jugador."""
        return bool(self._dll.gamepad_show_single_config_dialog(None))

    def show_single_switch_config_dialog(self, parent=None) -> bool:
        """Abre la ventana modal Qt de mapeo de Nintendo Switch / Pro Controller."""
        return bool(self._dll.gamepad_show_single_switch_config_dialog(None))

    @staticmethod
    def launch_config_process(mode: str = "switch"):
        """
        Lanza la interfaz de configuración en un proceso independiente de Windows.
        Esto previene cualquier conflicto de hilos con Tkinter.
        """
        root_dir = os.path.dirname(os.path.abspath(__file__))
        app_candidates = {
            "switch": [
                os.path.join(root_dir, "SingleSwitchMapperApp.exe"),
                os.path.join(root_dir, "GamepadMapperLib", "build", "SingleSwitchMapperApp.exe"),
            ],
            "single": [
                os.path.join(root_dir, "SingleGamepadMapperApp.exe"),
                os.path.join(root_dir, "GamepadMapperLib", "build", "SingleGamepadMapperApp.exe"),
            ],
            "multi": [
                os.path.join(root_dir, "GamepadMapperApp.exe"),
                os.path.join(root_dir, "GamepadMapperLib", "build", "GamepadMapperApp.exe"),
            ]
        }

        for path in app_candidates.get(mode, app_candidates["switch"]):
            if os.path.exists(path):
                return subprocess.Popen([path], cwd=root_dir)

        # Fallback a script python
        return subprocess.Popen([sys.executable, __file__, f"--{mode}"], cwd=root_dir)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        pad = GamepadManager()
        pad.initialize()
        arg = sys.argv[1].lower()
        if "--single" in arg:
            pad.show_single_config_dialog()
        elif "--multi" in arg:
            pad.show_config_dialog()
        else:
            pad.show_single_switch_config_dialog()
        pad.shutdown()
