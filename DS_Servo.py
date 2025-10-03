import threading
import time
from rpi_hardware_pwm import HardwarePWM

_SERVO_MAP = {
    "intake": (0, 0),
    "output": (0, 2),
}
_MIN_DC = 4.0
_MAX_DC = 11.0

_targets = {}
_servos = {}
_threads = {}
_running = True


def _angle_to_dc(angle):
    return _MIN_DC + (angle / 180.0) * (_MAX_DC - _MIN_DC)


def _servo_loop(name, chip, channel):
    pwm = HardwarePWM(pwm_channel=channel, hz=50, chip=chip)
    pwm.start(_angle_to_dc(81))  # start at 90
    _servos[name] = pwm
    _targets[name] = 81

    while _running:
        target = _targets[name]
        pwm.change_duty_cycle(_angle_to_dc(target))
        time.sleep(0.05)  # update rate


def start_servos():
    for name, (chip, channel) in _SERVO_MAP.items():
        t = threading.Thread(target=_servo_loop, args=(name, chip, channel), daemon=True)
        t.start()
        _threads[name] = t


def set_angle(name, angle):
    _targets[name] = max(0, min(180, angle))


def get_angle(name):
    return _targets.get(name)


def stop_servos():
    global _running
    _running = False
    for pwm in _servos.values():
        pwm.stop()
