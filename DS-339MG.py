from gpiozero import AngularServo
from time import sleep

servo = AngularServo(18, min_pulse_width=0.0008, max_pulse_width=0.0022)

while True:
    for angle in [-90, 0, 90]:
        print(f"Moving to {angle}")
        servo.angle = angle
        sleep(2)