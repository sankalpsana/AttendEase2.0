from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, id, role, name):
        self.id = id  # Roll number or ID number
        self.role = role  # 'student', 'faculty', or 'admin'
        self.name = name  # User's name

from app.extensions import login_manager
from flask import session

@login_manager.user_loader
def load_user(id):
    if session.get('id') == id and session.get('role'):
        return User(session.get('id'), session.get('role'), session.get('name'))
    return None
