#!/usr/bin/env python3
"""
Peltier Module Controller for Flask Integration
"""

import time
import logging
from typing import Optional
import threading
import RPi.GPIO as GPIO

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("peltier_controller")

class PIDController:
    """Simple PID Controller implementation"""
    
    def __init__(self, kp: float, ki: float, kd: float, output_limits: tuple = (0, 100)):
        self.kp = kp
        self.ki = ki  
        self.kd = kd
        self.output_limits = output_limits
        
        self.integral = 0
        self.previous_error = 0
        self.previous_time = None
        
    def compute(self, setpoint: float, current_value: float, current_time: Optional[float] = None) -> float:
        if current_time is None:
            current_time = time.time()
            
        error = setpoint - current_value
        
        if self.previous_time is None:
            dt = 0
        else:
            dt = current_time - self.previous_time
            
        p_term = self.kp * error
        self.integral += error * dt
        i_term = self.ki * self.integral
        
        if dt > 0:
            d_term = self.kd * (error - self.previous_error) / dt
        else:
            d_term = 0
        
        output = p_term + i_term + d_term
        output = max(self.output_limits[0], min(self.output_limits[1], output))
        
        self.previous_error = error
        self.previous_time = current_time
        
        return output

class PeltierController:
    def __init__(self, gpio_pin: int = 18, pwm_frequency: int = 1000):
        self.gpio_pin = gpio_pin
        self.pwm_frequency = pwm_frequency
        self.setpoint = 22.0  # Default setpoint
        self.current_temp = 0.0
        self.is_running = False
        self.control_thread = None
        
        # PID parameters (tune these)
        self.pid = PIDController(kp=5.0, ki=0.1, kd=0.5, output_limits=(0, 100))
        
        self.setup_gpio()
        logger.info(f"Peltier controller initialized on GPIO {gpio_pin}")
    
    def setup_gpio(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.gpio_pin, GPIO.OUT)
        self.pwm = GPIO.PWM(self.gpio_pin, self.pwm_frequency)
        self.pwm.start(0)
    
    def set_setpoint(self, temperature: float):
        if 0 <= temperature <= 50:
            self.setpoint = temperature
            logger.info(f"Setpoint changed to {temperature} C")
            return True
        else:
            logger.warning(f"Setpoint {temperature} C is outside valid range")
            return False
    
    def get_setpoint(self):
        return self.setpoint
    
    def update_temperature(self, temperature: float):
        self.current_temp = temperature
    
    def get_current_temp(self):
        return self.current_temp
    
    def get_output_level(self):
        if hasattr(self, 'current_output'):
            return self.current_output
        return 0
    
    def control_loop(self):
        while self.is_running:
            try:
                output = self.pid.compute(self.setpoint, self.current_temp, time.time())
                duty_cycle = max(0, min(100, output))
                self.current_output = duty_cycle
                
                self.pwm.ChangeDutyCycle(duty_cycle)
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in control loop: {e}")
                time.sleep(1)
    
    def start(self):
        if not self.is_running:
            self.is_running = True
            self.control_thread = threading.Thread(target=self.control_loop, daemon=True)
            self.control_thread.start()
            logger.info("Peltier controller started")

    def stop(self):
        if self.is_running:
            self.is_running = False
            if self.control_thread:
                self.control_thread.join(timeout=2.0)
            self.pwm.ChangeDutyCycle(0)
            logger.info("Peltier controller stopped")
    
    def cleanup(self):
        self.stop()
        self.pwm.stop()
        GPIO.cleanup()

# Global instance
peltier_controller = None

def init_peltier_controller(gpio_pin=18):
    global peltier_controller
    if peltier_controller is None:
        peltier_controller = PeltierController(gpio_pin=gpio_pin)
        peltier_controller.start()
    return peltier_controller

def get_peltier_controller():
    global peltier_controller
    return peltier_controller