import cv2
import time
import os
from datetime import datetime
from threading import Lock, Event 

try:
    from mushroom_controller import chamber_controller
    CONTROLLER_AVAILABLE = True
except ImportError:
    CONTROLLER_AVAILABLE = False
    print("Mushroom controller not available")

# === Settings ===
TIME_LAP_DIR = "/home/luke/Pictures/Timelapse Images"
CURR_IMG_DIR = "/home/luke/Pictures/Latest Image"
DEF_TIM_LAP_INTERVAL = 300      # Time (s) between photos (5min) = roughly 10seconds per day
CAM_INDEX = 0                   
LATEST_IMG = "latest.jpg"
RESOLUTION_W = 1920
RESOLUTION_H = 1080
MAX_RETRIES = 4                # Number of retries for failed captures
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

# Global camera instance
camera_instance = None
camera_lock = Lock()

# New: Pause flag
pause_event = Event()
pause_event.clear()  


data_lock = Lock()


# Create time lapse directory if it doesn't exist
os.makedirs(TIME_LAP_DIR, exist_ok=True)
os.makedirs(CURR_IMG_DIR, exist_ok=True)

class CaptureError(Exception):
    """Custom exception for capture failures"""
    pass

def print_camera_settings(cap):
    """Print current camera settings for debugging"""
    try:
        print("Camera Settings:")
        print(f"  Auto Focus: {cap.get(cv2.CAP_PROP_AUTOFOCUS)}")
        print(f"  Focus: {cap.get(cv2.CAP_PROP_FOCUS)}")
        print(f"  Auto Exposure: {cap.get(cv2.CAP_PROP_AUTO_EXPOSURE)}")
        print(f"  Exposure: {cap.get(cv2.CAP_PROP_EXPOSURE)}")
        print(f"  Brightness: {cap.get(cv2.CAP_PROP_BRIGHTNESS)}")
        print(f"  Contrast: {cap.get(cv2.CAP_PROP_CONTRAST)}")
    except Exception as e:
        print(f"Could not read camera settings: {e}")

def initialize_camera():
    """Initialize and configure the camera once"""
    global camera_instance
    
    with camera_lock:
        if camera_instance is not None:
            # print_camera_settings(camera_instance)
            return camera_instance
            
        cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_V4L2)
        if not cap.isOpened():
            raise CaptureError("Could not open webcam")
        
        # Set resolution
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, RESOLUTION_W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, RESOLUTION_H)
        
        # Set manual focus for consistency
        try:
            cap.set(cv2.CAP_PROP_AUTOFOCUS, 0) 
            cap.set(cv2.CAP_PROP_FOCUS, 15)   
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1) 
            cap.set(cv2.CAP_PROP_EXPOSURE, 30)  
            cap.set(cv2.CAP_PROP_BRIGHTNESS, 140)  
            cap.set(cv2.CAP_PROP_AUTO_WB, 0)  
            cap.set(cv2.CAP_PROP_WB_TEMPERATURE, 5800)
        except:
            print("Warning: Could not set manual focus - using default")
        
        # Verify resolution was set correctly
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if actual_w != RESOLUTION_W or actual_h != RESOLUTION_H:
            cap.release()
            raise CaptureError(f"Failed to set resolution. Requested {RESOLUTION_W}x{RESOLUTION_H}, got {actual_w}x{actual_h}")
        
        # Warm up camera with a dummy read
        for _ in range(1):
            cap.read()
            time.sleep(0.1)
        
        camera_instance = cap
        print("Camera initialized and ready")
        print_camera_settings(cap)
        return camera_instance

def close_camera():
    """Close the camera instance"""
    global camera_instance
    with camera_lock:
        if camera_instance is not None:
            camera_instance.release()
            camera_instance = None
            print("Camera closed")

def capture_img():
    """Capture image using the persistent camera instance"""
    for attempt in range(MAX_RETRIES):
        try:
            if CONTROLLER_AVAILABLE:
                chamber_controller.trigger_photo_mode(duration=1) 
                time.sleep(0.3)
            
            cap = initialize_camera()
            
            with camera_lock:
                if not cap.isOpened():
                    # Try to reinitialize if camera closed unexpectedly
                    close_camera()
                    cap = initialize_camera()
                    if not cap.isOpened():
                        raise CaptureError("Error: Could not open webcam.")
                
                ret, frame = cap.read()
                
                if not ret:
                    # Try one more read if first fails
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
            
            # If camera error, try to reset camera
            if "camera" in str(e).lower() or "webcam" in str(e).lower():
                close_camera()
                time.sleep(1) 
                
            time.sleep(RETRY_DELAY)
    
    raise CaptureError("Unexpected error in capture_img")

def update_latest_img(frame):
    """Update the latest image file"""
    curr_img_filepath = os.path.join(CURR_IMG_DIR, LATEST_IMG)
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
    """Main timelapse loop"""
    # Initialize camera at startup
    try:
        initialize_camera()
    except Exception as e:
        print(f"Warning: Camera initialization failed: {e}")
    
    # Set paused state by default at startup
    pause_event.set()  # Start in paused state
    
    initial_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with data_lock:
        timelapse_data["start_timestamp"] = initial_timestamp
        timelapse_data["status"] = "paused" 
        
    print(f"Timelapse started in PAUSED state")
    
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
            
            update_latest_img(frame)
            
            with data_lock:
                timelapse_data["iterations"] += 1
                timelapse_data["last_timestamp"] = timestamp

            # Wait before next capture
            time.sleep(timelapse_data["interval"])
            
    except KeyboardInterrupt:
        print("\nTimelapse stopped by user.")
    except Exception as e:
        print(f"Timelapse error: {e}")
    finally:
        # Always close camera on exit
        close_camera()
        print("Timelapse stopped")

if __name__ == "__main__":
    run_timelapse()