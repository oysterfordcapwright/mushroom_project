from flask import Flask, jsonify, request
from mushroom_controller import chamber_controller, initialize_controller, shutdown_controller
import threading
import atexit

app = Flask(__name__)

# Initialize controller when module loads
print("Initializing mushroom chamber controller...")
controller_thread = threading.Thread(target=initialize_controller, daemon=True)
controller_thread.start()

# Ensure clean shutdown
atexit.register(shutdown_controller)

@app.route('/')
def index():
    """Simple status page without templates"""
    status = chamber_controller.get_system_status()
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Mushroom Chamber Control</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .card {{ border: 1px solid #ccc; padding: 15px; margin: 10px 0; border-radius: 5px; }}
            .status {{ background-color: #f0f0f0; }}
            .readings {{ background-color: #e6f7ff; }}
            .controls {{ background-color: #f9f9f9; }}
            button {{ padding: 8px 15px; margin: 5px; }}
            input {{ padding: 5px; margin: 5px; }}
        </style>
    </head>
    <body>
        <h1>Mushroom Chamber Control System</h1>
        
        <div class="card status">
            <h2>System Status: {status['system_state']}</h2>
            <p><strong>Last Updated:</strong> {status.get('timestamp', 'N/A')}</p>
        </div>
        
        <div class="card readings">
            <h2>Current Readings</h2>
            <p><strong>Temperatures:</strong> {status['current_readings']['temperatures']}</p>
            <p><strong>Humidity:</strong> {status['current_readings']['humidity']}%</p>
            <p><strong>CO2:</strong> {status['current_readings']['co2']} ppm</p>
        </div>
        
        <div class="card">
            <h2>Setpoints</h2>
            <p><strong>Temperature:</strong> {status['setpoints']['temperature']}�C</p>
            <p><strong>Humidity:</strong> {status['setpoints']['humidity']}%</p>
            <p><strong>CO2 Max:</strong> {status['setpoints']['co2_max']} ppm</p>
        </div>
        
        <div class="card controls">
            <h2>Quick Controls</h2>
            <p><a href="/api/status">View Full Status JSON</a></p>
            <p><a href="/api/errors">View Errors</a></p>
        </div>
    </body>
    </html>
    """
    return html

@app.route('/api/status')
def get_status():
    """Get complete system status"""
    status = chamber_controller.get_system_status()
    return jsonify(status)

@app.route('/api/setpoints', methods=['GET', 'POST'])
def handle_setpoints():
    """Get or update setpoints"""
    if request.method == 'POST':
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "No JSON data provided"}), 400
                
            chamber_controller.update_setpoints(**data)
            return jsonify({"message": "Setpoints updated successfully"})
        except Exception as e:
            return jsonify({"error": str(e)}), 400
    else:
        status = chamber_controller.get_system_status()
        return jsonify(status["setpoints"])

@app.route('/api/photo', methods=['POST'])
def trigger_photo():
    """Trigger photo mode for timelapse"""
    try:
        data = request.get_json() or {}
        duration = data.get('duration', 30)
        chamber_controller.trigger_photo_mode(duration)
        return jsonify({"message": f"Photo mode activated for {duration} seconds"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/pid', methods=['GET', 'POST'])
def handle_pid():
    """Get or update PID parameters"""
    if request.method == 'POST':
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "No JSON data provided"}), 400
                
            chamber_controller.update_pid_parameters(
                kp=data.get('kp'),
                ki=data.get('ki'),
                kd=data.get('kd')
            )
            return jsonify({"message": "PID parameters updated"})
        except Exception as e:
            return jsonify({"error": str(e)}), 400
    else:
        pid_params = chamber_controller.get_pid_parameters()
        return jsonify(pid_params)

@app.route('/api/state', methods=['POST'])
def set_state():
    """Change system state"""
    try:
        data = request.get_json()
        if not data or 'state' not in data:
            return jsonify({"error": "No state provided"}), 400
            
        state = data.get('state')
        chamber_controller.set_system_state(state)
        return jsonify({"message": f"System state changed to {state}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/errors')
def get_errors():
    """Get recent errors"""
    status = chamber_controller.get_system_status()
    return jsonify(status["errors"])

if __name__ == '__main__':
    print("Starting Flask server on http://0.0.0.0:5000")
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        shutdown_controller()