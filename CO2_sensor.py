from datetime import datetime
import serial
import time

DEVICE_PATH = "/dev/serial0"

def current_time():
    now = datetime.now()
    return now.strftime('%Y-%m-%d %H:%M:%S')

def connect():
    return serial.Serial(DEVICE_PATH, baudrate=9600, timeout=3.0)

def get_CO2_data():
    with connect() as ser:
        ser.write(b"\xff\x01\x86\x00\x00\x00\x00\x00\x79")
        r = ser.read(9)

        if len(r) == 9 and r[0] == 0xff and r[1] == 0x86:
            return {"time": current_time(),
                    "co2": r[2]*256 + r[3],
                    "temperature": r[4] - 40,
                    "TT": r[4], # raw temperature
                    "SS": r[5], # status?
                    "Uh": r[6], # ticks in calibration cycle?
                    "Ul": r[7]} # number of performed calibrations?
        else:
            raise Exception("Got unexpected answer from CO2 sensor %s" % r)

def get_CO2_ppm():
    data = get_CO2_data()
    return data["co2"]

def disable_abc_permanently():
    """Permanently disable ABC - survives power cycles"""
    with connect() as ser:
        # Command to turn off ABC (0x00 in byte3)
        ser.write(b"\xff\x01\x79\x00\x00\x00\x00\x00\x86")
        print("ABC permanently disabled - will remain off after power cycles")


if __name__ == "__main__":

    try:
        disable_abc_permanently()
        time.sleep(0.1)
        while True:
            result = get_CO2_data()
            if result:
                cur_time, co2, temp, tt, ss, uh, ul = result
                #print(f"CO2: {co2} ppm, Temp: {temp} C")
                print(result)
            else:
                print("Read error")
            time.sleep(2)
    except KeyboardInterrupt:
        print("Exiting")

