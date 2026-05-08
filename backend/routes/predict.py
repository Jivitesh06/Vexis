from flask import Blueprint, request, jsonify
from utils.firebase_auth import firebase_required, get_or_create_user
from utils.validators import validate_obd_input
from ml.model_loader import predict_health
from database import execute_query
from config import Config
import json
import random
import statistics
from collections import Counter

predict_bp = Blueprint('predict', __name__)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# POST /predict  [jwt_required]
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@predict_bp.route('/predict', methods=['POST'])
@firebase_required
def predict():
    try:
        data = request.get_json()

        # 1. Validate OBD input fields
        valid, error = validate_obd_input(data)
        if not valid:
            return jsonify({"error": error}), 400

        # 2. Run ML prediction
        result = predict_health(data)
        if "error" in result:
            return jsonify({"error": result["error"]}), 500

        # 3. Persist report to database
        failure_risk = 1 if result['health_category'] in ['Poor', 'Critical'] else 0

        # Get DB user_id
        db_user = get_or_create_user(request.user['uid'], request.user['email'])
        user_id = db_user['id']

        execute_query(
            """
            INSERT INTO reports
                (user_id, engine_score, fuel_score, stress_score,
                 overall_score, failure_risk, status_label, raw_input, issues)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                result['engine_score'],
                result['fuel_score'],
                result['driving_score'],       # driving â†” stress
                result['overall_score'],
                failure_risk,
                result['health_category'],
                json.dumps(data),
                json.dumps(result['issues'])
            ),
            commit=True
        )

        # 4. Return prediction response
        return jsonify({
            "success": True,
            "scores": {
                "engine":     result['engine_score'],
                "fuel":       result['fuel_score'],
                "efficiency": result['efficiency_score'],
                "driving":    result['driving_score'],
                "thermal":    result['thermal_score'],
                "overall":    result['overall_score']
            },
            "health_category":   result['health_category'],
            "issues":            result['issues'],
            "component_weights": result['component_weights']
        }), 200

    except Exception as e:
        print(f"[predict error] {e}")
        return jsonify({"error": "Prediction failed"}), 500


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# GET /live-metrics  [jwt_required]
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@predict_bp.route('/live-metrics', methods=['GET'])
@firebase_required
def live_metrics():
    try:
        metrics = {
            "rpm":             random.randint(700, 3500),
            "speed":           random.randint(0, 120),
            "load":            round(random.uniform(20, 80), 1),
            "maf":             round(random.uniform(2, 25), 2),
            "stft":            round(random.uniform(-8, 8), 2),
            "ltft":            round(random.uniform(-5, 5), 2),
            "oat":             round(random.uniform(20, 95), 1),
            "speed_limit":     60,
            "coolant_temp":    round(random.uniform(70, 105), 1),
            "throttle_pos":    round(random.uniform(10, 70), 1),
            "intake_air_temp": round(random.uniform(25, 55), 1)
        }
        return jsonify({"success": True, "metrics": metrics}), 200

    except Exception as e:
        print(f"[live-metrics error] {e}")
        return jsonify({"error": "Failed"}), 500


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# POST /predict/live  [jwt_required]  â€” uses live OBD data
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@predict_bp.route('/predict/live', methods=['POST'])
@firebase_required
def predict_live():
    try:
        from obd_reader import get_current_data, get_status

        status = get_status()
        if not status.get('connected'):
            return jsonify({"error": "OBD scanner not connected"}), 400

        data = get_current_data()
        if not data:
            return jsonify({"error": "No OBD data available"}), 400

        # Run ML prediction on live sensor data
        result = predict_health(data)
        if "error" in result:
            return jsonify({"error": result["error"]}), 500

        # Persist to DB
        failure_risk = 1 if result['health_category'] in ['Poor', 'Critical'] else 0

        # Get DB user_id
        db_user = get_or_create_user(request.user['uid'], request.user['email'])
        user_id = db_user['id']

        execute_query(
            """
            INSERT INTO reports
                (user_id, engine_score, fuel_score, stress_score,
                 overall_score, failure_risk, status_label, raw_input, issues)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                result['engine_score'],
                result['fuel_score'],
                result['driving_score'],
                result['overall_score'],
                failure_risk,
                result['health_category'],
                json.dumps(data),
                json.dumps(result['issues'])
            ),
            commit=True
        )

        return jsonify({
            "success":           True,
            "source":            "live_obd" if not status.get('simulated') else "simulated",
            "scores": {
                "engine":     result['engine_score'],
                "fuel":       result['fuel_score'],
                "efficiency": result['efficiency_score'],
                "driving":    result['driving_score'],
                "thermal":    result['thermal_score'],
                "overall":    result['overall_score']
            },
            "health_category":   result['health_category'],
            "issues":            result['issues'],
            "component_weights": result['component_weights']
        }), 200

    except Exception as e:
        print(f"[predict_live error] {e}")
        return jsonify({"error": "Prediction failed"}), 500


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# POST /predict/batch  [jwt_required]
# Accept array of OBD rows, aggregate via median, save report
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@predict_bp.route('/predict/batch', methods=['POST'])
@firebase_required
def predict_batch():
    try:
        data        = request.get_json()
        rows        = data.get('rows', [])
        duration    = data.get('duration_seconds', 120)
        vehicle_id  = data.get('vehicle_id', None)   # Firestore vehicle doc ID
        vehicle_name= data.get('vehicle_name', None) # display name
        vehicle_model=data.get('vehicle_model', None)

        if len(rows) < 5:
            return jsonify({
                "error": "Not enough data. Drive for at least 10 seconds."
            }), 400

        # â”€â”€ Run ML on each row â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        results = []
        for row in rows:
            result = predict_health(row)
            if 'error' not in result:
                results.append(result)

        if len(results) < 3:
            return jsonify({
                "error": "Too many prediction errors. Check OBD data quality."
            }), 500

        # â”€â”€ Aggregate using MEDIAN (robust to outliers) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        def med(key):
            vals = [r[key] for r in results if r.get(key) is not None]
            return round(statistics.median(vals), 2) if vals else 50.0

        engine_score     = med('engine_score')
        fuel_score       = med('fuel_score')
        efficiency_score = med('efficiency_score')
        driving_score    = med('driving_score')
        thermal_score    = med('thermal_score')
        overall_score    = med('overall_score')

        # â”€â”€ Persistent issues only (>30% of rows) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        all_issues = []
        for r in results:
            all_issues.extend(r.get('issues', []))

        issue_counts      = Counter(all_issues)
        threshold         = len(results) * 0.30
        persistent_issues = [
            issue for issue, count in issue_counts.items()
            if count >= threshold
        ]

        # â”€â”€ Health category & failure risk â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        status_label = Config.get_status_label(overall_score)
        failure_risk = 1 if status_label in ['Poor', 'Critical'] else 0

        # â”€â”€ Data quality tier â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if len(results) >= 30:
            quality = "High"
        elif len(results) >= 15:
            quality = "Medium"
        else:
            quality = "Low"

        # Get DB user_id
        db_user = get_or_create_user(request.user['uid'], request.user['email'])
        user_id = db_user['id']

        # â”€â”€ Persist report to DB â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        report_row = execute_query(
            """INSERT INTO reports
               (user_id, engine_score, fuel_score, stress_score,
                overall_score, failure_risk, status_label,
                raw_input, issues)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (
                user_id,
                engine_score,
                fuel_score,
                driving_score,
                overall_score,
                failure_risk,
                status_label,
                json.dumps({
                    "batch":        True,
                    "rows":         len(rows),
                    "duration":     duration,
                    "vehicle_id":   vehicle_id,
                    "vehicle_name": vehicle_name,
                    "vehicle_model":vehicle_model,
                    "source":       "live_obd"
                }),
                json.dumps(persistent_issues)
            ),
            fetchone=True,
            commit=True
        )

        report_id = report_row['id'] if report_row else None

        return jsonify({
            "success":       True,
            "overall_score": overall_score,
            "component_scores": {
                "engine":     engine_score,
                "fuel":       fuel_score,
                "efficiency": efficiency_score,
                "driving":    driving_score,
                "thermal":    thermal_score
            },
            "health_category": status_label,
            "issues":          persistent_issues,
            "failure_risk":    failure_risk,
            "data_quality": {
                "rows_collected":  len(results),
                "rows_submitted":  len(rows),
                "duration_seconds": duration,
                "quality":         quality
            },
            "report_id": report_id
        }), 200

    except Exception as e:
        print(f"[predict_batch error] {e}")
        return jsonify({"error": f"Batch prediction failed: {str(e)}"}), 500


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# POST /api/obd/agent-data  [jwt_required]
# Frontend pushes live OBD readings collected via Web Serial API.
# obd_reader.update_data() stores it and broadcasts via SocketIO.
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@predict_bp.route('/obd/agent-data', methods=['POST'])
@firebase_required
def obd_agent_data():
    try:
        from obd_reader import update_data
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        update_data(data)
        return jsonify({"success": True}), 200
    except Exception as e:
        print(f"[obd_agent_data error] {e}")
        return jsonify({"error": str(e)}), 500


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# POST /predict/csv  [firebase_required]
# Upload a CSV of OBD readings â†’ ML batch predict â†’ return PDF
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@predict_bp.route('/predict/csv', methods=['POST'])
@firebase_required
def predict_csv():
    try:
        import pandas as pd
        import io as _io
        import base64
        from datetime import datetime
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors as rc
        from reportlab.lib.units import mm
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from reportlab.platypus import (
            BaseDocTemplate, PageTemplate, Frame, Flowable,
            Spacer, Paragraph, Table, TableStyle, KeepTogether
        )

        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        f = request.files['file']
        if not f.filename.endswith('.csv'):
            return jsonify({"error": "Please upload a .csv file"}), 400

        # â”€â”€ Vehicle details from FormData â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        vehicle_name  = (request.form.get('vehicle_name')  or '').strip() or 'My Vehicle'
        vehicle_model = (request.form.get('vehicle_model') or '').strip()
        vehicle_id    = (request.form.get('vehicle_id')    or '').strip()

        # â”€â”€ Parse CSV â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        content = f.read().decode('utf-8')
        df = pd.read_csv(_io.StringIO(content))

        REQUIRED = ['rpm', 'speed', 'load', 'coolant_temp', 'throttle_pos',
                    'intake_temp', 'maf', 'stft', 'ltft']
        missing = [c for c in REQUIRED if c not in df.columns]
        if missing:
            return jsonify({"error": f"Missing columns: {', '.join(missing)}"}), 400

        df = df.fillna(0)
        rows = df.to_dict(orient='records')

        if len(rows) < 5:
            return jsonify({"error": "CSV must have at least 5 rows of data"}), 400

        # â”€â”€ Compute derived features for each row â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        def compute_derived(raw):
            rpm   = raw.get('rpm', 0) or 0
            speed = raw.get('speed', 0) or 0
            load  = raw.get('load', 0) or 0
            maf   = raw.get('maf', 0) or 0
            stft  = raw.get('stft', 0) or 0
            ltft  = raw.get('ltft', 0) or 0
            oat   = raw.get('coolant_temp', 70) or 70
            speed_limit = 60
            return {
                **raw,
                'oat': oat,
                'speed_limit': speed_limit,
                'maf_per_rpm':            round(maf / rpm, 4) if rpm > 0 else 0,
                'rpm_load_ratio':         round(rpm / load, 2) if load > 0 else 0,
                'maf_per_speed':          round(maf / speed, 4) if speed > 0 else 0,
                'load_per_speed':         round(load / speed, 2) if speed > 0 else 0,
                'maf_speed_deviation':    abs(maf / speed - maf / (rpm or 1)) if speed > 0 else 0,
                'fuel_trim_combined':     round(stft + ltft, 2),
                'fuel_trim_abs':          round(abs(stft) + abs(ltft), 2),
                'speed_excess':           max(0, speed - speed_limit),
                'is_overspeeding':        1 if speed > speed_limit else 0,
                'thermal_stress':         round(oat * (load / 100), 2),
                'maf_temp_adjusted':      round(maf * (1 + oat / 100), 2),
                'gradient_speed_stress':  round((rpm / 1000) * (speed / 100), 2),
            }

        # â”€â”€ Run ML on each row â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # Use cooperative yields (eventlet.sleep(0)) between rows so the
        # eventlet event loop stays alive and worker heartbeat doesn't time out.
        # ThreadPoolExecutor must NOT be used here â€” it corrupts eventlet sockets.
        results = []
        try:
            import eventlet as _ev
            _ev_ok = True
        except ImportError:
            _ev_ok = False

        for row in rows:
            enriched = compute_derived(row)
            result   = predict_health(enriched)
            if 'error' not in result:
                results.append(result)
            if _ev_ok:
                _ev.sleep(0)   # yield to event loop â€” prevents heartbeat timeout

        if len(results) < 3:
            return jsonify({"error": "Too many prediction errors. Check CSV data quality."}), 500




        # â”€â”€ Aggregate (median) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        engine_score     = round(statistics.median([r['engine_score']     for r in results]), 1)
        fuel_score       = round(statistics.median([r['fuel_score']       for r in results]), 1)
        efficiency_score = round(statistics.median([r['efficiency_score'] for r in results]), 1)
        driving_score    = round(statistics.median([r['driving_score']    for r in results]), 1)
        thermal_score    = round(statistics.median([r['thermal_score']    for r in results]), 1)
        overall_score    = round(statistics.median([r['overall_score']    for r in results]), 1)

        all_issues    = []
        for r in results: all_issues.extend(r.get('issues', []))
        issue_counts  = Counter(all_issues)
        threshold     = len(results) * 0.30
        persist_issues = [iss for iss, cnt in issue_counts.items() if cnt >= threshold]

        status_label  = Config.get_status_label(overall_score)
        failure_risk  = status_label in ['Poor', 'Critical']

        quality = "High" if len(results) >= 30 else "Medium" if len(results) >= 15 else "Low"

        # â”€â”€ Save report to DB (best-effort â€” PDF still returns if DB is down) â”€â”€
        report_id = None
        try:
            db_user = get_or_create_user(request.user['uid'], request.user['email'])
            if db_user:
                raw_meta = {
                    "source":        "csv_upload",
                    "rows":          len(results),
                    "quality":       quality,
                    "vehicle_name":  vehicle_name,
                    "vehicle_model": vehicle_model,
                    "vehicle_id":    vehicle_id,
                }
                report_row = execute_query(
                    """INSERT INTO reports
                       (user_id, engine_score, fuel_score, stress_score,
                        overall_score, failure_risk, status_label, raw_input, issues)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING id""",
                    (
                        db_user['id'], engine_score, fuel_score, driving_score,
                        overall_score, 1 if failure_risk else 0, status_label,
                        json.dumps(raw_meta),
                        json.dumps(persist_issues)
                    ),
                    fetchone=True, commit=True
                )
                report_id = report_row['id'] if report_row else None
        except Exception as db_err:
            print(f"[WARN] predict_csv: DB save failed (PDF still returning): {db_err}")

        # â”€â”€ Premium PDF via dedicated generator â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        from routes.pdf_generator import generate_report_pdf
        pdf_bytes = generate_report_pdf(
            vehicle_name    = vehicle_name,
            vehicle_model   = vehicle_model,
            overall_score   = overall_score,
            engine_score    = engine_score,
            fuel_score      = fuel_score,
            efficiency_score= efficiency_score,
            driving_score   = driving_score,
            thermal_score   = thermal_score,
            status_label    = status_label,
            failure_risk    = failure_risk,
            persist_issues  = persist_issues,
            issue_counts    = issue_counts,
            n_results       = len(results),
            quality         = quality,
        )
        # ── Generate smart notification timeline ──────────────────────
        try:
            from utils.timeline_engine import generate_timeline
            from firebase_admin import firestore as fs

            # Fetch last 3 reports for trend detection
            db = fs.client()
            uid = request.user['uid']
            history_docs = (
                db.collection('users').document(uid)
                  .collection('reports')
                  .order_by('timestamp', direction='DESCENDING')
                  .limit(4)
                  .stream()
            )
            report_history = [d.to_dict() for d in history_docs]

            timeline = generate_timeline(
                overall_score    = overall_score,
                engine_score     = engine_score,
                fuel_score       = fuel_score,
                efficiency_score = efficiency_score,
                driving_score    = driving_score,
                thermal_score    = thermal_score,
                persist_issues   = persist_issues,
                issue_counts     = dict(issue_counts),
                n_results        = len(results),
                report_history   = report_history,
            )

            # Write notification meta to Firestore under the vehicle
            if vehicle_id:
                db.collection('vehicles').document(vehicle_id)\
                  .collection('notification_meta').document('current')\
                  .set({
                      **timeline,
                      'uid':           uid,
                      'user_email':    request.user.get('email', ''),
                      'vehicle_name':  vehicle_name,
                      'vehicle_model': vehicle_model,
                  })

            print(f'[NOTIFY] Timeline written for vehicle={vehicle_id} tier={timeline["tier"]}')
        except Exception as notify_err:
            print(f'[WARN] Timeline generation failed (non-fatal): {notify_err}')


        return jsonify({
            "success":      True,
            "pdf_base64":   base64.b64encode(pdf_bytes).decode('utf-8'),
            "filename":     f"vexis_{vehicle_name.replace(' ','_')}_report.pdf",
            "report_id":    report_id,

            "vehicle_name": vehicle_name,
            "vehicle_model":vehicle_model,
            "scores": {
                "overall":    overall_score,
                "engine":     engine_score,
                "fuel":       fuel_score,
                "efficiency": efficiency_score,
                "driving":    driving_score,
                "thermal":    thermal_score,
            },
            "status_label":  status_label,
            "failure_risk":  failure_risk,
            "issues":        persist_issues,
            "quality":       quality,
            "rows_analysed": len(results),
        })

    except Exception as e:
        print(f"[predict_csv error] {e}")
        import traceback; traceback.print_exc()
        return jsonify({"error": f"CSV analysis failed: {str(e)}"}), 500

