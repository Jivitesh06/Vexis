"""
predict.py — ML prediction routes (Firestore-only, no PostgreSQL)
"""
from flask import Blueprint, request, jsonify
from utils.firebase_auth import firebase_required
from utils.validators import validate_obd_input
from ml.model_loader import predict_health
from config import Config
import json
import random
import statistics
from collections import Counter
import base64

predict_bp = Blueprint('predict', __name__)


def _fs():
    from firebase_admin import firestore
    return firestore.client()


# ── POST /api/predict ────────────────────────────────────────────────────
# Single OBD reading — returns scores, no persistence
# ────────────────────────────────────────────────────────────────────────
@predict_bp.route('/predict', methods=['POST'])
@firebase_required
def predict():
    try:
        data = request.get_json()
        valid, error = validate_obd_input(data)
        if not valid:
            return jsonify({"error": error}), 400

        result = predict_health(data)
        if "error" in result:
            return jsonify({"error": result["error"]}), 500

        return jsonify({
            "success": True,
            "scores": {
                "engine":     result['engine_score'],
                "fuel":       result['fuel_score'],
                "efficiency": result['efficiency_score'],
                "driving":    result['driving_score'],
                "thermal":    result['thermal_score'],
                "overall":    result['overall_score'],
            },
            "health_category":   result['health_category'],
            "issues":            result['issues'],
            "component_weights": result['component_weights'],
        }), 200

    except Exception as e:
        print(f"[predict error] {e}")
        return jsonify({"error": "Prediction failed"}), 500


# ── GET /api/live-metrics ────────────────────────────────────────────────
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
            "intake_air_temp": round(random.uniform(25, 55), 1),
        }
        return jsonify({"success": True, "metrics": metrics}), 200

    except Exception as e:
        print(f"[live-metrics error] {e}")
        return jsonify({"error": "Failed"}), 500


# ── POST /api/predict/live ───────────────────────────────────────────────
# Live OBD prediction — reads from connected OBD reader, no persistence
# ────────────────────────────────────────────────────────────────────────
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

        result = predict_health(data)
        if "error" in result:
            return jsonify({"error": result["error"]}), 500

        return jsonify({
            "success": True,
            "source":  "live_obd" if not status.get('simulated') else "simulated",
            "scores": {
                "engine":     result['engine_score'],
                "fuel":       result['fuel_score'],
                "efficiency": result['efficiency_score'],
                "driving":    result['driving_score'],
                "thermal":    result['thermal_score'],
                "overall":    result['overall_score'],
            },
            "health_category":   result['health_category'],
            "issues":            result['issues'],
            "component_weights": result['component_weights'],
        }), 200

    except Exception as e:
        print(f"[predict_live error] {e}")
        return jsonify({"error": "Prediction failed"}), 500


# ── POST /api/predict/batch ──────────────────────────────────────────────
# Batch OBD rows → aggregate → save report to Firestore
# ────────────────────────────────────────────────────────────────────────
@predict_bp.route('/predict/batch', methods=['POST'])
@firebase_required
def predict_batch():
    try:
        from datetime import datetime
        data         = request.get_json()
        rows         = data.get('rows', [])
        duration     = data.get('duration_seconds', 120)
        vehicle_id   = data.get('vehicle_id')
        vehicle_name = data.get('vehicle_name') or 'My Vehicle'
        vehicle_model= data.get('vehicle_model') or ''

        if len(rows) < 5:
            return jsonify({"error": "Not enough data. Drive for at least 10 seconds."}), 400

        # Run ML on each row
        results = []
        for row in rows:
            result = predict_health(row)
            if 'error' not in result:
                results.append(result)

        if len(results) < 3:
            return jsonify({"error": "Too many prediction errors. Check OBD data quality."}), 500

        # Aggregate with median
        def med(key):
            vals = [r[key] for r in results if r.get(key) is not None]
            return round(statistics.median(vals), 2) if vals else 50.0

        engine_score     = med('engine_score')
        fuel_score       = med('fuel_score')
        efficiency_score = med('efficiency_score')
        driving_score    = med('driving_score')
        thermal_score    = med('thermal_score')
        overall_score    = med('overall_score')

        all_issues = []
        for r in results:
            all_issues.extend(r.get('issues', []))
        issue_counts      = Counter(all_issues)
        threshold         = len(results) * 0.30
        persistent_issues = [iss for iss, cnt in issue_counts.items() if cnt >= threshold]

        status_label = Config.get_status_label(overall_score)
        failure_risk = status_label in ['Poor', 'Critical']
        quality = "High" if len(results) >= 30 else "Medium" if len(results) >= 15 else "Low"

        # Save to Firestore
        report_id = None
        try:
            uid = request.user['uid']
            ref = _fs().collection('users').document(uid).collection('reports').add({
                'source':           'live_obd',
                'vehicle_name':     vehicle_name,
                'vehicle_model':    vehicle_model,
                'vehicle_id':       vehicle_id or '',
                'overall_score':    overall_score,
                'engine_score':     engine_score,
                'fuel_score':       fuel_score,
                'efficiency_score': efficiency_score,
                'driving_score':    driving_score,
                'thermal_score':    thermal_score,
                'status_label':     status_label,
                'failure_risk':     bool(failure_risk),
                'issues':           persistent_issues,
                'quality':          quality,
                'rows_analysed':    len(results),
                'duration_seconds': duration,
                'timestamp':        datetime.utcnow().isoformat(),
            })
            report_id = ref[1].id
            print(f'[FIRESTORE] Batch report saved: {report_id}')
        except Exception as fs_err:
            print(f'[WARN] predict_batch: Firestore save failed: {fs_err}')

        return jsonify({
            "success":       True,
            "overall_score": overall_score,
            "component_scores": {
                "engine":     engine_score,
                "fuel":       fuel_score,
                "efficiency": efficiency_score,
                "driving":    driving_score,
                "thermal":    thermal_score,
            },
            "health_category": status_label,
            "issues":          persistent_issues,
            "failure_risk":    failure_risk,
            "data_quality": {
                "rows_collected":   len(results),
                "rows_submitted":   len(rows),
                "duration_seconds": duration,
                "quality":          quality,
            },
            "report_id": report_id,
        }), 200

    except Exception as e:
        print(f"[predict_batch error] {e}")
        return jsonify({"error": f"Batch prediction failed: {str(e)}"}), 500


