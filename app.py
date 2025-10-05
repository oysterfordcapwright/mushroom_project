# app.py
from __init__ import create_app
import threading
from AUSDOM_cam import run_timelapse
from mushroom_controller import initialize_controller

app = create_app()

# Import your routes and models after creating app to avoid circular imports
from models import get_user_by_id

@app.login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(int(user_id))

# Global flag to track if threads were started
timelapse_started = False
controller_started = False
first_request_handled = False


@app.before_request
def start_threads():
    """Start the timelapse and controller thread on first request"""
    global first_request_handled
    if not first_request_handled:
        global timelapse_started
        global controller_started

        if not timelapse_started:
            threading.Thread(target=run_timelapse, daemon=True).start()
            timelapse_started = True

        if not controller_started:
            threading.Thread(target=initialize_controller, daemon=True).start()
            controller_started = True 
        
        first_request_handled = True


if __name__ == '__main__':
    # Note: No threads started here anymore
    # They are started by before_first_request
    app.run(host='0.0.0.0', port=8080, debug=False)