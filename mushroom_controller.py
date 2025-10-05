import time
import threading
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime, time as dt_time, timedelta
import json
import logging
from simple_pid import PID

# Import your existing libraries
from device_control import DeviceController
# from sensors import get_DS_temp, get_CO2_ppm, get_DHT22_data
from CO2_sensor import get_CO2_data
from DS18B20 import get_DS_temp
from DHT22 import get_DHT22_data

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SystemState(Enum):
    STANDBY = "standby"
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    ERROR = "error"

class LightSchedule:
    def __init__(self, start_time: dt_time, end_time: dt_time, rgb: Tuple[int, int, int] = (0, 0, 0), 
                 white_intensity: float = 0.0, uv_intensity: float = 0.0):
        self.start_time = start_time
        self.end_time = end_time
        self.rgb = rgb
        self.white_intensity = white_intensity
        self.uv_intensity = uv_intensity
    
    def is_active(self, current_time: dt_time) -> bool:
        return self.start_time <= current_time <= self.end_time

@dataclass
class ControlSetpoints:
    # Defaults 
    temperature: float = 20.0
    humidity: float = 85.0
    co2_max: float = 800.0
    light_schedules: List[LightSchedule] = None
    
    def __post_init__(self):
        if self.light_schedules is None:
            # Default light schedule: 8am to 5pm
            self.light_schedules = [
                LightSchedule(dt_time(8, 0), dt_time(17, 0), (255, 255, 255), 0.5, 0.1)
            ]

