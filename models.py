import os
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

# Simple user model - in production, use a database
class User(UserMixin):
    def __init__(self, id, username, password, is_admin=False):
        self.id = id
        self.username = username
        self.password = password
        self.is_admin = is_admin

    def check_password(self, password):
        return check_password_hash(self.password, password)

# Sample users - in production, store these in a database
users = [
    User(1, os.getenv("VIEWER_USER"), generate_password_hash(os.getenv("VIEWER_PASS")), False),
    User(2, os.getenv("ADMIN_USER"), generate_password_hash(os.getenv("ADMIN_PASS")), True)
]

def get_user_by_username(username):
    for user in users:
        if user.username == username:
            return user
    return None

def get_user_by_id(user_id):
    for user in users:
        if user.id == user_id:
            return user
    return None