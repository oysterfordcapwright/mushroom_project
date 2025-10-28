# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    UPDATE_CLIP_FILENAME = '/home/luke/Desktop/Useful Scripts/Take Clip and Upload to Drive.py'
    RCLONE_REMOTE = "google_drive"
    RCLONE_PATH = ""
    CURR_IMG_DIR = "/home/luke/Pictures/Latest Image"
    LATEST_IMG = "latest.jpg"
    TL_DRIVE_FOLDER = "google_drive:/Videos"