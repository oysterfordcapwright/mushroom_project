# app.py
from __init__ import create_app
import threading
from AUSDOM_cam import run_timelapse

app = create_app()

# Import your routes and models after creating app to avoid circular imports
from models import get_user_by_id

@app.login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(int(user_id))

# Global flag to track if thread was started
timelapse_started = False

@app.before_request
def start_timelapse_thread():
    """Start the timelapse thread on first request"""
    global timelapse_started
    if not timelapse_started:
        threading.Thread(target=run_timelapse, daemon=True).start()
        timelapse_started = True

if __name__ == '__main__':
    # Note: We don't start the thread here anymore
    # It will be started by before_first_request
    app.run(host='0.0.0.0', port=8080, debug=False)