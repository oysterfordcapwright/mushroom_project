# routes.py
from flask import Blueprint, render_template, jsonify, send_from_directory, send_file, current_app, request
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
from __init__ import limiter
import subprocess
import ffmpeg
import os

from AUSDOM_cam import update_latest_img, capture_img, data_lock, timelapse_data, toggle_timelapse, set_tl_interval
from mushroom_controller import chamber_controller, SystemState

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
        

# Sensor routes to using the controller
@bp.route('/DS18B20_sensor')
@login_required
def DS18B20_sensor():
    """Get temperature data from controller"""
    try:
        sensor_data = chamber_controller.get_sensor_data()
        return jsonify(sensor_data["temperatures"])
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    

@bp.route('/DHT22_sensor')
@login_required
def DHT22_sensor():
    """Get humidity data from controller"""
    try:
        sensor_data = chamber_controller.get_sensor_data()
        return jsonify({"humidity": sensor_data["humidity"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/co2_sensor')
@login_required
def co2_sensor():
    """Get CO2 data from controller"""
    sensor_data = chamber_controller.get_sensor_data()
    return jsonify({"co2": sensor_data["co2"]})

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
    
# .output(output_file, vcodec="libx264")    
@bp.route('/upload_tl')
@admin_required
def upload_tl():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output_file = f"/home/luke/Videos/Timelapse/timelapse {timestamp}.mp4"
    (
        ffmpeg
        .input("/home/luke/Pictures/Timelapse Images/*.jpg", pattern_type="glob", framerate=30)
        .output(
                output_file, 
                vcodec="libx264",
                crf=28, 
                preset="medium", 
                pix_fmt="yuv420p" 
            )
        .run(quiet=True)
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

@bp.route('/toggle_tl')
@admin_required
def toggle_tl():
    return toggle_timelapse()
    
@bp.route('/restart_tl')
@admin_required
def restart_tl():
    return " coming soon!"
    
@bp.route('/set_tl_rate/<int:interval>', methods=['POST'])  
@admin_required
def set_tl_rate(interval):
    """Set timelapse interval lengths"""
    set_tl_interval(interval)
    return jsonify({"status": "success", "interval": interval})

# Flask
@bp.route('/update_setpoints', methods=['POST']) 
@admin_required
def update_setpoints():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400
    
    try:
        updated_params = {}
        
        if "temperature" in data:
            chamber_controller.set_temperature(float(data["temperature"]))
            updated_params["temperature"] = data["temperature"]
            
        if "humidity" in data:
            chamber_controller.set_humidity(float(data["humidity"]))
            updated_params["humidity"] = data["humidity"]
            
        if "co2_max" in data: 
            chamber_controller.set_co2_level(float(data["co2_max"])) 
            updated_params["co2_max"] = data["co2_max"]
            
        if "light_schedules" in data: 
            chamber_controller.set_light_schedule(data["light_schedules"])
            updated_params["light_schedules"] = len(data["light_schedules"])

        return jsonify({
            "status": "success", 
            "message": "Setpoints updated successfully",
            "updated_parameters": updated_params
        })
        
    except (ValueError, KeyError) as e:
        return jsonify({"status": "error", "message": f"Invalid input: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

    """Set CO2 level"""
    try:
        co2_max = float(request.json.get('co2_max'))
        chamber_controller.set_co2_level(co2_max)
        return jsonify({"status": "success", "co2_max": co2_max})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@bp.route('/set_light_schedule', methods=['POST'])
@admin_required
def set_light_schedule():
    """Set light schedule"""
    try:
        schedules = request.json.get('schedules', [])
        chamber_controller.set_light_schedule(schedules)
        return jsonify({"status": "success", "schedules": schedules})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@bp.route('/set_light_wavelength', methods=['POST'])
@admin_required
def set_light_wavelength():
    """Set light wavelengths"""
    try:
        rgb = tuple(request.json.get('rgb', (255, 255, 255)))
        white = float(request.json.get('white', 0.8))
        uv = float(request.json.get('uv', 0.1))
        chamber_controller.set_light_wavelengths(rgb, white, uv)
        return jsonify({"status": "success", "rgb": rgb, "white": white, "uv": uv})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@bp.route('/emergency_stop')
@admin_required
def emergency_stop():
    """Emergency stop everything"""
    chamber_controller.emergency_stop()
    return "Emergency stop activated"

@bp.route('/control_status')
@login_required
def control_status():
    """Get control system status"""
    status = chamber_controller.get_control_status()
    return jsonify(status)

@bp.route('/toggle_lights', methods=['POST'])
@admin_required
def toggle_lights():
    """Toggle lights on/off manually"""
    try:
        return jsonify({
            "status": "success", 
            "message": "Lights toggled",
            "lights_on": True
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@bp.route('/trigger_photo_mode', methods=['POST'])
@admin_required
def trigger_photo_mode():
    """Trigger photo mode for timelapse"""
    try:
        data = request.get_json()
        duration = data.get('duration', 5)
        chamber_controller.trigger_photo_mode(duration)
        return jsonify({
            "status": "success", 
            "message": f"Photo mode activated for {duration} seconds"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@bp.route('/download_logs')
@login_required
def download_logs():
    """Download the system data log as CSV"""
    try:
        log_file = "/home/luke/mushroom_project/mushroom_chamber_data.csv"
        if os.path.exists(log_file):
            return send_file(log_file, as_attachment=True, download_name='mushroom_chamber_data.csv')
        else:
            return jsonify({"error": "No log file found"}), 404
    except Exception as e:
        return jsonify({"error": f"Error downloading logs: {str(e)}"}), 500
    

@bp.route('/toggle_system_state', methods=['POST'])
@admin_required
def toggle_system_state():
    """Toggle between active and standby states"""
    try:
        current_state = chamber_controller.state
        new_state = SystemState.STANDBY if current_state == SystemState.ACTIVE else SystemState.ACTIVE
        chamber_controller.set_system_state(new_state.value)
        
        return jsonify({
            "status": "success",
            "message": f"System {new_state.value}",
            "new_state": new_state.value
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400