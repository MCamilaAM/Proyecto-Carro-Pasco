# Multi-Robot Manager for PASCO //control.Node devices
import time
import threading
from typing import Dict, Optional, Callable
from pasco.pasco_bot import PascoBot

MAX_ROBOTS = 5
DEFAULT_ACCEL = 720
SERVO_UPDATE_INTERVAL = 0.02

class RobotSlot:
    def __init__(self, slot_id: int, default_pasco_id: str = "438-831"):
        self.slot_id = slot_id
        self.pasco_id = default_pasco_id
        self.player_idx = slot_id  # Default mapping: Slot 0 -> Player 0, etc.
        self.bot: Optional[PascoBot] = None
        self.connected = False
        self.connecting = False
        self.enabled = True
        self.last_vel_a = 0
        self.last_vel_b = 0
        self.is_moving = False
        self.lift_angle = -98.0
        self.pinza_angle = 70.0
        self.last_lift = -98.0
        self.last_pinza = 70.0
        self.last_servo_send = 0.0
        self.status_msg = "Desconectado"
        self.lock = threading.Lock()

class MultiPascoManager:
    def __init__(self, num_robots: int = MAX_ROBOTS):
        self.num_robots = min(num_robots, MAX_ROBOTS)
        self.slots: Dict[int, RobotSlot] = {}
        
        default_ids = ["438-831", "438-576", "438-123", "438-456", "438-789"]
        for i in range(self.num_robots):
            did = default_ids[i] if i < len(default_ids) else f"438-00{i+1}"
            self.slots[i] = RobotSlot(i, did)

    def get_slot(self, slot_id: int) -> Optional[RobotSlot]:
        return self.slots.get(slot_id)

    def set_player_mapping(self, slot_id: int, player_idx: int):
        slot = self.get_slot(slot_id)
        if slot:
            slot.player_idx = player_idx

    def set_pasco_id(self, slot_id: int, pasco_id: str):
        slot = self.get_slot(slot_id)
        if slot:
            slot.pasco_id = pasco_id.strip()

    def set_enabled(self, slot_id: int, enabled: bool):
        slot = self.get_slot(slot_id)
        if slot:
            slot.enabled = enabled
            if not enabled and slot.connected:
                self.stop_robot(slot_id)

    def connect_async(self, slot_id: int, on_complete: Optional[Callable[[int, bool, str], None]] = None):
        slot = self.get_slot(slot_id)
        if not slot or slot.connecting or slot.connected:
            return

        def _worker():
            slot.connecting = True
            slot.status_msg = "Conectando..."
            target_id = slot.pasco_id.strip()
            if len(target_id) == 6 and '-' not in target_id:
                target_id = f"{target_id[:3]}-{target_id[3:]}"
                slot.pasco_id = target_id

            try:
                bot = PascoBot()
                bot.connect_by_id(target_id)
                with slot.lock:
                    slot.bot = bot
                    slot.connected = True
                    slot.connecting = False
                    slot.status_msg = f"Conectado ({target_id})"
                if on_complete:
                    on_complete(slot_id, True, slot.status_msg)
            except Exception as e:
                err_str = str(e)
                if len(err_str) > 25:
                    err_str = err_str[:25]
                with slot.lock:
                    slot.bot = None
                    slot.connected = False
                    slot.connecting = False
                    slot.status_msg = f"Error: {err_str}"
                if on_complete:
                    on_complete(slot_id, False, slot.status_msg)

        threading.Thread(target=_worker, daemon=True).start()

    def disconnect_async(self, slot_id: int, on_complete: Optional[Callable[[int], None]] = None):
        slot = self.get_slot(slot_id)
        if not slot:
            return

        def _worker():
            with slot.lock:
                if slot.bot and slot.connected:
                    try:
                        slot.bot.stop_steppers(DEFAULT_ACCEL, DEFAULT_ACCEL)
                    except Exception:
                        pass
                    try:
                        slot.bot.disconnect()
                    except Exception:
                        pass
                slot.bot = None
                slot.connected = False
                slot.connecting = False
                slot.is_moving = False
                slot.last_vel_a = 0
                slot.last_vel_b = 0
                slot.status_msg = "Desconectado"
            if on_complete:
                on_complete(slot_id)

        threading.Thread(target=_worker, daemon=True).start()

    def send_drive(self, slot_id: int, vel_a: int, vel_b: int, accel: int = DEFAULT_ACCEL):
        slot = self.get_slot(slot_id)
        if not slot or not slot.connected or not slot.enabled or not slot.bot:
            return

        if vel_a != 0 or vel_b != 0:
            if vel_a != slot.last_vel_a or vel_b != slot.last_vel_b or not slot.is_moving:
                try:
                    slot.bot.rotate_steppers_continuously(vel_a, accel, vel_b, accel)
                    slot.last_vel_a = vel_a
                    slot.last_vel_b = vel_b
                    slot.is_moving = True
                except Exception:
                    pass
        else:
            if slot.is_moving:
                try:
                    slot.bot.stop_steppers(accel, accel)
                    slot.last_vel_a = 0
                    slot.last_vel_b = 0
                    slot.is_moving = False
                except Exception:
                    pass

    def send_servos(self, slot_id: int, lift_angle: float, pinza_angle: float, swap_ports: bool = True):
        slot = self.get_slot(slot_id)
        if not slot or not slot.connected or not slot.enabled or not slot.bot:
            return

        slot.lift_angle = lift_angle
        slot.pinza_angle = pinza_angle
        now = time.time()
        if (lift_angle != slot.last_lift or pinza_angle != slot.last_pinza) and (now - slot.last_servo_send >= SERVO_UPDATE_INTERVAL):
            try:
                s1 = lift_angle if not swap_ports else pinza_angle
                s2 = pinza_angle if not swap_ports else lift_angle
                slot.bot.set_servos("standard", s1, "standard", s2)
                slot.last_lift = lift_angle
                slot.last_pinza = pinza_angle
                slot.last_servo_send = now
            except Exception:
                pass

    def stop_robot(self, slot_id: int):
        slot = self.get_slot(slot_id)
        if slot and slot.connected and slot.bot:
            try:
                slot.bot.stop_steppers(DEFAULT_ACCEL, DEFAULT_ACCEL)
                slot.last_vel_a = 0
                slot.last_vel_b = 0
                slot.is_moving = False
            except Exception:
                pass

    def emergency_stop_all(self):
        for slot_id in self.slots:
            self.stop_robot(slot_id)

    def disconnect_all(self):
        for slot_id in self.slots:
            slot = self.slots[slot_id]
            if slot.connected and slot.bot:
                try:
                    slot.bot.stop_steppers(DEFAULT_ACCEL, DEFAULT_ACCEL)
                    slot.bot.disconnect()
                except Exception:
                    pass
                slot.connected = False
                slot.bot = None
