from flask import Blueprint, request, jsonify
from utils.jwt_helper import jwt_required
from utils.validators import validate_obd_input
from ml.model_loader import predict_health
from database import execute_query
from config import Config
import json
import random
import statistics
from collections import Counter

predict_bp = Blueprint('predict', __name__)


# ──────────────────────────────────────────────────────────────────
# POST /predict  [jwt_required]
# ──────────────────────────────────────────────────────────────────
@predict_bp.route('/predict', methods=['POST'])
@jwt_required
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

        execute_query(
            """
            INSERT INTO reports
                (user_id, engine_score, fuel_score, stress_score,
                 overall_score, failure_risk, status_label, raw_input, issues)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request.user['user_id'],
                result['engine_score'],
                result['fuel_score'],
                result['driving_score'],       # driving ↔ stress
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


# ──────────────────────────────────────────────────────────────────
# GET /live-metrics  [jwt_required]
# ──────────────────────────────────────────────────────────────────
@predict_bp.route('/live-metrics', methods=['GET'])
@jwt_required
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


# ──────────────────────────────────────────────────────────────────
# POST /predict/live  [jwt_required]  — uses live OBD data
# ──────────────────────────────────────────────────────────────────
@predict_bp.route('/predict/live', methods=['POST'])
@jwt_required
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

        execute_query(
            """
            INSERT INTO reports
                (user_id, engine_score, fuel_score, stress_score,
                 overall_score, failure_risk, status_label, raw_input, issues)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request.user['user_id'],
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


# ──────────────────────────────────────────────────────────────────
# POST /predict/batch  [jwt_required]
# Accept array of OBD rows, aggregate via median, save report
# ──────────────────────────────────────────────────────────────────
@predict_bp.route('/predict/batch', methods=['POST'])
@jwt_required
def predict_batch():
    try:
        data     = request.get_json()
        rows     = data.get('rows', [])
        duration = data.get('duration_seconds', 120)

        if len(rows) < 5:
            return jsonify({
                "error": "Not enough data. Drive for at least 10 seconds."
            }), 400

        # ── Run ML on each row ─────────────────────────────────────
        results = []
        for row in rows:
            result = predict_health(row)
            if 'error' not in result:
                results.append(result)

        if len(results) < 3:
            return jsonify({
                "error": "Too many prediction errors. Check OBD data quality."
            }), 500

        # ── Aggregate using MEDIAN (robust to outliers) ────────────
        def med(key):
            vals = [r[key] for r in results if r.get(key) is not None]
            return round(statistics.median(vals), 2) if vals else 50.0

        engine_score     = med('engine_score')
        fuel_score       = med('fuel_score')
        efficiency_score = med('efficiency_score')
        driving_score    = med('driving_score')
        thermal_score    = med('thermal_score')
        overall_score    = med('overall_score')

        # ── Persistent issues only (>30% of rows) ─────────────────
        all_issues = []
        for r in results:
            all_issues.extend(r.get('issues', []))

        issue_counts      = Counter(all_issues)
        threshold         = len(results) * 0.30
        persistent_issues = [
            issue for issue, count in issue_counts.items()
            if count >= threshold
        ]

        # ── Health category & failure risk ─────────────────────────
        status_label = Config.get_status_label(overall_score)
        failure_risk = 1 if status_label in ['Poor', 'Critical'] else 0

        # ── Data quality tier ──────────────────────────────────────
        if len(results) >= 30:
            quality = "High"
        elif len(results) >= 15:
            quality = "Medium"
        else:
            quality = "Low"

        # ── Persist report to DB ───────────────────────────────────
        report_row = execute_query(
            """INSERT INTO reports
               (user_id, engine_score, fuel_score, stress_score,
                overall_score, failure_risk, status_label,
                raw_input, issues)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (
                request.user['user_id'],
                engine_score,
                fuel_score,
                driving_score,
                overall_score,
                failure_risk,
                status_label,
                json.dumps({
                    "batch":    True,
                    "rows":     len(rows),
                    "duration": duration
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


# ──────────────────────────────────────────────────────────────────
# POST /api/obd/agent-data  [jwt_required]
# Frontend pushes live OBD readings collected via Web Serial API.
# obd_reader.update_data() stores it and broadcasts via SocketIO.
# ──────────────────────────────────────────────────────────────────
@predict_bp.route('/obd/agent-data', methods=['POST'])
@jwt_required
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