# ── POST /api/obd/agent-data ─────────────────────────────────────────────
# Frontend pushes live OBD readings via Web Serial API
# ────────────────────────────────────────────────────────────────────────
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


# ── POST /api/predict/csv ────────────────────────────────────────────────
# Upload a CSV of OBD readings → ML batch predict → PDF → Firestore save
# ────────────────────────────────────────────────────────────────────────
@predict_bp.route('/predict/csv', methods=['POST'])
@firebase_required
def predict_csv():
    try:
        import pandas as pd
        import io as _io
        from datetime import datetime

        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        f = request.files['file']
        if not f.filename.endswith('.csv'):
            return jsonify({"error": "Please upload a .csv file"}), 400

        # Vehicle details from FormData
        vehicle_name  = (request.form.get('vehicle_name')  or '').strip() or 'My Vehicle'
        vehicle_model = (request.form.get('vehicle_model') or '').strip()
        vehicle_id    = (request.form.get('vehicle_id')    or '').strip()

        # Parse CSV
        content = f.read().decode('utf-8')
        df = pd.read_csv(_io.StringIO(content))

        REQUIRED = ['rpm', 'speed', 'load', 'coolant_temp', 'throttle_pos',
                    'intake_temp', 'maf', 'stft', 'ltft']
        missing = [c for c in REQUIRED if c not in df.columns]
        if missing:
            return jsonify({"error": f"Missing columns: {', '.join(missing)}"}), 400

        df   = df.fillna(0)
        rows = df.to_dict(orient='records')

        if len(rows) < 5:
            return jsonify({"error": "CSV must have at least 5 rows of data"}), 400

        # Compute derived features
        def compute_derived(raw):
            rpm         = raw.get('rpm', 0) or 0
            speed       = raw.get('speed', 0) or 0
            load        = raw.get('load', 0) or 0
            maf         = raw.get('maf', 0) or 0
            stft        = raw.get('stft', 0) or 0
            ltft        = raw.get('ltft', 0) or 0
            oat         = raw.get('coolant_temp', 70) or 70
            speed_limit = 60
            return {
                **raw,
                'oat':                    oat,
                'speed_limit':            speed_limit,
                'maf_per_rpm':            round(maf / rpm, 4)              if rpm   > 0 else 0,
                'rpm_load_ratio':         round(rpm / load, 2)             if load  > 0 else 0,
                'maf_per_speed':          round(maf / speed, 4)            if speed > 0 else 0,
                'load_per_speed':         round(load / speed, 2)           if speed > 0 else 0,
                'maf_speed_deviation':    abs(maf / speed - maf / (rpm or 1)) if speed > 0 else 0,
                'fuel_trim_combined':     round(stft + ltft, 2),
                'fuel_trim_abs':          round(abs(stft) + abs(ltft), 2),
                'speed_excess':           max(0, speed - speed_limit),
                'is_overspeeding':        1 if speed > speed_limit else 0,
                'thermal_stress':         round(oat * (load / 100), 2),
                'maf_temp_adjusted':      round(maf * (1 + oat / 100), 2),
                'gradient_speed_stress':  round((rpm / 1000) * (speed / 100), 2),
            }

        # Run ML on each row — yield to eventlet between rows
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
                _ev.sleep(0)  # prevent eventlet heartbeat timeout

        if len(results) < 3:
            return jsonify({"error": "Too many prediction errors. Check CSV data quality."}), 500

        # Aggregate (median)
        engine_score     = round(statistics.median([r['engine_score']     for r in results]), 1)
        fuel_score       = round(statistics.median([r['fuel_score']       for r in results]), 1)
        efficiency_score = round(statistics.median([r['efficiency_score'] for r in results]), 1)
        driving_score    = round(statistics.median([r['driving_score']    for r in results]), 1)
        thermal_score    = round(statistics.median([r['thermal_score']    for r in results]), 1)
        overall_score    = round(statistics.median([r['overall_score']    for r in results]), 1)

        all_issues = []
        for r in results:
            all_issues.extend(r.get('issues', []))
        issue_counts   = Counter(all_issues)
        threshold      = len(results) * 0.30
        persist_issues = [iss for iss, cnt in issue_counts.items() if cnt >= threshold]

        status_label = Config.get_status_label(overall_score)
        failure_risk = status_label in ['Poor', 'Critical']
        quality = "High" if len(results) >= 30 else "Medium" if len(results) >= 15 else "Low"

        # Generate premium PDF
        from routes.pdf_generator import generate_report_pdf
        pdf_bytes = generate_report_pdf(
            vehicle_name     = vehicle_name,
            vehicle_model    = vehicle_model,
            overall_score    = overall_score,
            engine_score     = engine_score,
            fuel_score       = fuel_score,
            efficiency_score = efficiency_score,
            driving_score    = driving_score,
            thermal_score    = thermal_score,
            status_label     = status_label,
            failure_risk     = failure_risk,
            persist_issues   = persist_issues,
            issue_counts     = issue_counts,
            n_results        = len(results),
            quality          = quality,
        )

        pdf_b64   = base64.b64encode(pdf_bytes).decode('utf-8')
        report_id = None

        # Save report + PDF to Firestore
        try:
            uid = request.user['uid']
            ref = _fs().collection('users').document(uid).collection('reports').add({
                'source':           'csv_upload',
                'vehicle_name':     vehicle_name,
                'vehicle_model':    vehicle_model,
                'vehicle_id':       vehicle_id,
                'overall_score':    overall_score,
                'engine_score':     engine_score,
                'fuel_score':       fuel_score,
                'efficiency_score': efficiency_score,
                'driving_score':    driving_score,
                'thermal_score':    thermal_score,
                'status_label':     status_label,
                'failure_risk':     bool(failure_risk),
                'issues':           persist_issues,
                'quality':          quality,
                'rows_analysed':    len(results),
                'pdf_base64':       pdf_b64,
                'timestamp':        datetime.utcnow().isoformat(),
            })
            report_id = ref[1].id
            print(f'[FIRESTORE] CSV report saved: {report_id}')
        except Exception as fs_err:
            print(f'[WARN] predict_csv: Firestore save failed (PDF still returning): {fs_err}')

        # Generate notification timeline (non-blocking)
        try:
            from utils.timeline_engine import generate_timeline
            uid = request.user['uid']

            history_docs = _fs().collection('users').document(uid)\
                               .collection('reports')\
                               .order_by('timestamp', direction='DESCENDING')\
                               .limit(4).stream()
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

            if not vehicle_id:
                # Generate a fallback vehicle_id so the notification engine can track it
                import hashlib
                vid_hash = hashlib.md5(f"{uid}_{vehicle_name}".encode()).hexdigest()[:8]
                vehicle_id = f"v_{vid_hash}"

            # Ensure parent vehicle document exists so it shows up in "My Vehicles" and timeline-summary
            veh_ref = _fs().collection('vehicles').document(vehicle_id)
            if not veh_ref.get().exists:
                veh_ref.set({
                    'userId':        uid,
                    'name':          vehicle_name,
                    'model':         vehicle_model,
                    'created_at':    datetime.utcnow().isoformat(),
                    'last_analysed': datetime.utcnow().isoformat()
                })
            else:
                veh_ref.update({'last_analysed': datetime.utcnow().isoformat()})

            _fs().collection('vehicles').document(vehicle_id)\
                 .collection('notification_meta').document('current')\
                 .set({
                         **timeline,
                         'uid':           uid,
                         'user_email':    request.user.get('email', ''),
                         'vehicle_name':  vehicle_name,
                         'vehicle_model': vehicle_model,
                     })
            print(f'[NOTIFY] Timeline written tier={timeline["tier"]}')
        except Exception as notify_err:
            print(f'[WARN] Timeline generation failed (non-fatal): {notify_err}')

        return jsonify({
            "success":       True,
            "pdf_base64":    pdf_b64,
            "filename":      f"vexis_{vehicle_name.replace(' ','_')}_report.pdf",
            "report_id":     report_id,
            "vehicle_name":  vehicle_name,
            "vehicle_model": vehicle_model,
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
