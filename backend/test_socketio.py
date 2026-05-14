import eventlet
eventlet.monkey_patch(thread=False)
from flask import Flask
from flask_socketio import SocketIO

app = Flask(__name__)
try:
    socketio = SocketIO(app, async_mode='eventlet')
    print("SocketIO initialized successfully with thread=False")
except Exception as e:
    print(f"Error: {e}")
