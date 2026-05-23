"""Flask extension singletons, attached to the app in `create_app()`."""

from flask_socketio import SocketIO

# Bare instance — `init_app(app, ...)` is called from create_app().
socketio = SocketIO()
