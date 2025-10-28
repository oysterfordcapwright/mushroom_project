import time
import threading
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, time as dt_time, timedelta
import json
import logging
import csv
import os
from simple_pid import PID

from device_control import DeviceController
from CO2_sensor import get_CO2_data
from DS18B20 import get_DS_temp
from DHT22 import get_DHT22_data

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SystemState(Enum):
    STANDBY = "standby"
    ACTIVE = "active"
    ERROR = "error"

class LightSchedule:
    def __init__(self, start_time: dt_time, end_time: dt_time, colour: str = "off", 
                  neopixel_intensity: float = 0.0, white_intensity: float = 0.0, uv_intensity: float = 0.0):
        self.start_time = start_time
        self.end_time = end_time
        self.colour = colour
        self.neopixel_intensity = neopixel_intensity
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
                LightSchedule(dt_time(8, 0), dt_time(17, 0), "off", 0.0, 0.0, 0.0)
            ]

class MushroomChamberController:
    def __init__(self):
        self.state = SystemState.STANDBY
        self.devices = DeviceController()
        self.setpoints = ControlSetpoints()
        self.system_start_time = None
        
        # Control temp parameters defaults
        self.temp_control_state = False
        self.temp_pid = PID(0.9, 0.0008, 0.5, setpoint=self.setpoints.temperature)
        self.temp_pid.output_limits = (-1.0, 0.13)  # Full range for heating/cooling
        self.temp_pid.auto_mode = True      # Enable anti-windup
        self.steady_state_bias = 0.0  
        self.last_stable_time = None
        self.temperature_stable_start_time = None
        self.temperature_stable = False

        # Humidity control state
        self.humidity_control_state = False
        self.humidifier_on_time = None  
        self.humidifier_runtime_limit = 5400  # 1 hour 30 min in seconds
        self.humidity_override_active = False
        self.humidity_override_start_time = None
        self.ventilation_phase_start_time = None
        self.humidity_history = []  # Track humidity trends

        # CO2 control state
        self.CO2_control_state = False
        
        # Ventilation control defaults
        self.vent_angle = 0  # 0=closed, 180=fully open
        self.vent_fan_speed = 0.0
        
        # Timing and state tracking defaults
        self.last_control_cycle = time.time()
        self.control_interval = 2.0  # seconds
        self.sensor_read_interval = 2.0
        
        # Current sensor readings with intialised values for startup
        self.current_temps = {"Probe1": 0.0, "Probe2": 0.0, "Probe3": 0.0, "DHT_Sensor":0.0, "CO2_Sensor":0.0,}
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
        self.max_sensor_errors = 5 

        # Data logging
        self.log_file = "/home/luke/mushroom_project/mushroom_chamber_data.csv"
        self.log_interval = 10  # Log every 10 sec
        self.last_log_time = 0
        self.setup_data_logging()
        
        logger.info("Mushroom Chamber Controller initialized")
    
    def start(self):
        """Start the control system in a background thread"""
        if self.running:
            logger.warning("Controller already running")
            return
        
        self.running = True
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
    
    def setup_data_logging(self):
        """Setup CSV logging file with headers"""
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'system_state', 
                    'temp_setpoint', 'humidity_setpoint', 'co2_setpoint',
                    'temp_probe1', 'temp_probe2', 'temp_probe3', 'temp_dht', 'temp_co2',
                    'humidity', 'co2_ppm',
                    'peltier_mode', 'peltier_duty', 'peltier_enabled',
                    'humidifier', 'internal_fan',
                    'vent_angle', 'vent_fan_speed',
                    'active_light_schedule', 'neopixel_color', 'neopixel_intensity',
                    'white_intensity', 'uv_intensity', 'photo_mode'
                ])
        logger.info(f"Data logging setup complete. Log file: {self.log_file}")

    def log_system_data(self):
        """Log current system state to CSV"""
        current_time = time.time()
        if current_time - self.last_log_time >= self.log_interval:
            try:
                with self.lock:
                    # Get active light schedule
                    current_time_obj = datetime.now().time()
                    active_schedule = None
                    active_schedule_name = "None"
                    neopixel_color = "off"
                    neopixel_intensity = 0
                    white_intensity = 0
                    uv_intensity = 0
                    
                    for schedule in self.setpoints.light_schedules:
                        if schedule.is_active(current_time_obj):
                            active_schedule = schedule
                            active_schedule_name = f"{schedule.start_time.strftime('%H:%M')}-{schedule.end_time.strftime('%H:%M')}"
                            neopixel_color = schedule.colour
                            neopixel_intensity = schedule.neopixel_intensity
                            white_intensity = schedule.white_intensity
                            uv_intensity = schedule.uv_intensity
                            break
                    
                    peltier_state = self.devices.get_peltier_state()
                    
                    with open(self.log_file, 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            datetime.now().isoformat(),
                            self.state.value,
                            self.setpoints.temperature,
                            self.setpoints.humidity,
                            self.setpoints.co2_max,
                            self.current_temps.get("Probe1", 0),
                            self.current_temps.get("Probe2", 0),
                            self.current_temps.get("Probe3", 0),
                            self.current_temps.get("DHT_Sensor", 0),
                            self.current_temps.get("CO2_Sensor", 0),
                            self.current_humidity,
                            self.current_co2,
                            peltier_state['mode'],
                            peltier_state['duty_cycle'],
                            peltier_state['enabled'],
                            bool(self.devices.get_state("humidifier")),
                            bool(self.devices.get_state("internal_fan")),
                            self.vent_angle,
                            self.vent_fan_speed,
                            active_schedule_name,
                            neopixel_color,
                            neopixel_intensity,
                            white_intensity,
                            uv_intensity,
                            self.photo_mode_active
                        ])
                
                self.last_log_time = current_time
                
            except Exception as e:
                logger.error(f"Error logging system data: {e}")

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
                
                # Log system data
                self.log_system_data()

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
                        self.current_temps["Probe1"] = ds_temps[temp_keys[0]]  # Hot side of peltier
                        self.current_temps["Probe2"] = round(ds_temps[temp_keys[1]]+0.2,4)  # Inside chamber
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
                    self.current_temps["DHT_Sensor"] = round(dht_data["temperature"]-0.7,3)     #dht sensor reads wtih 0.7°C offset
                    self.sensor_errors = 0  
                else:
                    self.sensor_errors += 1
            except Exception as e:
                logger.warning(f"Error reading DHT22: {e}")
                self.sensor_errors += 1
            
            # If too many sensor errors, go to error state
            if self.sensor_errors >= self.max_sensor_errors:
                logger.error("Too many sensor errors, entering error state")        
                self.state = SystemState.ERROR
                self._add_error("Critical: Too many sensor errors")
                
        except Exception as e:
            logger.error(f"Critical error reading sensors: {e}")
            self._add_error(f"Critical sensor error: {str(e)}")
    
    def _control_temperature(self):
        """PID control for temperature using peltier"""
        current_temp = self.current_temps["DHT_Sensor"]  # Use DHT temp reading (inside chamber)

        if self._check_temperature_safety():
            return  # Exit if safety limits triggered

        with self.lock:
            # Update PID setpoint
            self.temp_pid.setpoint = self.setpoints.temperature
            
            # Calculate PID output
            pid_output = self.temp_pid(current_temp)

            # Manual bias based on temperature difference from ambient
            ambient_temp = self.current_temps.get("Probe1", 20)  # Outside temp
            temp_diff = self.setpoints.temperature - ambient_temp

            if temp_diff > 0:  # Heating needed
                manual_bias = min(0.09, temp_diff * 0.02)  # 2% per °C above ambient
            else:  # Cooling needed
                manual_bias = max(-0.9, temp_diff * 0.16)  # 16% per °C below ambient
            
            print("Manual bias =", manual_bias)

            final_output = pid_output + manual_bias
            final_output = max(min(final_output, 0.13), -1.0)

            # Learn the steady-state bias when we're stable
            # temp_error = abs(current_temp - self.setpoints.temperature)
            # if temp_error < 0.2:  # Very close to setpoint
            #     if self.last_stable_time is None:
            #         self.last_stable_time = time.time()
            #     elif time.time() - self.last_stable_time > 60:  # Stable for 1 minute
            #         # Gradually adapt the bias toward the current output
            #         self.steady_state_bias = 0.95 * self.steady_state_bias + 0.05 * pid_output
            # else:
            #     self.last_stable_time = None
            
            # # Apply the learned bias
            # final_output = pid_output + self.steady_state_bias

            # final_output = max(min(final_output, 0.1), -1.0)
            
            # Determine heating/cooling mode
            if abs(final_output) > 0.0001: #0.0001:  # Deadband
                
                # Enable peltier system
                self.devices.peltier_enable()
                self.devices.turn_on("peltier_fan")
                self.devices.turn_on("water_pump")
                self.devices.turn_on("internal_fan")
                self.temp_control_state = True
                
                if final_output > 0:  # Need heating
                    self.devices.set_peltier_pwm(final_output, "heat") 
                else:  # Need cooling
                    self.devices.set_peltier_pwm(abs(final_output), "cool")

            elif self.temp_control_state == True:
                self.devices.peltier_disable()
                self.devices.set_peltier_pwm(0, "off")
                self.devices.turn_off("peltier_fan")
                self.devices.turn_off("water_pump")
                self.devices.turn_off("internal_fan")
                self.temp_control_state = False
                
    def _check_temperature_safety(self):
        """Check and enforce temperature safety limits"""
        safety_triggered = False
        
        # Peltier temperature safety (probe 3)
        if self.current_temps.get("Probe3", 0) > 40.0:
            self.devices.peltier_disable()
            self.devices.set_peltier_pwm(0, "off")
            print("SAFETY: Peltier disabled - temperature exceeded 40°C")
            safety_triggered = True
        
        # Coil temperature safety (probe 2)  
        if self.current_temps.get("Probe2", 0) > 30.0:
            self.devices.peltier_disable()
            self.devices.set_peltier_pwm(0, "off")
            print("SAFETY: Coil temperature exceeded 30°C")
            safety_triggered = True
        
        return safety_triggered
    
    def _is_temperature_stable(self, stability_threshold=0.5, stability_duration=120):
        """Check if temperature has been stable within threshold for duration (default: 2 minutes)"""
        if not hasattr(self, 'current_temps') or "DHT_Sensor" not in self.current_temps:
            return False
        
        current_temp = self.current_temps["DHT_Sensor"]
        temp_error = abs(current_temp - self.setpoints.temperature)
        
        # Check if temperature is within threshold
        if temp_error <= stability_threshold:
            if self.temperature_stable_start_time is None:
                # Start timing stability
                self.temperature_stable_start_time = time.time()
                print(f"TEMPERATURE: Starting stability timer - within {stability_threshold}°C of setpoint")
            else:
                # Check if been stable long enough
                stable_time = time.time() - self.temperature_stable_start_time
                if stable_time >= stability_duration:
                    return True
                else:
                    remaining = (stability_duration - stable_time) / 60
                    print(f"TEMPERATURE: Stable for {stable_time/60:.1f}min, {remaining:.1f}min remaining")
        else:
            # Temperature not stable - reset timer
            if self.temperature_stable_start_time is not None:
                print(f"TEMPERATURE: Lost stability - error: {temp_error:.2f}°C")
            self.temperature_stable_start_time = None
        
        return False

    def _control_humidity(self):
        """Control humidity using prioritized approach: ventilation -> evaporative cooling -> natural absorption"""
        if not self.current_humidity:
            return
        
        if self.devices.get_state("humidifier"):
            if self.humidifier_on_time is None:
                self.humidifier_on_time = time.time()
            else:
                runtime = time.time() - self.humidifier_on_time
                if runtime >= self.humidifier_runtime_limit:
                    print("HUMIDITY: Humidifier reached safety timeout, cycling power to reset")
                    self.devices.turn_off("humidifier")
                    time.sleep(0.4)  # Give module time to reset 
                    self.devices.turn_on("humidifier")
                    self.humidifier_on_time = time.time()  # Reset timer
        else:
            # Reset timer if humidifier is off
            self.humidifier_on_time = None
        
        # Check if temperature is stable first
        if not self._is_temperature_stable():
            if self.temperature_stable:  # Was stable, now unstable
                print("HUMIDITY: Temperature unstable - pausing humidity control")
                self.temperature_stable = False
                # Turn off humidifier everything
                self.devices.turn_off("humidifier")
                self.vent_angle = 0
                self.vent_fan_speed = 0
                self.devices.set_servo_angle(0)
                self.devices.set_pwm("intake_fan", 0)
                self.devices.set_pwm("outflow_fan", 0)
                self.devices.turn_off("internal_fan")
            return
        
        # If here, temperature is stable
        if not self.temperature_stable:
            print("HUMIDITY: Temperature stable - resuming humidity control")
            self.temperature_stable = True
        
        
        # Check if in cooldown period after natural absorption
        current_time = time.time()
        if hasattr(self, 'humidity_cooldown_until') and current_time < self.humidity_cooldown_until:
            remaining = (self.humidity_cooldown_until - current_time) / 60
            print(f"HUMIDITY: In cooldown period - {remaining:.1f} minutes remaining")
            return
        
        with self.lock:
            humidity_error = self.setpoints.humidity - self.current_humidity
            
            if humidity_error > 2:  # Too dry -> add humidity (with hysteresis)
                self.devices.turn_on("humidifier")
                self.devices.turn_on("internal_fan")  # Distribute humidity
                # Reset all humidity control states
                self.humidity_override_active = False
                self.humidity_override_start_time = None
                self.ventilation_phase_start_time = None
                self.humidity_control_state = True
                # Clear any cooldown since now adding humidity
                if hasattr(self, 'humidity_cooldown_until'):
                    delattr(self, 'humidity_cooldown_until')
                print("HUMIDITY: Adding humidity - humidifier ON")
                
            elif humidity_error < -3:  # Too humid -> reduce humidity (with hysteresis)
                self._reduce_humidity_prioritized()
                self.humidity_control_state = True
            elif self.humidity_control_state == True:
                # Within acceptable range
                self.devices.turn_off("humidifier")
                self.devices.turn_off("internal_fan")
                self.vent_angle = 0
                self.vent_fan_speed = 0
                self.devices.set_servo_angle(0)
                self.devices.set_pwm("intake_fan", 0)
                self.devices.set_pwm("outflow_fan", 0)
                # Reset all humidity control states
                self.humidity_override_active = False
                self.humidity_override_start_time = None
                self.ventilation_phase_start_time = None
                self.humidity_control_state = False

    def _reduce_humidity_prioritized(self):
        """Prioritized approach to reduce humidity with time-based switching"""
        current_time = time.time()
        
        # Step 1: Try ventilation first (unless already in cooling phase)
        if not self.humidity_override_active:
            # Check if just starting ventilation phase
            if self.ventilation_phase_start_time is None:
                self.ventilation_phase_start_time = current_time
                print("HUMIDITY: Starting ventilation phase to reduce humidity")
            
            # Set ventilation proportional to humidity error
            self._set_ventilation_for_humidity()
            
            # Check if ventilation has been running for 2 minutes without effect
            if current_time - self.ventilation_phase_start_time >= 120:  # 2 minutes
                if not self._humidity_decreasing():
                    # Ventilation not working, move to evaporative cooling
                    self.humidity_override_active = True
                    self.humidity_override_start_time = current_time
                    self.ventilation_phase_start_time = None
                    self.vent_angle = 0
                    self.vent_fan_speed = 0
                    self.devices.set_servo_angle(0)
                    self.devices.set_pwm("intake_fan", 0)
                    self.devices.set_pwm("outflow_fan", 0)
                    print("HUMIDITY: Ventilation ineffective after 2 minutes, switching to evaporative cooling")
                else:
                    # Ventilation is working, reset timer and continue
                    self.ventilation_phase_start_time = current_time
                    print("HUMIDITY: Ventilation effective, continuing...")
            return
        
        # Step 2: Evaporative cooling phase
        if self.humidity_override_active:
            # Check if we should continue evaporative cooling
            if current_time - self.humidity_override_start_time < 180:  # 3 minutes
                if not self._humidity_decreasing():
                    # Use peltier for cooling to condense moisture
                    if not self._check_temperature_safety():  # Only if safe
                        self.devices.peltier_enable()
                        self.devices.set_peltier_pwm(1.0, "cool")  # Max cooling
                        self.devices.turn_on("peltier_fan")
                        self.devices.turn_on("water_pump")
                        self.devices.turn_off("humidifier")
                        self.devices.turn_off("internal_fan")
                        self.vent_angle = 0
                        self.vent_fan_speed = 0 
                        self.devices.set_servo_angle(0)
                        self.devices.set_pwm("intake_fan", 0)
                        self.devices.set_pwm("outflow_fan", 0)
                        print("HUMIDITY: Active evaporative cooling")
                    else:
                        print("HUMIDITY: Evaporative cooling blocked by temperature safety")
                else:
                    # Evaporative cooling is working, continue
                    print("HUMIDITY: Evaporative cooling effective")
            else:
                # Step 3: 20 minutes passed, release control and start cooldown
                self.humidity_override_active = False
                self.humidity_override_start_time = None
                self.ventilation_phase_start_time = None
                
                # Start cooldown period - wait 3 hours before trying again
                cooldown_hours = 3
                self.humidity_cooldown_until = current_time + (cooldown_hours * 3600)
                
                print(f"HUMIDITY: 20 minutes elapsed - releasing control, cooldown for {cooldown_hours} hours")
                print("HUMIDITY: Letting mushrooms absorb humidity naturally")

    def _set_ventilation_for_humidity(self):
        """Set ventilation opening proportional to humidity error with minimum opening"""
        # Calculate how much too humid we are (positive value = too humid)
        humidity_excess = max(0, self.current_humidity - self.setpoints.humidity)
        
        # Proportional control: more humidity error = more ventilation
        # Scale from minimum (30% open) to maximum (100% open) based on humidity excess
        max_humidity_excess = 15.0  # Consider 15% over setpoint as maximum
        
        # Calculate vent ratio: 0.3 (30% open) to 1.0 (100% open)
        vent_ratio = 0.3 + (min(humidity_excess, max_humidity_excess) / max_humidity_excess) * 0.7
        
        # Convert to angle (0° = closed, 180° = fully open)
        self.vent_angle = int(180 * vent_ratio)
        print(self.vent_angle)
        
        # Fan speed proportional to vent opening (minimum 30% speed)
        self.vent_fan_speed = max(0.3, vent_ratio)
        
        # Apply the changes
        self.devices.set_servo_angle(self.vent_angle)
        self.devices.set_pwm("intake_fan", self.vent_fan_speed)
        self.devices.set_pwm("outflow_fan", self.vent_fan_speed)
        
        print(f"HUMIDITY: Humidity {humidity_excess:.1f}% over setpoint, vents {vent_ratio*100:.0f}% open")

    def _humidity_decreasing(self):
        """Check if humidity shows signs of decreasing over recent readings"""
        # Store humidity history (keep last 6 readings = ~30 seconds at 5s intervals)
        if not hasattr(self, 'humidity_history'):
            self.humidity_history = []
        
        self.humidity_history.append(self.current_humidity)
        # Keep only recent history (last 6 readings)
        if len(self.humidity_history) > 6:
            self.humidity_history.pop(0)
        
        # Need at least 3 readings to determine trend
        if len(self.humidity_history) < 3:
            return True  # Not enough data, assume it's working
        
        # Calculate recent trend vs previous trend
        recent_readings = self.humidity_history[-3:]  # Last 3 readings
        previous_readings = self.humidity_history[-6:-3] if len(self.humidity_history) >= 6 else recent_readings
        
        recent_avg = sum(recent_readings) / len(recent_readings)
        previous_avg = sum(previous_readings) / len(previous_readings)
        
        # Consider it decreasing if recent average is at least 0.5% lower than previous
        return recent_avg <= (previous_avg - 0.2)
    
    def _control_co2(self):
        """Control CO2 levels - when above setpoint, reduce to 550ppm and maintain"""
        if not self.current_co2:
            return
        
        # If humidity control is actively managing ventilation, don't override it
        if self.humidity_override_active or self.ventilation_phase_start_time is not None:
            print(f"CO2: Ventilation controlled by humidity system (vent_angle: {self.vent_angle}�)")
            return
        
        with self.lock:
            # Check if we're in "reduction mode" (CO2 exceeded setpoint)
            if not hasattr(self, 'co2_reduction_mode'):
                self.co2_reduction_mode = False
            
            # Enter reduction mode if CO2 exceeds setpoint
            if self.current_co2 > self.setpoints.co2_max and not self.co2_reduction_mode:
                self.co2_reduction_mode = True
                print(f"CO2: {self.current_co2}ppm > {self.setpoints.co2_max}ppm - entering reduction mode (target: 550ppm)")
            
            # Control logic
            if self.co2_reduction_mode:
                # In reduction mode - keep reducing until we reach 550ppm
                target_co2 = 550
                current_error = self.current_co2 - target_co2
                
                if current_error > 0:  # Still above 550ppm
                    # Scale ventilation based on how much above 550ppm we are
                    max_error = 500  # Consider 500ppm above 550 as maximum
                    vent_ratio = min(1.0, current_error / max_error)
                    
                    # Apply minimum opening limit (30% open minimum)
                    min_vent_ratio = 0.3
                    vent_ratio = max(vent_ratio, min_vent_ratio)
                    
                    self.vent_angle = int(180 * vent_ratio)
                    self.vent_fan_speed = max(0.3, vent_ratio)
                    
                    self.devices.set_servo_angle(self.vent_angle)
                    self.devices.set_pwm("intake_fan", self.vent_fan_speed)
                    self.devices.set_pwm("outflow_fan", self.vent_fan_speed)
                    
                    print(f"CO2: Reduction mode - {self.current_co2}ppm > 550ppm (vents {vent_ratio*100:.0f}% open)")
                else:
                    # At or below 550ppm turn off
                    self.vent_angle = 0
                    self.vent_fan_speed = 0
                    self.devices.set_servo_angle(0)
                    self.devices.set_pwm("intake_fan", 0)
                    self.devices.set_pwm("outflow_fan", 0)
                    # self.CO2_control_state = False
                    self.co2_reduction_mode = False
                    print(f"CO2: {self.current_co2}ppm < 550ppm - exiting reduction mode")
                    
            else:  # Not in reduction mode
                # Only close vents if not needed for humidity control
                if not self.humidity_override_active:
                    self.vent_angle = 0
                    self.vent_fan_speed = 0
                    self.devices.set_servo_angle(0)
                    self.devices.turn_off("intake_fan")
                    self.devices.turn_off("outflow_fan")
                    print(f"CO2: Normal mode - {self.current_co2}ppm <= {self.setpoints.co2_max}ppm, vents closed")
    
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
                # Set NeoPixel color and intensity
                try:
                    # Fixed colours for now, could add custom RGB, would need to extend device_control
                    self.devices.set_neopixel_color(active_schedule.colour) 
                    self.devices.set_neopixel_brightness(active_schedule.neopixel_intensity)
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
        
        if self.system_start_time is None:
            uptime = 0
            self.system_start_time = time.time()

        elif self.system_start_time:
            uptime = time.time() - self.system_start_time

        with self.lock:
            return {
                "system_state": self.state.value,
                'uptime_seconds': uptime,
                'uptime': self._format_uptime(uptime),
                "setpoints": {
                    "temperature": self.setpoints.temperature,
                    "humidity": self.setpoints.humidity,
                    "co2_max": self.setpoints.co2_max,         
                    "light_schedules": [
                        {
                            "start": s.start_time.strftime("%H:%M"),
                            "end": s.end_time.strftime("%H:%M"),
                            "colour": s.colour,
                            "neopixel": s.neopixel_intensity,
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
                colour = schedule["colour"]
                neopixel = schedule.get("neopixel", 0.0)
                white = schedule.get("white", 0.0)
                uv = schedule.get("uv", 0.0)
                new_schedules.append(LightSchedule(start, end, colour,neopixel, white, uv))
            
            self.setpoints.light_schedules = new_schedules
            logger.info(f"Light schedules updated: {len(schedules)} schedules")
    
    def set_light_wavelengths(self, colour: str, neopixel_intensity: float, white_intensity: float, uv_intensity: float):
        """Set manual light wavelengths and intensities"""
        with self.lock:
            current_time = datetime.now().time()
            end_time = (datetime.now() + timedelta(hours=1)).time()
            
            temp_schedule = LightSchedule(current_time, end_time, colour, neopixel_intensity, white_intensity, uv_intensity)
            self.setpoints.light_schedules = [temp_schedule]
            
            logger.info(f"Light wavelengths set: Colour:{colour}, NeoPixel:{neopixel_intensity}, White:{white_intensity}, UV:{uv_intensity}")

    def _format_uptime(self, uptime_seconds: float) -> str:
        """Format uptime seconds to HH:MM format"""
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        return f"{hours}:{minutes:02d}"

    def trigger_photo_mode(self, duration: int = 10):
        """
        Trigger photo mode for timelapse photography
        duration: seconds to keep lights on for photo
        """
        with self.lock:
            self.photo_mode_active = True
            self.photo_mode_timeout = time.time() + duration
            
            # Turn on white LEDs for photography
            self.devices.set_pwm("white_leds",55)
            # Add some NeoPixel fill light
            self.devices.set_neopixel_brightness(0.35)
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
    
    def set_system_state(self, state: str):                     
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
chamber_controller = MushroomChamberController()  

def initialize_controller():
    """Initialize and start the controller"""
    chamber_controller.start()
    return chamber_controller

def shutdown_controller():
    """Shutdown the controller"""
    chamber_controller.stop()