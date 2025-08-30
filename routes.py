# routes.py
from flask import Blueprint, render_template, jsonify, send_from_directory, current_app
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
from __init__ import limiter
import subprocess
import ffmpeg

from CO2_sensor import read_all 
from timelapse import run_timelapse, update_latest_img, capture_img, data_lock, timelapse_data

bp = Blueprint('main', __name__)

# Admin required decorator
def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            return "Admin access required", 403
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
@login_required
def index():
    return render_template('index.html')

@bp.route('/take_clip')
@admin_required
def take_clip():
    try:
        subprocess.run(['python3', current_app.config['UPDATE_CLIP_FILENAME']], check=True)
        return "Clip recorded and uploaded successfully!"
    except subprocess.CalledProcessError:
        return "Error: Could not take clip or upload."
        
@bp.route('/co2_sensor')
@login_required
def co2_sensor():
    try:
        data = read_all()
        return {
            "co2": data["co2"],
            "temperature": data["temperature"],
        }
    except Exception as e:
        return {"error": str(e)}, 500

@bp.route('/send_latest_image')
@login_required
def send_latest_image():
    return send_from_directory(current_app.config['CURR_IMG_DIR'], current_app.config['LATEST_IMG'])

@bp.route('/get_timestamp')
@login_required
def get_timestamp():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return jsonify(timestamp)

@bp.route('/take_photo')
@admin_required
def take_photo():
    try:
        frame = capture_img()
        update_latest_img(frame)
        return jsonify({"success" : True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    
@bp.route('/upload_tl')
@admin_required
def upload_tl():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output_file = f"/home/luke/Videos/Timelapse/timelapse {timestamp}.mp4"
    (
        ffmpeg
        .input("/home/luke/Pictures/Timelapse Images/*.jpg", pattern_type="glob", framerate=5)
        .output(output_file, vcodec="libx264")
        .run()
    )
    try:
        subprocess.run(['rclone', 'copy', output_file, current_app.config['TL_DRIVE_FOLDER']], check=True)
    except subprocess.CalledProcessError as e:
        print(e)
        return str(e)
    
    return 'Complete'
    
@bp.route("/timelapse_status")
@login_required
def timelapse_status():
    with data_lock:
        return jsonify(timelapse_data)

# Placeholder routes for future functionality - all require admin access

@bp.route('/toggle_tl')
@admin_required
def toggle_tl():
    return " coming soon!"
    
@bp.route('/restart_tl')
@admin_required
def restart_tl():
    return " coming soon!"
    
@bp.route('/set_tl_rate')
@admin_required
def set_tl_rate():
    return " coming soon!"

@bp.route('/adjust_temp')
@admin_required
def adjust_temp():
    return "Temperature adjustment coming soon!"

@bp.route('/adjust_humidity')
@admin_required
def adjust_humidity():
    return "Humidity adjustment coming soon!"

@bp.route('/toggle_fan')
@admin_required
def toggle_fan():
    return "Fan control coming soon!"

@bp.route('/toggle_light')
@admin_required
def toggle_light():
    return "Light control coming soon!"

@bp.route('/set_light_schedule')
@admin_required
def set_light_schedule():
    return "Light scheduling coming soon!"

@bp.route('/emergency_stop')
@admin_required
def emergency_stop():
    return "Emergency stop functionality coming soon!"

@bp.route('/update_settings')
@admin_required
def update_settings():
    return "Settings update coming soon!"

@bp.route('/view_logs')
@admin_required
def view_logs():
    return "System logs coming soon!"
