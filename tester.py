from gpiozero import LED

# Define your pins
pins = [23, 27, 13, 19, 12, 16, 20, 21]

# Create LED objects for each pin (HIGH = ON, LOW = OFF)
leds = {pin: LED(pin) for pin in pins}

def turn_on(pin):
    leds[pin].on()
    print(f"GPIO{pin} ON")

def turn_off(pin):
    leds[pin].off()
    print(f"GPIO{pin} OFF")

try:
    print("GPIO Control Interactive Mode (gpiozero)")
    print("Commands: on <pin>, off <pin>, on all, off all, exit")

    while True:
        cmd = input("Enter command: ").strip().lower()

        if cmd == "exit":
            break

        parts = cmd.split()
        if len(parts) < 2:
            print("Invalid command. Example: on 23, off 27, on all, off all")
            continue

        action, target = parts[0], parts[1]

        if target == "all":
            for p in pins:
                if action == "on":
                    turn_on(p)
                elif action == "off":
                    turn_off(p)
        else:
            try:
                pin = int(target)
            except ValueError:
                print("Pin must be a number or 'all'")
                continue

            if pin not in pins:
                print(f"Pin {pin} not in configured list {pins}")
                continue

            if action == "on":
                turn_on(pin)
            elif action == "off":
                turn_off(pin)
            else:
                print("Action must be 'on' or 'off'")

finally:
    # Turn everything off before exit
    for p in pins:
        leds[p].off()
    print("All GPIO turned off, exiting.")







# import board
# import neopixel_spi as neopixel

# # SPI setup
# pixels = neopixel.NeoPixel_SPI(board.SPI(), 10, brightness=0.2, auto_write=False)

# # Turn all pixels off
# pixels.fill((0, 0, 0))
# pixels.show()








# from gpiozero import PWMOutputDevice, DigitalOutputDevice
# import time
# from DS18B20 import get_DS_temp

# # Define pins
# LEFT_ENABLE_PIN = 25
# RIGHT_ENABLE_PIN = 8
# LEFT_PWM_PIN = 7
# RIGHT_PWM_PIN = 1

# # Setup devices
# left_enable = DigitalOutputDevice(LEFT_ENABLE_PIN)
# right_enable = DigitalOutputDevice(RIGHT_ENABLE_PIN)

# left_pwm = PWMOutputDevice(LEFT_PWM_PIN, frequency=1000)
# right_pwm = PWMOutputDevice(RIGHT_PWM_PIN, frequency=1000)

# pump_pin = DigitalOutputDevice(27)

# def set_peltier(power, direction="cool"):
#     """
#     Control Peltier power & direction.
#     power: 0.0 - 1.0 (duty cycle)
#     direction: "cool" or "heat"
#     """
#     # Both enable pins must be ON
#     left_enable.on()
#     right_enable.on()

#     if direction == "cool":
#         left_pwm.value = 0.0
#         right_pwm.value = power
#     elif direction == "heat":
#         right_pwm.value = 0.0
#         left_pwm.value = power
#     else:
#         # Stop both
#         left_pwm.value = 0.0
#         right_pwm.value = 0.0
#         left_enable.off()
#         right_enable.off()

# if __name__ == "__main__":
#     try:
#         # Ask user for mode
#         mode = input("Enter mode (cool/heat): ").strip().lower()

#         print(f"Running in {mode} mode at 100% duty cycle...")

#         pump_pin.on()

#         while True:
#             set_peltier(1.0, mode)  # Full duty cycle
#             print("Temp:", get_DS_temp())
#             time.sleep(2)

#     except KeyboardInterrupt:
#         print("Stopping...")
#         set_peltier(0)
#         pump_pin.off()








# import DS_Servo as sc
# import time

# sc.start_servos()

# try:
#     time.sleep(1)
#     sc.set_angle("output", 0)
#     time.sleep(1)
#     sc.set_angle("output", 180)
#     time.sleep(1)
#     print("Intake is at", sc.get_angle("output"))
#     time.sleep(1)
# finally:
#     sc.stop_servos()



# from rpi_hardware_pwm import HardwarePWM
# import time

# PWM_CHANNEL = 2
# PWM_FREQ = 50
# MIN_DC = 4.5    # 4.7 for out
# MAX_DC = 10     # 11 for out
# STEP = 15  # degrees per step

# def angle_to_dc(angle):
#     return MIN_DC + (angle / 180.0) * (MAX_DC - MIN_DC)

# pwm = HardwarePWM(pwm_channel=PWM_CHANNEL, hz=PWM_FREQ, chip=0)
# angle = 90
# pwm.start(angle_to_dc(angle))

# print("Controls: '>' to increase, '<' to decrease, 'q' to quit")

# try:
#     while True:
#         key = input("Enter command: ")
#         if key == ".":
#             angle = min(180, angle + STEP)
#         elif key == ",":
#             angle = max(0, angle - STEP)
#         elif key == "q":
#             break
#         else:
#             continue

#         pwm.change_duty_cycle(angle_to_dc(angle))
#         print(f"Moved to {angle}�")

# except KeyboardInterrupt:
#     pass
# finally:
#     pwm.stop()
#     print("\nServo control stopped.")


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

# pin27 = DigitalOutputDevice(27)  # GPIO27 as output

# status = False

# print("Press any key + Enter to toggle pin. Ctrl+C to quit.")

# try:
#     while True:
#         print("Temp:", get_DS_temp())

#         # Check if user typed something (non-blocking)
#         if select.select([sys.stdin], [], [], 0.1)[0]:
#             sys.stdin.readline()  # clear buffer
#             if status:
#                 pin27.off()
#                 print("LOW")
#                 status = False
#             else:
#                 pin27.on()
#                 print("HIGH")
#                 status = True

#         sleep(0.3)
# except KeyboardInterrupt:
#     print("\nExiting program")
#     pin27.off()

# print("Sending test signal on GPIO27. Press Ctrl+C to stop.")
# pin27.on()   # set HIGH (3.3V)
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
