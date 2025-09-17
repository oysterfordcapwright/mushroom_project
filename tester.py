from rpi_hardware_pwm import HardwarePWM
import time

PWM_CHANNEL = 2
PWM_FREQ = 50
MIN_DC = 4
MAX_DC = 11
STEP = 15  # degrees per step

def angle_to_dc(angle):
    return MIN_DC + (angle / 180.0) * (MAX_DC - MIN_DC)

pwm = HardwarePWM(pwm_channel=PWM_CHANNEL, hz=PWM_FREQ, chip=0)
angle = 90
pwm.start(angle_to_dc(angle))

print("Controls: '>' to increase, '<' to decrease, 'q' to quit")

try:
    while True:
        key = input("Enter command: ")
        if key == ">":
            angle = min(180, angle + STEP)
        elif key == "<":
            angle = max(0, angle - STEP)
        elif key == "q":
            break
        else:
            continue

        pwm.change_duty_cycle(angle_to_dc(angle))
        print(f"Moved to {angle}�")

except KeyboardInterrupt:
    pass
finally:
    pwm.stop()
    print("\nServo control stopped.")


# from rpi_hardware_pwm import HardwarePWM
# import time

# # Servo parameters
# PWM_CHANNEL = 2
# PWM_FREQ = 50          # Standard servo frequency
# MIN_DC = 4           # ~0� (adjust if needed)
# MAX_DC = 11          # ~180� (adjust if needed)
# STEP = 0.01             # Step size for duty cycle change
# DELAY = 0.001           # Delay between steps (lower = faster)

# # Setup PWM
# pwm = HardwarePWM(pwm_channel=PWM_CHANNEL, hz=PWM_FREQ, chip=0)
# pwm.start(MIN_DC)  # Start at 0 degrees

# try:
#     while True:
#         # Sweep 0 -> 180
#         duty = MIN_DC
#         while duty <= MAX_DC:
#             pwm.change_duty_cycle(duty)
#             duty += STEP
#             # print(duty)
#             time.sleep(DELAY)

#         # Sweep 180 -> 0
#         duty = MAX_DC
#         while duty >= MIN_DC:
#             pwm.change_duty_cycle(duty)
#             duty -= STEP
#             # print(duty)
#             time.sleep(DELAY)

# except KeyboardInterrupt:
#     pwm.stop()
#     print("\nServo sweep stopped.")




# from gpiozero import AngularServo
# from time import sleep

# servo = AngularServo(18, min_angle=-45, max_angle=45)

# while True:

#     servo.angle = -45
#     sleep(2)
#     servo.angle = 0
#     sleep(2)
#     servo.angle = 45
#     sleep(2)



# from gpiozero import DigitalOutputDevice
# from time import sleep
# from DS18B20 import get_DS_temp
# import sys, select

# pin = DigitalOutputDevice(27)  # GPIO17 as output

# status = False

# print("Press any key + Enter to toggle pin. Ctrl+C to quit.")

# try:
#     while True:
#         print("Temp:", get_DS_temp())

#         # Check if user typed something (non-blocking)
#         if select.select([sys.stdin], [], [], 0.1)[0]:
#             sys.stdin.readline()  # clear buffer
#             if status:
#                 pin.off()
#                 print("LOW")
#                 status = False
#             else:
#                 pin.on()
#                 print("HIGH")
#                 status = True

#         sleep(0.3)
# except KeyboardInterrupt:
#     print("\nExiting program")
#     pin.off()

# print("Sending test signal on GPIO27. Press Ctrl+C to stop.")
# pin.on()   # set HIGH (3.3V)
# status = True
# print("HIGH")  

# try:
#     while True:
#         print(get_DS_temp())
        
#         if keyboard.is_pressed():  # detects any key press
#             if status:
#                 pin.off()
#                 print("LOW")
#                 status = False
#             else:
#                 pin.on()
#                 print("HIGH")
#                 status = True

#             # debounce delay so one press doesn�t toggle many times
#             sleep(0.3)
#         # pin.off()  # set LOW (0V) 
#         # print("LOW")
#         # sleep(0)

        
# except KeyboardInterrupt:
#     print("\nExiting program")

# pin.off()
