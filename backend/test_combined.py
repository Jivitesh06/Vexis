import eventlet
eventlet.monkey_patch(thread=False)

import os
from flask import Flask
from flask_socketio import SocketIO
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')

cred = credentials.Certificate("firebase-service-account.json")
firebase_admin.initialize_app(cred)

@app.route('/')
def index():
    db = firestore.client()
    docs = db.collection("users").limit(1).get()
    return f"Success! Got {len(docs)} users"

if __name__ == '__main__':
    print("Starting test server on port 5001...")
    socketio.run(app, port=5001)
