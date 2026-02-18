from flask import Flask
from app.config import Config
from app.extensions import socketio, login_manager
from app.routes.auth import auth
from app.routes.admin import admin
from app.routes.faculty import faculty
from app.routes.student import student

def create_app(config_class=Config):
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object(config_class)

    # Initialize extensions
    socketio.init_app(app)
    login_manager.init_app(app)

    # Register Blueprints
    app.register_blueprint(auth)
    app.register_blueprint(admin)
    app.register_blueprint(faculty)
    app.register_blueprint(student)

    # Import events to register socket handlers
    from app import events

    return app
