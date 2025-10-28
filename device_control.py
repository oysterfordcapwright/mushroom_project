import time
import board
import neopixel_spi as neopixel
from rpi_hardware_pwm import HardwarePWM
from gpiozero import PWMOutputDevice, DigitalOutputDevice
from DS18B20 import get_DS_temp
from CO2_sensor import get_CO2_data
from DHT22 import get_DHT22_data
import smbus2
import math


# Pin Mapping with Labels
PIN_CONFIG = {
    "water_pump": 27,
    "white_leds": 12,       # Hardware PWM (channel 0)
    "uv_leds": 13,          # Hardware PWM (channel 1)
    "peltier_fan": 1,
    "intake_fan": 16,
    "outflow_fan": 21,
    "internal_fan": 20,
    "humidifier": 23,
}

# Servos config
MIN_DC = 4.5    
MAX_DC = 10     

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

        # Setup gpiozero PWM devices (excluding hardware PWM pins)
        for label, pin in PIN_CONFIG.items():
            if pin not in (13, 12, 18):  # hardware PWM handled separately
                if label in ("water_pump", "humidifier"):
                    self.devices[label] = DigitalOutputDevice(pin)
                else:
                    self.devices[label] = PWMOutputDevice(pin, frequency=20)

        # Setup hardware PWM LEDs
        self.devices["white_leds"] = HardwarePWM(pwm_channel=0, hz=1000, chip=0)
        self.devices["uv_leds"] = HardwarePWM(pwm_channel=1, hz=1000, chip=0)

        # Start LED PWM at 0% duty
        self.devices["white_leds"].start(0)
        self.devices["uv_leds"].start(0)
        
        # Setup servos on hardware PWM
        self._servo_pwm = HardwarePWM(pwm_channel=2, hz=50, chip=0)
        self._servo_pwm.start(self._angle_to_dc(0))  # start closed (default state) 
        self._servo_angle = 0

        
        # NeoPixel SPI Setup
        self.NEO_NUM_PIXELS = 12 
        self.COLOR_MAP = {
            "red": (255, 0, 0),
            "green": (0, 255, 0),
            "blue": (0, 0, 255),
            "yellow": (255, 255, 0),
            "cyan": (0, 255, 255),
            "magenta": (255, 0, 255),
            "white": (255, 255, 255),
            "orange": (255, 165, 0),
            "purple": (128, 0, 128),
            "off": (0, 0, 0)
        }
        self.neopixels = neopixel.NeoPixel_SPI(
            board.SPI(),
            self.NEO_NUM_PIXELS,
            brightness=0.2,
            auto_write=False,
        )
        self.neopixel_state = [(0, 0, 0)] * self.NEO_NUM_PIXELS
        self.neopixels.fill((0, 0, 0))
        self.neopixels.show()

        # Setup peltier H-bridge
        self.left_enable = DigitalOutputDevice(LEFT_ENABLE_PIN)
        self.right_enable = DigitalOutputDevice(RIGHT_ENABLE_PIN)
        self.left_pwm = PWMOutputDevice(LEFT_PWM_PIN, frequency=40)
        self.right_pwm = PWMOutputDevice(RIGHT_PWM_PIN, frequency=40)

    # ================================
    # Control Functions
    # ================================
    def set_pwm(self, label, duty_cycle: float):
        """
        Set PWM duty cycle for a device.
        duty_cycle: float 0.0-1.0 for gpiozero devices
                    float 0.0-100.0 for hardware PWM 
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
    # Servo Control
    # ================================
    def _angle_to_dc(self, angle):
        """Map angle (0-180°) to duty cycle usually."""
        return MIN_DC + (angle / 180.0) * (MAX_DC - MIN_DC)

    def set_servo_angle(self, angle):
        """Set angle in degrees (0-180). Controls both servos since same pin."""
        clamped = max(0, min(180, angle))
        self._servo_pwm.change_duty_cycle(self._angle_to_dc(clamped))
        self._servo_angle = clamped

    def stop_servo(self):
        """Turn off the servo PWM signal (both servos stop holding)."""
        self._servo_pwm.stop()


    # ================================
    # H-Bridge Control
    # ================================
    def peltier_enable(self, left=True, right=True):
        self.left_enable.value = 1 if left else 0
        self.right_enable.value = 1 if right else 0

    def peltier_disable(self):
        self.left_enable.off()
        self.right_enable.off()

    def set_peltier_pwm(self, power, direction="cool"):
        """
        Control H-bridge motor with PWM.
        power: 0.0 - 1.0 (duty cycle)
        direction: "forward" or "backward"
        """
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
    # NeoPixel Control
    # ================================
    def set_neopixel_color(self, color_name, pixel_indices=None):
        """
        Set NeoPixel color by name.
        color_name: str from COLOR_MAP
        pixel_indices: list of indices to update, None = all
        """
        color = self.COLOR_MAP.get(color_name.lower())
        if color is None:
            raise ValueError(f"Unknown color '{color_name}'. Valid options: {list(self.COLOR_MAP.keys())}")

        if pixel_indices is None:
            self.neopixels.fill(color)
            self.neopixel_state = [color] * self.NEO_NUM_PIXELS
        else:
            for i in pixel_indices:
                if 0 <= i < self.NEO_NUM_PIXELS:
                    self.neopixels[i] = color
                    self.neopixel_state[i] = color

        self.neopixels.show()

    def set_neopixel_brightness(self, brightness):
        """
        Set brightness for all NeoPixels.
        brightness: float 0.0 (off) to 1.0 (full brightness)
        """
        if not 0.0 <= brightness <= 1.0:
            raise ValueError("Brightness must be between 0.0 and 1.0")
        
        self.neopixels.brightness = brightness
        self.neopixels.show()


    # ================================
    # State Getters
    # ================================
    def get_state(self, label):
        """
        Get the current state (duty cycle or on/off) of a device by label.
        Returns:
            - float: duty cycle (0.0-1.0 for gpiozero, 0-100 for HardwarePWM)
            - bool: True/False for DigitalOutputDevice
        """
        if label not in self.devices:
            raise ValueError(f"Unknown device label: {label}")

        dev = self.devices[label]

        if isinstance(dev, HardwarePWM):
            return dev.duty_cycle  # already 0-100
        elif isinstance(dev, PWMOutputDevice):
            return dev.value       # 0.0-1.0
        elif isinstance(dev, DigitalOutputDevice):
            return dev.value       # 0/1 (False/True)
        else:
            return None

    def get_servo_angle(self):
        """Return the last commanded servo angle in degrees."""
        return self._servo_angle

    def get_peltier_state(self):
        """
        Return a dict describing the Peltier's state.
        Includes mode ('cool', 'heat', 'off') and current duty cycle.
        """
        left_val = self.left_pwm.value
        right_val = self.right_pwm.value

        if left_val > 0 and right_val == 0:
            mode = "heat"
            duty = left_val
        elif right_val > 0 and left_val == 0:
            mode = "cool"
            duty = right_val
        else:
            mode = "off"
            duty = 0.0

        return {
            "mode": mode,
            "duty_cycle": duty,   # 0.0-1.0
            "enabled": (self.left_enable.value or self.right_enable.value)
        }

    def get_neopixel_state(self, index=None):
        """
        Get NeoPixel state.
        index: None returns full list, else return color of that pixel
        """
        if index is None:
            return self.neopixel_state
        elif 0 <= index < self.NEO_NUM_PIXELS:
            return self.neopixel_state[index]
        else:
            raise ValueError(f"Pixel index {index} out of range (0-{self.NEO_NUM_PIXELS-1})")


    # ================================
    # Cleanup
    # ================================
    def cleanup(self):

        # Turn off NeoPixels first
        if hasattr(self, "neopixels"):
            self.neopixels.fill((0, 0, 0))
            self.neopixels.show()
            self.neopixel_state = [(0, 0, 0)] * self.NEO_NUM_PIXELS
        
        # Stop and close other devices
        for dev in self.devices.values():
            if isinstance(dev, HardwarePWM):
                dev.stop()
            else:
                dev.close()

        # Stop servos
        if hasattr(self, "_servo_pwm"):
            dev.change_duty_cycle(self._angle_to_dc(0)) 
            time.sleep(0.5)  # give time to physically move
            self._servo_pwm.stop()
        
         # Close peltier H-bridge
        self.left_pwm.close()
        self.right_pwm.close()
        self.left_enable.close()
        self.right_enable.close()

def gxhtc3_read():
    try:
        bus.write_i2c_block_data(0x70, 0x35, [0x17])
        time.sleep(0.001)  # Short delay after wake-up
    
        bus.write_i2c_block_data(0x70, 0x7C, [0xA2])
        time.sleep(0.02) 
        data = bus.read_i2c_block_data(0x70, 0x00, 6)
        
        bus.write_i2c_block_data(0x70, 0xB0, [0x98])
        
        # Extract and convert values
        temp_raw = (data[0] << 8) | data[1]
        hum_raw = (data[3] << 8) | data[4]
        
        temp = -45 + (175 * temp_raw / 65535.0)
        hum = 100 * hum_raw / 65535.0
        
        return temp, hum
        
    except Exception as e:
        print(f"GXHTC3 error: {e}")
        return None, None


if __name__ == "__main__":
    
    try:
        dc = DeviceController()
        

        # Set white LEDs (hardware PWM)
        # dc.set_pwm("white_leds", 80)
        # dc.set_pwm("uv_leds", 80)  # 50% brightness

        # Set all pixels to red
        # dc.set_neopixel_color("red")
        # time.sleep(3)

        # # Set pixels 0 and 1 to blue
        # dc.set_neopixel_color("blue", pixel_indices=[0,1])
        # time.sleep(3)


        # Use H-bridge
        # dc.peltier_enable()
        # dc.set_peltier_pwm(1, "cool")  # forward
        dc.turn_on("peltier_fan")
        dc.turn_on("water_pump")
        # dc.turn_on("humidifier")
        dc.turn_on("internal_fan")
        # dc.turn_on("intake_fan")
        # dc.turn_on("outflow_fan")
        # dc.set_servo_angle(360)
        # t=0

        bus = smbus2.SMBus(1)

        while True:
            temperatures = get_DS_temp()
            CO2_data = get_CO2_data()
            humid_data = get_DHT22_data()
            gxhtc3_temp, gxhtc3_hum = gxhtc3_read()
            
            print("\n" + "="*50)
            print("SENSOR COMPARISON -", time.strftime("%H:%M:%S"))
            print("="*50)
            
            print("TEMPERATURE SENSORS:")
            print(f"  DS18B20 - Probe1...{temperatures['Probe1']:.1f}°C")
            print(f"  DS18B20 - Probe2...{temperatures['Probe2']:.1f}°C") 
            print(f"  DS18B20 - Probe3...{temperatures['Probe3']:.1f}°C")
            print(f"  CO2 Sensor.........{CO2_data['temperature']:.0f}°C")
            print(f"  DHT22..............{humid_data['temperature']-0.7:.1f}°C")
            print(f"  GXHTC3.............{gxhtc3_temp:.1f}°C" if gxhtc3_temp else "  GXHTC3:          Failed")
            print()
            print("HUMIDITY SENSORS:")
            print(f"  DHT22..............{humid_data['humidity']:.1f}%")
            print(f"  GXHTC3.............{gxhtc3_hum:.1f}%" if gxhtc3_hum else "  GXHTC3:   Failed")
            
            # print("="*50)
            
            time.sleep(2)
        #     t=t+1
            
        #     dc.set_servo_angle(math.sin(t/500)*90+90)

        # while True:
        #     dc.set_servo_angle(0)
        #     time.sleep(3)
        #     dc.set_servo_angle(180)
        #     time.sleep(3)


        # Cleanup
        # dc.cleanup()

    except KeyboardInterrupt:
        print("Stopping...")
        dc.peltier_disable()
        dc.cleanup()
