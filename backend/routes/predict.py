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


# ──────────────────────────────────────────────────────────────────
# POST /predict  [jwt_required]
# ──────────────────────────────────────────────────────────────────
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


# ──────────────────────────────────────────────────────────────────
# POST /predict/live  [jwt_required]  — uses live OBD data
# ──────────────────────────────────────────────────────────────────
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


# ──────────────────────────────────────────────────────────────────
# POST /predict/batch  [jwt_required]
# Accept array of OBD rows, aggregate via median, save report
# ──────────────────────────────────────────────────────────────────
@predict_bp.route('/predict/batch', methods=['POST'])
@firebase_required
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

        # Get DB user_id
        db_user = get_or_create_user(request.user['uid'], request.user['email'])
        user_id = db_user['id']

        # ── Persist report to DB ───────────────────────────────────
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


# ──────────────────────────────────────────────────────────────────
# POST /predict/csv  [firebase_required]
# Upload a CSV of OBD readings → ML batch predict → return PDF
# ──────────────────────────────────────────────────────────────────
@predict_bp.route('/predict/csv', methods=['POST'])
@firebase_required
def predict_csv():
    try:
        import pandas as pd
        import io as _io
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_CENTER
        from flask import make_response
        from datetime import datetime

        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        f = request.files['file']
        if not f.filename.endswith('.csv'):
            return jsonify({"error": "Please upload a .csv file"}), 400

        # ── Parse CSV ─────────────────────────────────────────────
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

        # ── Compute derived features for each row ─────────────────
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

        # ── Run ML on each row ────────────────────────────────────
        results = []
        for row in rows:
            enriched = compute_derived(row)
            result   = predict_health(enriched)
            if 'error' not in result:
                results.append(result)

        if len(results) < 3:
            return jsonify({"error": "Too many prediction errors. Check CSV data quality."}), 500

        # ── Aggregate (median) ────────────────────────────────────
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

        # ── Helper ────────────────────────────────────────────────
        def score_label(s):
            if s >= 90: return ("Excellent", colors.HexColor("#22c55e"))
            if s >= 75: return ("Good",      colors.HexColor("#84cc16"))
            if s >= 60: return ("Fair",      colors.HexColor("#f59e0b"))
            if s >= 40: return ("Poor",      colors.HexColor("#f97316"))
            return              ("Critical", colors.HexColor("#ef4444"))

        # ── Build PDF ─────────────────────────────────────────────
        buf    = _io.BytesIO()
        doc    = SimpleDocTemplate(buf, pagesize=letter,
                                   rightMargin=50, leftMargin=50,
                                   topMargin=50, bottomMargin=40)
        styles = getSampleStyleSheet()
        story  = []

        # Title
        title_style = ParagraphStyle('VexisTitle', fontSize=22, fontName='Helvetica-Bold',
                                      textColor=colors.HexColor("#0ea5e9"), alignment=TA_CENTER,
                                      spaceAfter=4)
        sub_style   = ParagraphStyle('VexisSub', fontSize=10, textColor=colors.HexColor("#6b7280"),
                                      alignment=TA_CENTER, spaceAfter=2)

        story.append(Paragraph("⬡ VEXIS", title_style))
        story.append(Paragraph("AI-Powered Vehicle Health Report — Manual CSV Analysis", sub_style))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}  |  Rows Analysed: {len(results)}  |  Data Quality: {quality}", sub_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0"), spaceAfter=16, spaceBefore=10))

        # Overall Score Banner
        ov_label, ov_color = score_label(overall_score)
        banner_data = [[
            Paragraph(f"<b>Overall Health Score</b>", styles['Normal']),
            Paragraph(f"<b>{overall_score}/100</b>", styles['Normal']),
            Paragraph(f"<b>{ov_label}</b>", styles['Normal']),
            Paragraph(f"<b>{'⚠ At Risk' if failure_risk else '✓ Healthy'}</b>", styles['Normal'])
        ]]
        banner_table = Table(banner_data, colWidths=[160, 100, 110, 110])
        banner_table.setStyle(TableStyle([
            ('BACKGROUND',  (0,0), (-1,0), colors.HexColor("#0f172a")),
            ('TEXTCOLOR',   (0,0), (-1,0), colors.white),
            ('FONTSIZE',    (0,0), (-1,0), 11),
            ('ALIGN',       (0,0), (-1,0), 'CENTER'),
            ('VALIGN',      (0,0), (-1,0), 'MIDDLE'),
            ('TOPPADDING',  (0,0), (-1,0), 12),
            ('BOTTOMPADDING',(0,0), (-1,0), 12),
            ('BACKGROUND',  (1,0), (1,0), ov_color),
            ('BACKGROUND',  (2,0), (2,0), ov_color),
            ('ROUNDEDCORNERS', [4]),
        ]))
        story.append(banner_table)
        story.append(Spacer(1, 18))

        # Component Scores Table
        story.append(Paragraph("<b>Component Health Scores</b>", styles['Heading2']))
        story.append(Spacer(1, 8))

        components = [
            ("🔧 Engine",      engine_score),
            ("⛽ Fuel System", fuel_score),
            ("⚡ Efficiency",  efficiency_score),
            ("🚗 Driving",     driving_score),
            ("🌡 Thermal",     thermal_score),
        ]
        comp_data = [["Component", "Score", "Status", "Health Bar"]]
        for name, score in components:
            lbl, clr = score_label(score)
            bar_filled = int(score / 5)  # max 20 chars
            bar = "█" * bar_filled + "░" * (20 - bar_filled)
            comp_data.append([name, f"{score}/100", lbl, bar])

        comp_table = Table(comp_data, colWidths=[130, 70, 90, 190])
        comp_table.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0), colors.HexColor("#1e293b")),
            ('TEXTCOLOR',     (0,0), (-1,0), colors.white),
            ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0,0), (-1,-1), 10),
            ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING',    (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('GRID',          (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
            ('FONTNAME',      (3,1), (3,-1), 'Courier'),
            ('FONTSIZE',      (3,1), (3,-1), 7),
        ]))
        story.append(comp_table)
        story.append(Spacer(1, 20))

        # Detected Issues
        story.append(Paragraph("<b>Detected Issues</b>", styles['Heading2']))
        story.append(Spacer(1, 8))
        if persist_issues:
            issue_data = [["#", "Issue Description", "Frequency"]]
            for i, iss in enumerate(persist_issues, 1):
                cnt = issue_counts[iss]
                pct = round(cnt / len(results) * 100)
                issue_data.append([str(i), iss, f"{pct}% of readings"])
            issue_table = Table(issue_data, colWidths=[30, 330, 120])
            issue_table.setStyle(TableStyle([
                ('BACKGROUND',    (0,0), (-1,0), colors.HexColor("#dc2626")),
                ('TEXTCOLOR',     (0,0), (-1,0), colors.white),
                ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE',      (0,0), (-1,-1), 10),
                ('ALIGN',         (0,0), (0,-1), 'CENTER'),
                ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
                ('TOPPADDING',    (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('GRID',          (0,0), (-1,-1), 0.5, colors.HexColor("#fca5a5")),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#fef2f2"), colors.white]),
            ]))
            story.append(issue_table)
        else:
            story.append(Paragraph("✅ No persistent issues detected across readings.", styles['Normal']))
        story.append(Spacer(1, 20))

        # Recommendations
        story.append(Paragraph("<b>Recommendations</b>", styles['Heading2']))
        story.append(Spacer(1, 8))
        recs = []
        if engine_score < 60:  recs.append("🔧 Engine health is below optimal. Schedule a full engine diagnostic immediately.")
        if fuel_score < 60:    recs.append("⛽ Fuel system efficiency is low. Check injectors and O2 sensors.")
        if thermal_score < 60: recs.append("🌡 Thermal stress is high. Inspect cooling system and coolant levels.")
        if driving_score < 60: recs.append("🚗 Driving pattern is aggressive. Reduce rapid acceleration and hard braking.")
        if efficiency_score < 60: recs.append("⚡ Engine efficiency is poor. Consider air filter and spark plug inspection.")
        if not recs:           recs.append("✅ Vehicle is in good health. Continue regular maintenance schedule.")

        for rec in recs:
            story.append(Paragraph(f"• {rec}", styles['Normal']))
            story.append(Spacer(1, 6))

        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0")))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            f"<i>This report was generated by Vexis AI using {len(results)} OBD readings from your uploaded CSV. "
            f"Data quality: {quality}. This is an automated ML analysis — consult a certified mechanic for official diagnosis.</i>",
            ParagraphStyle('Disclaimer', fontSize=8, textColor=colors.HexColor("#9ca3af"), alignment=TA_CENTER)
        ))

        doc.build(story)
        pdf_bytes = buf.getvalue()
        buf.close()

        response = make_response(pdf_bytes)
        response.headers['Content-Type']        = 'application/pdf'
        response.headers['Content-Disposition'] = 'attachment; filename=vexis_manual_report.pdf'
        return response

    except Exception as e:
        print(f"[predict_csv error] {e}")
        import traceback; traceback.print_exc()
        return jsonify({"error": f"CSV analysis failed: {str(e)}"}), 500

