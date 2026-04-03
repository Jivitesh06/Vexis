import eventlet
eventlet.monkey_patch()

from flask import Flask, jsonify, request, send_from_directory
import os
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from config import Config
from database import init_db
from ml.model_loader import load_models, MODELS
from routes.auth import auth_bp
from routes.predict import predict_bp
from routes.reports import reports_bp
from utils.jwt_helper import jwt_required
from obd_reader import (
    init_socketio, connect_obd, disconnect_obd,
    get_status, get_current_data
)

# ──────────────────────────────────────────────────────────────────
# App & extensions
# ──────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config.from_object(Config)

CORS(app, origins=Config.CORS_ORIGINS)

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='eventlet'
)

# Give obd_reader a reference so it can emit events
init_socketio(socketio)

# ──────────────────────────────────────────────────────────────────
# Blueprints
# ──────────────────────────────────────────────────────────────────
app.register_blueprint(auth_bp,    url_prefix='/api/auth')
app.register_blueprint(predict_bp, url_prefix='/api')
app.register_blueprint(reports_bp, url_prefix='/api')

# ──────────────────────────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────────────────────────
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status":        "ok",
        "app":           "Vexis API",
        "version":       "1.0.0",
        "models_loaded": list(MODELS.keys()),
        "models_count":  len(MODELS)
    }), 200

# ──────────────────────────────────────────────────────────────────
# Frontend static file serving
# ──────────────────────────────────────────────────────────────────
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    # API routes are handled by blueprints — this catches everything else
    if path.startswith('api/'):
        return jsonify({"error": "Not found"}), 404
    full = os.path.join(FRONTEND_DIR, path)
    if path and os.path.exists(full):
        return send_from_directory(FRONTEND_DIR, path)
    return send_from_directory(FRONTEND_DIR, 'index.html')

# ──────────────────────────────────────────────────────────────────
# OBD REST endpoints
# ──────────────────────────────────────────────────────────────────
@app.route('/api/obd/connect', methods=['POST'])
@jwt_required
def obd_connect():
    try:
        data = request.get_json() or {}
        port = data.get('port', None)
        success = connect_obd(port=port)
        return jsonify({"success": success, "status": get_status()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/obd/disconnect', methods=['POST'])
@jwt_required
def obd_disconnect():
    try:
        disconnect_obd()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/obd/status', methods=['GET'])
@jwt_required
def obd_status():
    try:
        return jsonify(get_status()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/obd/data', methods=['GET'])
@jwt_required
def obd_data():
    try:
        return jsonify({"success": True, "data": get_current_data()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ──────────────────────────────────────────────────────────────────
# WebSocket event handlers
# ──────────────────────────────────────────────────────────────────
@socketio.on('connect')
def handle_connect():
    print("[WS] Client connected")
    emit('obd_status', get_status())


@socketio.on('disconnect')
def handle_disconnect():
    print("[WS] Client disconnected")


@socketio.on('request_data')
def handle_request_data():
    emit('obd_data', {
        'success': True,
        'data':    get_current_data()
    })

# ──────────────────────────────────────────────────────────────────
# Global error handlers
# ──────────────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Route not found"}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed"}), 405

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500

# ──────────────────────────────────────────────────────────────────
# Startup
# ──────────────────────────────────────────────────────────────────
print("=" * 50)
print(" VEXIS API SERVER STARTING...")
print("=" * 50)

try:
    init_db()
    print("Database initialized successfully")
except Exception as e:
    print(f"Database init failed: {e}")
    print("App will continue without DB - check credentials")
load_models()

# ──────────────────────────────────────────────────────────────────
# Entry point — use socketio.run() (not app.run())
# ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=Config.DEBUG
    )
