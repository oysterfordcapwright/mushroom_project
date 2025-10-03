from gpiozero import PWMOutputDevice, DigitalOutputDevice
from rpi_hardware_pwm import HardwarePWM
import time

# ================================
# Pin Mapping with Labels
# ================================
PIN_CONFIG = {
    "water_pump": 27,
    "white_leds": 13,    # Hardware PWM (pwm1 channel 0)
    "uv_leds": 19,       # Hardware PWM (pwm1 channel 1)
    "peltier_fan": 12,
    "intake_fan": 16,
    "internal_fan": 20,
    "outflow_fan": 21,
    "humidifier": 23,
}

# H-bridge config
LEFT_ENABLE_PIN = 26
RIGHT_ENABLE_PIN = 6
LEFT_PWM_PIN = 5
RIGHT_PWM_PIN = 0

# ================================
# Device Controller Class
# ================================
class DeviceController:
    def __init__(self):
        self.devices = {}

        # Setup gpiozero PWM devices (excluding hardware PWM pins 13 and 19)
        for label, pin in PIN_CONFIG.items():
            if pin not in (13, 19):  # hardware PWM handled separately
                if label in ("water_pump", "humidifier"):
                    self.devices[label] = DigitalOutputDevice(pin)
                else:
                    self.devices[label] = PWMOutputDevice(pin, frequency=1000)

        # Setup hardware PWM (GPIO13 + GPIO19)
        self.devices["white_leds"] = HardwarePWM(pwm_channel=0, hz=1000)
        self.devices["uv_leds"] = HardwarePWM(pwm_channel=1, hz=1000)

        # Start hardware PWM at 0% duty
        self.devices["white_leds"].start(0)
        self.devices["uv_leds"].start(0)

        # Setup H-bridge
        self.left_enable = DigitalOutputDevice(LEFT_ENABLE_PIN)
        self.right_enable = DigitalOutputDevice(RIGHT_ENABLE_PIN)
        self.left_pwm = PWMOutputDevice(LEFT_PWM_PIN, frequency=1000)
        self.right_pwm = PWMOutputDevice(RIGHT_PWM_PIN, frequency=1000)

    # ================================
    # Control Functions
    # ================================
    def set_pwm(self, label, duty_cycle: float):
        """
        Set PWM duty cycle for a device.
        duty_cycle: float 0.0-1.0 for gpiozero devices
                    float 0.0-100.0 for hardware PWM (GPIO13/19)
        """
        if label not in self.devices:
            raise ValueError(f"Unknown device label: {label}")

        dev = self.devices[label]

        if isinstance(dev, HardwarePWM):
            dev.change_duty_cycle(duty_cycle)  # expects 0-100
        else:
            dev.value = duty_cycle  # expects 0.0-1.0

    def turn_on(self, label):
        self.set_pwm(label, 1.0 if not isinstance(self.devices[label], HardwarePWM) else 100.0)

    def turn_off(self, label):
        self.set_pwm(label, 0.0)

    # ================================
    # H-Bridge Control
    # ================================
    def hbridge_enable(self, left=True, right=True):
        self.left_enable.value = 1 if left else 0
        self.right_enable.value = 1 if right else 0

    def hbridge_disable(self):
        self.left_enable.off()
        self.right_enable.off()

    def set_hbridge_pwm(self, power, direction="cool"):
        """
        Control H-bridge motor with PWM.
        power: 0.0 - 1.0 (duty cycle)
        direction: "forward" or "backward"
        """

        # Both enable pins must be ON when running
        # self.left_enable.on()
        # self.right_enable.on()

        if direction == "cool":
            # Left side idle, right side drives
            self.left_pwm.value = 0.0
            self.right_pwm.value = power
        elif direction == "heat":
            # Right side idle, left side drives
            self.right_pwm.value = 0.0
            self.left_pwm.value = power
        else:
            # Stop: both off, disable outputs
            self.left_pwm.value = 0.0
            self.right_pwm.value = 0.0
            self.left_enable.off()
            self.right_enable.off()


    # ================================
    # Cleanup
    # ================================
    def cleanup(self):
        for dev in self.devices.values():
            if isinstance(dev, HardwarePWM):
                dev.stop()
            else:
                dev.close()
        self.left_pwm.close()
        self.right_pwm.close()
        self.left_enable.close()
        self.right_enable.close()


if __name__ == "__main__":
    
    try:
        dc = DeviceController()
        
        # Turn on water pump
        dc.turn_on("water_pump")
        time.sleep(5)
        dc.turn_off("water_pump")

        # Fade intake fan (0 - 100%)
        # for i in range(0, 101, 10):
        #     dc.set_pwm("intake_fan", i/100)
        #     time.sleep(0.2)
        dc.set_pwm("intake_fan", 1.0)
        time.sleep(5)
        dc.turn_off("intake_fan")

        # Set white LEDs (hardware PWM)
        dc.set_pwm("white_leds", 50)  # 50% brightness
        time.sleep(3)
        dc.turn_off("white_leds")

        # Use H-bridge
        dc.hbridge_enable()
        dc.set_hbridge_pwm(1.0, "cool")  # forward
        time.sleep(10)
        dc.hbridge_disable()

        # Cleanup
        dc.cleanup()

    except KeyboardInterrupt:
        print("Stopping...")
        dc.hbridge_disable()
        dc.cleanup()
