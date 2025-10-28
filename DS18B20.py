import os
import glob
import time

base_dir = '/sys/bus/w1/devices/'

sensor_names = {
    "28-02f3d446c2fc": "Probe1",    # Bottom Probe (cold side)
    "28-3c01f0953a0b": "Probe2",    # Top Probe (hot side)
    "28-65b00087d215": "Probe3",    # Coil Probe
    
} 

def list_devices():
    """Return list of all DS18B20 device folders."""
    return glob.glob(base_dir + '28*')

def read_temp_raw(device_file):
    """Read the raw temperature data from a sensor file."""
    with open(device_file, 'r') as f:
        return f.readlines()

def read_temp(device_file):
    """Parse temperature in Celsius from a sensor's w1_slave file."""
    lines = read_temp_raw(device_file)
    # Wait until CRC is valid
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.05)
        lines = read_temp_raw(device_file)

    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = float(temp_string) / 1000.0
        return temp_c

def get_DS_temp():
    """
    Read temperatures from all connected DS18B20 sensors.
    Returns a dict {sensor_name_or_id: temperature_C}.
    """
    devices = list_devices()
    temps = {}

    for device in devices:
        device_id = os.path.basename(device)
        device_file = device + '/w1_slave'
        temp_c = read_temp(device_file)

        # Use friendly name if available, otherwise fall back to device_id
        sensor_name = sensor_names.get(device_id, device_id)
        temps[sensor_name] = round(temp_c, 2)

    return temps

def main():
    devices = list_devices()
    if not devices:
        print("No DS18B20 sensors found!")
        return
    
    print(f"Found {len(devices)} DS18B20 sensor(s):")
    for device in devices:
        print(" -", os.path.basename(device))

    try:
        while True:
            temps = get_DS_temp()
            for name, temp in temps.items():
                print(f"{name}: {temp:.2f} C")
            print("---")
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nStopping...")

if __name__ == "__main__":
    main()
    