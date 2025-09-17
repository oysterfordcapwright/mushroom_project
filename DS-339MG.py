# from gpiozero import AngularServo
# from time import sleep

# servo = AngularServo(18, min_pulse_width=0.0008, max_pulse_width=0.0022)

# while True:
#     for angle in [-90, 0, 90]:
#         print(f"Moving to {angle}")
#         servo.angle = angle
#         sleep(2)


import pigpio
from time import sleep

pi = pigpio.pi()
servo = 18  # BCM pin 18

for pulse in [1000, 1500, 2000]:  # microseconds
    print(f"Pulse {pulse}us")
    pi.set_servo_pulsewidth(servo, pulse)
    sleep(2)

pi.set_servo_pulsewidth(servo, 0)  # stop servo
pi.stop()
