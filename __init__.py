# __init__.py
from flask import Flask
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config
import os

# Initialize extensions without app
login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address)

def create_app():
    # Create app
    app = Flask(__name__)
    
    app.config.from_object(Config)

    app.secret_key = os.environ.get('SECRET_KEY', 'dev-fallback-key')

    # Initialize extensions with app
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    limiter.init_app(app)
    
    # Register blueprints
    from auth import auth_bp
    app.register_blueprint(auth_bp)
    
    # Import and register routes
    import routes
    app.register_blueprint(routes.bp)
    
    return app