import obd
import time
import threading

# socketio_ref is injected after Flask-SocketIO is created
socketio_ref = None

# ── Module-level state ─────────────────────────────────────────────
connection    = None   # obd.OBD connection object
is_connected  = False  # real or simulated connection flag
is_simulated  = False  # True when running in simulation mode
current_data  = {}     # latest OBD readings
reader_thread = None   # background polling thread

# ── OBD commands to query ──────────────────────────────────────────
OBD_COMMANDS = {
    'rpm':          obd.commands.RPM,
    'speed':        obd.commands.SPEED,
    'load':         obd.commands.ENGINE_LOAD,
    'coolant_temp': obd.commands.COOLANT_TEMP,
    'throttle_pos': obd.commands.THROTTLE_POS,
    'intake_temp':  obd.commands.INTAKE_TEMP,
    'maf':          obd.commands.MAF,
    'stft':         obd.commands.SHORT_FUEL_TRIM_1,
    'ltft':         obd.commands.LONG_FUEL_TRIM_1,
    'fuel_level':   obd.commands.FUEL_LEVEL,
    'o2_voltage':   obd.commands.O2_B1S1,
}


# ── 1. init_socketio ───────────────────────────────────────────────
def init_socketio(sio):
    global socketio_ref
    socketio_ref = sio


# ── 2. connect_obd ────────────────────────────────────────────────
def connect_obd(port=None):
    global connection, is_connected, is_simulated, current_data

    print(f"[OBD] Attempting connection{' on ' + port if port else ' (auto-detect)'}...")

    try:
        connection   = obd.OBD(port) if port else obd.OBD()
        real_connect = connection.is_connected()
    except Exception as e:
        print(f"[OBD] Hardware connect error: {e}")
        real_connect = False

    if real_connect:
        is_connected = True
        is_simulated = False
        port_name    = connection.port_name()
        print(f"[OBD] Connected on {port_name}")

        if socketio_ref:
            socketio_ref.emit('obd_status', {
                'connected': True,
                'port':      port_name,
                'message':   'OBD Scanner Connected Successfully'
            })
        start_reader_thread()
        return True

    else:
        # ── Fallback: simulation mode ──────────────────────────────
        print("[OBD] No real scanner — switching to Simulation Mode")
        is_connected = True
        is_simulated = True
        connection   = None

        if socketio_ref:
            socketio_ref.emit('obd_status', {
                'connected': True,
                'port':      'SIMULATED',
                'simulated': True,
                'message':   'Running in Simulation Mode (No real scanner detected)'
            })
        start_reader_thread()
        return True          # returns True because system is "connected" (simulated)


# ── 3. disconnect_obd ─────────────────────────────────────────────
def disconnect_obd():
    global connection, is_connected, is_simulated, current_data

    if connection:
        try:
            connection.close()
        except Exception:
            pass

    is_connected = False
    is_simulated = False
    current_data = {}
    connection   = None

    if socketio_ref:
        socketio_ref.emit('obd_status', {
            'connected': False,
            'message':   'OBD Scanner Disconnected'
        })
    print("[OBD] Disconnected")


# ── 4. read_obd_data ──────────────────────────────────────────────
def read_obd_data():
    global current_data

    # Simulated mode — delegate to simulator
    if is_simulated:
        from obd_simulator import simulate_obd_data
        current_data = simulate_obd_data()
        return current_data

    if not connection or not is_connected:
        return {}

    data = {}
    for key, cmd in OBD_COMMANDS.items():
        try:
            response = connection.query(cmd)
            if not response.is_null():
                data[key] = round(float(response.value.magnitude), 2)
            else:
                data[key] = None
        except Exception:
            data[key] = None

    # Fill sensible defaults for None values (prevents division errors)
    rpm   = data.get('rpm')         or 0
    speed = data.get('speed')       or 0
    load  = data.get('load')        or 0
    maf   = data.get('maf')         or 0
    stft  = data.get('stft')        or 0
    ltft  = data.get('ltft')        or 0
    oat   = data.get('coolant_temp') or 70

    data['oat']         = oat
    data['speed_limit'] = 60   # default speed limit

    # Derived features (mirrors compute_derived_features)
    data['maf_per_rpm']        = maf / rpm   if rpm   > 0 else 0
    data['rpm_load_ratio']     = rpm / load  if load  > 0 else 0
    data['maf_per_speed']      = maf / speed if speed > 0 else 0
    data['load_per_speed']     = load / speed if speed > 0 else 0
    data['fuel_trim_combined'] = stft + ltft
    data['fuel_trim_abs']      = abs(stft) + abs(ltft)

    current_data = data
    return data


# ── 5. reader_loop ────────────────────────────────────────────────
def reader_loop():
    while is_connected:
        try:
            data = read_obd_data()
            if data and socketio_ref:
                socketio_ref.emit('obd_data', {
                    'success':   True,
                    'data':      data,
                    'timestamp': time.time(),
                    'simulated': is_simulated
                })
        except Exception as e:
            print(f"[OBD] Read error: {e}")
            if 'disconnected' in str(e).lower():
                disconnect_obd()
                break
        time.sleep(2)


# ── 6. start_reader_thread ────────────────────────────────────────
def start_reader_thread():
    global reader_thread
    reader_thread = threading.Thread(target=reader_loop, daemon=True)
    reader_thread.start()
    mode = "SIMULATED" if is_simulated else "LIVE"
    print(f"[OBD] Background reader started ({mode})")


# ── 7. get_status ─────────────────────────────────────────────────
def get_status():
    port = None
    if connection and is_connected and not is_simulated:
        try:
            port = connection.port_name()
        except Exception:
            port = None
    elif is_simulated:
        port = 'SIMULATED'

    return {
        'connected': is_connected,
        'simulated': is_simulated,
        'port':      port,
        'data':      current_data
    }


# ── 8. get_current_data ───────────────────────────────────────────
def get_current_data():
    return current_data if is_connected else {}
