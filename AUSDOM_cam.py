import cv2
import time
import os
from datetime import datetime
from threading import Lock, Event 

# === Settings ===
TIME_LAP_DIR = "/home/luke/Pictures/Timelapse Images"
CURR_IMG_DIR = "/home/luke/Pictures/Latest Image"
DEF_TIM_LAP_INTERVAL = 8           # Time (s) between photos (10min)
CAM_INDEX = 0                   # Usually 0, change if you have multiple cameras
LATEST_IMG = "latest.jpg"
RESOLUTION_W = 1920
RESOLUTION_H = 1080
MAX_RETRIES = 4                 # Number of retries for failed captures
RETRY_DELAY = 1                # Seconds to wait between retries

# Overlay timestamp onto the image
FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 1
COLOR = (0, 255, 0)   # green text
THICKNESS = 2
def POSITION(frame): return (10, frame.shape[0] - 10)  # bottom-left corner

# For sharing data between threads
timelapse_data = {
    "status": None,
    "iterations": 0,
    "last_timestamp": None,
    "start_timestamp": None,
    "interval": DEF_TIM_LAP_INTERVAL
}


# New: Pause flag
pause_event = Event()
pause_event.clear()  # not paused at start


data_lock = Lock()


# Create time lapse directory if it doesn't exist
os.makedirs(TIME_LAP_DIR, exist_ok=True)
os.makedirs(CURR_IMG_DIR, exist_ok=True)


class CaptureError(Exception):
    """Custom exception for capture failures"""
    pass


def initialize_camera():
    """Initialize and configure the camera"""
    cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_V4L2)
    if not cap.isOpened():
        raise CaptureError("Could not open webcam")
    
    # Set resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, RESOLUTION_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, RESOLUTION_H)
    
    # Verify resolution was set correctly
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if actual_w != RESOLUTION_W or actual_h != RESOLUTION_H:
        cap.release()
        raise CaptureError(f"Failed to set resolution. Requested {RESOLUTION_W}x{RESOLUTION_H}, got {actual_w}x{actual_h}")
    
    return cap


def capture_img():
    
    for attempt in range(MAX_RETRIES):
        cap = None
        try:
            cap = initialize_camera()
            if not cap.isOpened():
                raise CaptureError("Error: Could not open webcam.")
                
            ret, frame = cap.read()
            
            if not ret:
                raise CaptureError("Failed to capture image")
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(frame, timestamp, POSITION(frame), FONT, FONT_SCALE, COLOR, THICKNESS, cv2.LINE_AA)
            return frame
            
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt == MAX_RETRIES - 1:
                raise CaptureError(f"Failed after {MAX_RETRIES} attempts: {str(e)}")
            time.sleep(RETRY_DELAY)
            
        finally:
            if cap is not None:
                cap.release()
    
    raise CaptureError("Unexpected error in capture_img")
    

def update_latest_img(frame):

    # Create filename with timestamp
    curr_img_filepath = os.path.join(CURR_IMG_DIR, LATEST_IMG)
    
    # Update latest image
    cv2.imwrite(curr_img_filepath, frame)

    return True    
        
        
def toggle_timelapse():
    """Toggle between paused and running"""
    if pause_event.is_set():
        pause_event.clear()
        print("Timelapse resumed.")
        with data_lock:
            timelapse_data["status"] = "running"
        return "running"
    else:
        pause_event.set()
        print("Timelapse paused.")
        with data_lock:
            timelapse_data["status"] = "paused"
        return "paused"

def set_tl_interval(time_s):
    with data_lock:
        timelapse_data["interval"] = time_s


def run_timelapse():
    
    intial_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with data_lock:
        timelapse_data["start_timestamp"] = intial_timestamp
        timelapse_data["status"] = "running"
        
    print(f"Timelapse running")
    try:
        while True:

            while pause_event.is_set():
                time.sleep(1)
            
            frame = capture_img()
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Create filename with timestamp
            filename = timestamp + ".jpg"
            tim_lap_filepath = os.path.join(TIME_LAP_DIR, filename)
            
            cv2.imwrite(tim_lap_filepath, frame)
            #print(f"Saved {filename} to Time Lapse Pictures")
            
            update_latest_img(frame)
            #print(f"Updated Current Image")
            
            with data_lock:
                timelapse_data["iterations"] += 1
                timelapse_data["last_timestamp"] = timestamp

            # Wait before next capture
            time.sleep(timelapse_data["interval"])

            
    except KeyboardInterrupt:
        print("\nTimelapse stopped by user.")

    print(f"Timelapse stopped")


if __name__ == "__main__":
    run_timelapse()
