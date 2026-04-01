"""
obd_reader.py — Lightweight OBD stub for cloud deployment.

Real OBD communication is handled in the browser via the
Web Serial API (obd_serial.js). This module only provides
stub functions so app.py keeps working without the python-obd
library, and exposes update_data() for the /api/obd/agent-data
endpoint to receive data pushed from the frontend.
"""

import time
import threading

# ── Module state ───────────────────────────────────────────────────
is_connected  = False
current_data  = {}
socketio_ref  = None


# ── 1. init_socketio ──────────────────────────────────────────────
def init_socketio(sio):
    global socketio_ref
    socketio_ref = sio


# ── 2. connect_obd (stub) ─────────────────────────────────────────
def connect_obd(port=None):
    """
    No-op on the server side.
    Connection is handled by the browser via Web Serial API.
    """
    return True


# ── 3. disconnect_obd ─────────────────────────────────────────────
def disconnect_obd():
    global is_connected, current_data
    is_connected = False
    current_data = {}
    if socketio_ref:
        socketio_ref.emit('obd_status', {
            'connected': False,
            'message':   'Disconnected'
        })


# ── 4. get_status ─────────────────────────────────────────────────
def get_status():
    return {
        'connected': is_connected,
        'port':      None,
        'data':      current_data
    }


# ── 5. get_current_data ──────────────────────────────────────────
def get_current_data():
    return current_data


# ── 6. update_data ───────────────────────────────────────────────
def update_data(data):
    """
    Called by /api/obd/agent-data when the frontend pushes
    a batch of OBD readings collected via Web Serial API.
    """
    global current_data, is_connected
    current_data = data
    is_connected = True
    if socketio_ref:
        socketio_ref.emit('obd_data', {
            'success': True,
            'data':    data,
            'source':  'web_serial'
        })
