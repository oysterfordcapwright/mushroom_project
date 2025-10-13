import time
import board
import adafruit_dht
import threading

# Configure the GPIO pin where your DHT22 data line is connected (pin 11 = GPIO17)

# Setup once, globally
DHT_PIN = board.D17   
dhtDevice = adafruit_dht.DHT22(DHT_PIN)

# To prevent concurrent access
_lock = threading.Lock()

def get_DHT22_data(retries=3, delay=1):
    """
    Read DHT22 data with retries if the first attempt fails.

    Args:
        retries (int): Number of times to retry if a read fails.
        delay (float): Delay in seconds between retries.

    Returns:
        dict or None: {"temperature": temp_C, "humidity": humidity} if successful, else None.
    """
    with _lock:
        attempt = 0
        while attempt < retries:
            try:
                temperature_c = dhtDevice.temperature
                humidity = dhtDevice.humidity

                if temperature_c is not None and humidity is not None:
                    return {
                        "temperature": round(temperature_c, 4),
                        "humidity": round(humidity, 4)
                    }

                # If one of them is None, treat as failed attempt
                print(f"DHT22 read returned None (attempt {attempt+1})")
            
            except RuntimeError as error:
                # Common timing errors
                print(f"DHT22 read error (attempt {attempt+1}): {error.args[0]}")
            except Exception as error:
                print(f"DHT22 unexpected error: {error}")
                return None  # Likely fatal, no retries

            attempt += 1
            time.sleep(delay)

        # All attempts failed
        print(f"DHT22 read failed after {retries} attempts")
        return None


def main():
    """Test function if running this file directly."""
    try:
        while True:
            data = get_DHT22_data()
            if data:
                print(f"Temp: {data['temperature']} \u00B0C, Humidity: {data['humidity']} %")
            else:
                print("Failed to get DHT22 data")
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nStopping...")

if __name__ == "__main__":
    main()
