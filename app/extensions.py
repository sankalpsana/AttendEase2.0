from flask_socketio import SocketIO
from flask_login import LoginManager

socketio = SocketIO(cors_allowed_origins="*")
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