class MushroomChamberController:
    def __init__(self):
        self.state = SystemState.STANDBY
        self.devices = DeviceController()
        self.setpoints = ControlSetpoints()
        
        # Control parameters defaults
        self.temp_pid = PID(2.0, 0.1, 0.5, setpoint=self.setpoints.temperature)
        self.temp_pid.output_limits = (-1.0, 1.0)  # Full range for heating/cooling
        
        # Ventilation control defaults
        self.vent_angle = 0  # 0=closed, 180=fully open
        self.vent_fan_speed = 0.0
        
        # Timing and state tracking defaults
        self.last_control_cycle = time.time()
        self.control_interval = 5.0  # seconds
        self.sensor_read_interval = 2.0
        
        # Current sensor readings with intialised values for startup
        self.current_temps = {"Probe1": 0.0, "Probe2": 0.0, "Probe3": 0.0, "DHT_Sensor":0.0, "CO2_Sensor":0.0,}  # Should match sensor names
        self.current_humidity = 0.0
        self.current_co2 = 0.0
        
        # Threading
        self.control_thread = None
        self.running = False
        self.lock = threading.RLock()
        
        # Error tracking
        self.errors = []
        self.max_errors = 20 # Ammount of errors stored in buffer
        
        # Photo mode for timelapse
        self.photo_mode_active = False
        self.photo_mode_timeout = 0
        
        # Sensor health tracking
        self.sensor_errors = 0
        self.max_sensor_errors = 5 # This might be unnecessary / cause issues
        
        logger.info("Mushroom Chamber Controller initialized")
    
    def start(self):
        """Start the control system in a background thread"""
        if self.running:
            logger.warning("Controller already running")
            return
        
        self.running = True
        self.state = SystemState.ACTIVE
        self.control_thread = threading.Thread(target=self._control_loop, daemon=True)
        self.control_thread.start()
        logger.info("Control system started")
    
    def stop(self):
        """Stop the control system"""
        self.running = False
        if self.control_thread:
            self.control_thread.join(timeout=5.0)
        self.state = SystemState.STANDBY
        self._safe_shutdown()
        logger.info("Control system stopped")
    
    def emergency_stop(self):
        """Emergency stop - turn off everything immediately"""
        with self.lock:
            self.state = SystemState.STANDBY
            self._safe_shutdown()
            logger.info("EMERGENCY STOP ACTIVATED")
    
    def _safe_shutdown(self):
        """Safely turn off all actuators"""
        with self.lock:
            try:
                # Turn off all devices
                for device in ["water_pump", "humidifier", "internal_fan", "intake_fan", "outflow_fan", "peltier_fan"]:
                    try:
                        self.devices.turn_off(device)
                    except Exception as e:
                        logger.error(f"Error turning off {device}: {e}")
                
                # Stop peltier
                self.devices.set_peltier_pwm(0, "cool")
                self.devices.peltier_disable()
                
                # Close vents
                self.devices.set_servo_angle(0)
                
                # Turn off lights
                self.devices.turn_off("white_leds")
                self.devices.turn_off("uv_leds")
                self.devices.set_neopixel_color("off")
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")
    
    def _control_loop(self):
        """Main control loop running in background thread"""
        last_sensor_read = 0
        
        while self.running:
            current_time = time.time()
            
            try:
                # Read sensors periodically
                if current_time - last_sensor_read >= self.sensor_read_interval:
                    self._read_sensors()
                    last_sensor_read = current_time
                
                # Run control algorithms only if in ACTIVE state
                if current_time - self.last_control_cycle >= self.control_interval:
                    if self.state == SystemState.ACTIVE:
                        self._control_temperature()
                        self._control_humidity()
                        self._control_co2()
                        self._control_lights()
                    self.last_control_cycle = current_time
                
                # Handle photo mode timeout
                if self.photo_mode_active and time.time() > self.photo_mode_timeout:
                    self._end_photo_mode()
                
                time.sleep(0.1)  # Small sleep to prevent CPU overload
                
            except Exception as e:
                logger.error(f"Error in control loop: {e}")
                self._add_error(f"Control loop error: {str(e)}")
                time.sleep(1.0)
    
    def _read_sensors(self):
        """Read all sensors and update current values with error handling"""
        try:
            # Read temperatures from DS18B20 (Probe1, Probe2, Probe3)
            try:
                ds_temps = get_DS_temp()
                if ds_temps:
                    # Mapped to the specific probe names
                    temp_keys = list(ds_temps.keys())
                    if len(temp_keys) >= 3:
                        # Order is consistent: Probe1, Probe2, Probe3
                        self.current_temps["Probe1"] = ds_temps[temp_keys[0]]  # Hot side of peltier
                        self.current_temps["Probe2"] = ds_temps[temp_keys[1]]  # Inside chamber
                        self.current_temps["Probe3"] = ds_temps[temp_keys[2]]  # Outside temperature
            except Exception as e:
                logger.warning(f"Error reading DS18B20: {e}")
            
            # Read CO2
            try:
                co2_data = get_CO2_data()
                co2_value = co2_data["co2"]
                if co2_value and co2_value > 0:
                    self.current_co2 = co2_value
                self.current_temps["C02_sensor"] = co2_data["temperature"]    
            except Exception as e:
                logger.warning(f"Error reading CO2: {e}")
            
            # Read humidity and temp from DHT22
            try:
                dht_data = get_DHT22_data()
                if dht_data:
                    self.current_humidity = dht_data["humidity"]
                    # Update internal temperature with DHT22 if available
                    self.current_temps["DHT_Sensor"] = dht_data["temperature"]      #dht_data.get("temperature", self.current_temps["Probe2"])
                    self.sensor_errors = 0  # Reset error counter on success (might cause issue)
                else:
                    self.sensor_errors += 1
            except Exception as e:
                logger.warning(f"Error reading DHT22: {e}")
                self.sensor_errors += 1
            
            # If too many sensor errors, go to error state
            if self.sensor_errors >= self.max_sensor_errors:
                logger.error("Too many sensor errors, entering error state")        # this all might cause issues
                self.state = SystemState.ERROR
                self._add_error("Critical: Too many sensor errors")
                
        except Exception as e:
            logger.error(f"Critical error reading sensors: {e}")
            self._add_error(f"Critical sensor error: {str(e)}")
    
    def _control_temperature(self):
        """PID control for temperature using peltier"""
        current_temp = self.current_temps["Probe2"]  # Use Probe2 (inside chamber)
        
        with self.lock:
            # Update PID setpoint
            self.temp_pid.setpoint = self.setpoints.temperature
            
            # Calculate PID output
            pid_output = self.temp_pid(current_temp)
            
            # Determine heating/cooling mode
            if abs(pid_output) < 0.1:  # Deadband
                self.devices.peltier_disable()
                self.devices.set_peltier_pwm(0, "off")
                self.devices.turn_off("peltier_fan")
                self.devices.turn_off("water_pump")
            else:
                # Enable peltier system
                self.devices.peltier_enable()
                self.devices.turn_on("peltier_fan")
                self.devices.turn_on("water_pump")
                
                if pid_output > 0:  # Need heating
                    self.devices.set_peltier_pwm(pid_output, "heat")        # May need to switch heating vs cooling (may cause issue)
                else:  # Need cooling
                    self.devices.set_peltier_pwm(abs(pid_output), "cool")
    
    def _control_humidity(self):
        """Control humidity using humidifier and condensation, uses bang-bang control"""
        if not self.current_humidity:
            return
        
        with self.lock:
            humidity_error = self.setpoints.humidity - self.current_humidity
            
            if humidity_error > 5:  # Too dry -> add humidity
                self.devices.turn_on("humidifier")
                # Ensure internal fan is on for distribution
                self.devices.turn_on("internal_fan")
                
            elif humidity_error < -5:  # Too humid -> reduce humidity
                self.devices.turn_off("humidifier")
                # Turn off internal fan to allow condensation
                self.devices.turn_off("internal_fan")
                # Brief cooling without fan to condense moisture                    # Currently trying to use peltier to remove moisture, might cause issues
                if self.current_temps["Probe2"] > self.setpoints.temperature - 2:   #
                    self.devices.peltier_enable()                                   #
                    self.devices.set_peltier_pwm(1, "cool")                         # The control is looped every 5 seconds so this should be kind of like 70% duty cooling
                    time.sleep(3.5)                                                 #
                    self.devices.set_peltier_pwm(0, "off")                          #
            else:
                self.devices.turn_off("humidifier")
                self.devices.turn_on("internal_fan")  # Normal circulation
    
    def _control_co2(self):
        """Control CO2 levels using ventilation"""
        if not self.current_co2:
            return
        
        with self.lock:
            co2_error = self.current_co2 - self.setpoints.co2_max
            
            if co2_error > 0:  # CO2 too high
                # Calculate vent opening based on CO2 level
                vent_ratio = min(1.0, co2_error / 500.0)  # Scale with error    might neet to add a max(0.1...) case since fans might not work this low (might cause issues)
                self.vent_angle = int(180 * vent_ratio)
                self.vent_fan_speed = max(0.4,vent_ratio)
                
                self.devices.set_servo_angle(self.vent_angle)
                self.devices.set_pwm("intake_fan", self.vent_fan_speed)
                self.devices.set_pwm("outflow_fan", self.vent_fan_speed)
                
            else:  # CO2 within limits
                self.vent_angle = 0
                self.vent_fan_speed = 0
                self.devices.set_servo_angle(0)
                self.devices.turn_off("intake_fan")
                self.devices.turn_off("outflow_fan")
    
    def _control_lights(self):
        """Control lights based on schedule or photo mode"""
        if self.photo_mode_active:
            return  # Photo mode overrides normal lighting
        
        current_time = datetime.now().time()
        
        with self.lock:
            active_schedule = None
            for schedule in self.setpoints.light_schedules:
                if schedule.is_active(current_time):
                    active_schedule = schedule
                    break
            
            if active_schedule:
                # Set NeoPixel color
                try:
                    # Fixed colours for now, could add custom RGB, would need to extend device_control
                    self.devices.set_neopixel_color("white")                                            # Might cause issue (rgb input to shedule colours is being ignored)
                    # Set white LEDs
                    self.devices.set_pwm("white_leds", active_schedule.white_intensity * 100)
                    # Set UV LEDs
                    self.devices.set_pwm("uv_leds", active_schedule.uv_intensity * 100)
                except Exception as e:
                    logger.error(f"Error controlling lights: {e}")
            else:
                # Lights off
                self.devices.set_neopixel_color("off")
                self.devices.turn_off("white_leds")
                self.devices.turn_off("uv_leds")
    
    def _add_error(self, error_msg):
        """Add error to error log"""
        self.errors.append({
            "timestamp": datetime.now().isoformat(),
            "message": error_msg
        })
        # Keep only recent errors
        if len(self.errors) > self.max_errors:
            self.errors.pop(0)
    
    # ================================
    # Public API Methods for Flask Routes
    # ================================
    
    def get_sensor_data(self) -> Dict:
        """Get all sensor data in format compatible with your existing routes"""
        with self.lock:
            return {
                "temperatures": self.current_temps,
                "humidity": self.current_humidity,
                "co2": self.current_co2
            }
    
    def get_control_status(self) -> Dict:
        """Get control system status"""
        with self.lock:
            return {
                "system_state": self.state.value,
                "setpoints": {
                    "temperature": self.setpoints.temperature,
                    "humidity": self.setpoints.humidity,
                    "co2_max": self.setpoints.co2_max,          #light setpoints might cause issues
                    "light_schedules": [
                        {
                            "start": s.start_time.strftime("%H:%M"),
                            "end": s.end_time.strftime("%H:%M"),
                            "rgb": s.rgb,
                            "white": s.white_intensity,
                            "uv": s.uv_intensity
                        } for s in self.setpoints.light_schedules
                    ]
                },
                "actuator_states": {
                    "peltier": self.devices.get_peltier_state(),
                    "servo_angle": self.devices.get_servo_angle(),
                    "vent_fan_speed": self.vent_fan_speed,
                    "humidifier": bool(self.devices.get_state("humidifier")),
                    "internal_fan": bool(self.devices.get_state("internal_fan"))
                },
                "photo_mode": self.photo_mode_active
            }
    
    def set_temperature(self, temperature: float):
        """Set temperature setpoint"""
        with self.lock:
            self.setpoints.temperature = float(temperature)
            logger.info(f"Temperature setpoint updated to: {temperature}°C")
    
    def set_humidity(self, humidity: float):
        """Set humidity setpoint"""
        with self.lock:
            self.setpoints.humidity = float(humidity)
            logger.info(f"Humidity setpoint updated to: {humidity}%")
    
    def set_co2_level(self, co2_max: float):
        """Set CO2 maximum level"""
        with self.lock:
            self.setpoints.co2_max = float(co2_max)
            logger.info(f"CO2 max level updated to: {co2_max} ppm")
    
    def set_light_schedule(self, schedules: List[Dict]):
        """Set light schedules"""
        with self.lock:
            new_schedules = []
            for schedule in schedules:
                start = datetime.strptime(schedule["start"], "%H:%M").time()
                end = datetime.strptime(schedule["end"], "%H:%M").time()
                rgb = tuple(schedule["rgb"])
                white = schedule.get("white", 0.0)
                uv = schedule.get("uv", 0.0)
                new_schedules.append(LightSchedule(start, end, rgb, white, uv))
            
            self.setpoints.light_schedules = new_schedules
            logger.info(f"Light schedules updated: {len(schedules)} schedules")
    
    def set_light_wavelengths(self, rgb: Tuple[int, int, int], white_intensity: float, uv_intensity: float):
        """Set manual light wavelengths and intensities"""
        with self.lock:
            # This could override schedules or work with them
            # For now, let's create a temporary schedule for immediate effect
            current_time = datetime.now().time()
            end_time = (datetime.now() + timedelta(hours=1)).time()
            
            temp_schedule = LightSchedule(current_time, end_time, rgb, white_intensity, uv_intensity)
            self.setpoints.light_schedules = [temp_schedule]
            
            logger.info(f"Light wavelengths set: RGB{rgb}, White:{white_intensity}, UV:{uv_intensity}")
    
    def trigger_photo_mode(self, duration: int = 30):
        """
        Trigger photo mode for timelapse photography
        duration: seconds to keep lights on for photo
        """
        with self.lock:
            self.photo_mode_active = True
            self.photo_mode_timeout = time.time() + duration
            
            # Turn on white LEDs for photography
            self.devices.turn_on("white_leds")
            # Add some NeoPixel fill light
            self.devices.set_neopixel_color("white")
            
            logger.info(f"Photo mode activated for {duration} seconds")
    
    def _end_photo_mode(self):
        """End photo mode and return to normal lighting"""
        with self.lock:
            self.photo_mode_active = False
            # Return to normal lighting control
            self._control_lights()
            logger.info("Photo mode ended")
    
    def get_pid_parameters(self) -> Dict:
        """Get current PID parameters"""
        return {
            "kp": self.temp_pid.Kp,
            "ki": self.temp_pid.Ki,
            "kd": self.temp_pid.Kd,
            "setpoint": self.temp_pid.setpoint
        }
    
    def update_pid_parameters(self, kp: float = None, ki: float = None, kd: float = None):
        """Update PID parameters"""
        with self.lock:
            if kp is not None:
                self.temp_pid.Kp = kp
            if ki is not None:
                self.temp_pid.Ki = ki
            if kd is not None:
                self.temp_pid.Kd = kd
            
            logger.info(f"PID parameters updated: Kp={self.temp_pid.Kp}, Ki={self.temp_pid.Ki}, Kd={self.temp_pid.Kd}")
    
    def set_system_state(self, state: str):                     #Might cause issues since I never activate the system
        """Change system state"""
        try:
            new_state = SystemState(state)
            with self.lock:
                self.state = new_state
                if new_state == SystemState.STANDBY:
                    self._safe_shutdown()
                logger.info(f"System state changed to: {state}")
        except ValueError:
            raise ValueError(f"Invalid system state: {state}")

# Global instance
chamber_controller = MushroomChamberController()            # Not sure why this is here yet (issues)

def initialize_controller():
    """Initialize and start the controller"""
    chamber_controller.start()
    return chamber_controller

def shutdown_controller():
    """Shutdown the controller"""
    chamber_controller.stop()