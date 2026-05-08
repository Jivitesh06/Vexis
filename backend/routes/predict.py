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

        # ── Vehicle details from FormData ─────────────────────────
        vehicle_name  = (request.form.get('vehicle_name')  or '').strip() or 'My Vehicle'
        vehicle_model = (request.form.get('vehicle_model') or '').strip()
        vehicle_id    = (request.form.get('vehicle_id')    or '').strip()

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
        # Use cooperative yields (eventlet.sleep(0)) between rows so the
        # eventlet event loop stays alive and worker heartbeat doesn't time out.
        # ThreadPoolExecutor must NOT be used here — it corrupts eventlet sockets.
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
                _ev.sleep(0)   # yield to event loop — prevents heartbeat timeout

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

        # ── Save report to DB (best-effort — PDF still returns if DB is down) ──
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

        # ══════════════════════════════════════════════════
        # PROFESSIONAL PDF — industry-level design
        # ══════════════════════════════════════════════════

        # ── Palette ───────────────────────────────────────
        NAVY   = rc.HexColor("#0f172a")
        NAVY2  = rc.HexColor("#1e293b")
        CYAN   = rc.HexColor("#0ea5e9")
        GREEN  = rc.HexColor("#22c55e")
        LIME   = rc.HexColor("#84cc16")
        AMBER  = rc.HexColor("#f59e0b")
        ORANGE = rc.HexColor("#f97316")
        RED    = rc.HexColor("#ef4444")
        LGRAY  = rc.HexColor("#f1f5f9")
        BORDER = rc.HexColor("#e2e8f0")
        MUTED  = rc.HexColor("#64748b")
        SLATE  = rc.HexColor("#94a3b8")

        PAGE_W, PAGE_H = A4
        HMARGIN = 18 * mm
        GEN_DATE = datetime.now().strftime("%d %b %Y, %H:%M")

        def score_info(s):
            if s >= 90: return ("EXCELLENT", GREEN)
            if s >= 75: return ("GOOD",      LIME)
            if s >= 60: return ("FAIR",      AMBER)
            if s >= 40: return ("POOR",      ORANGE)
            return              ("CRITICAL",  RED)

        # ── Custom Flowables ──────────────────────────────
        class ScoreBar(Flowable):
            def __init__(self, score, color, width=170, height=8):
                Flowable.__init__(self)
                self.score = min(max(float(score), 0), 100)
                self.color = color
                self.width = width
                self.height = height
            def wrap(self, *a): return (self.width, self.height)
            def draw(self):
                h = self.height
                self.canv.setFillColor(BORDER)
                self.canv.roundRect(0, 0, self.width, h, h/2, fill=1, stroke=0)
                fw = max((self.score / 100) * self.width, h)
                self.canv.setFillColor(self.color)
                self.canv.roundRect(0, 0, fw, h, h/2, fill=1, stroke=0)

        class ScoreCircle(Flowable):
            def __init__(self, score, color, size=88):
                Flowable.__init__(self)
                self.score = score
                self.color = color
                self.size = size
            def wrap(self, *a): return (self.size, self.size)
            def draw(self):
                cx = cy = self.size / 2
                r = self.size / 2 - 5
                # Outer ring
                self.canv.setFillColor(LGRAY)
                self.canv.setStrokeColor(BORDER)
                self.canv.setLineWidth(1)
                self.canv.circle(cx, cy, r + 5, fill=1, stroke=1)
                # Colored fill circle
                self.canv.setFillColor(self.color)
                self.canv.setStrokeColor(rc.white)
                self.canv.setLineWidth(3)
                self.canv.circle(cx, cy, r, fill=1, stroke=1)
                # Score text
                s = str(int(self.score))
                self.canv.setFillColor(rc.white)
                self.canv.setFont("Helvetica-Bold", 26)
                tw = self.canv.stringWidth(s, "Helvetica-Bold", 26)
                self.canv.drawString(cx - tw/2, cy + 3, s)
                self.canv.setFont("Helvetica", 8)
                self.canv.setFillColor(rc.HexColor("#cbd5e1"))
                tw2 = self.canv.stringWidth("/100", "Helvetica", 8)
                self.canv.drawString(cx - tw2/2, cy - 12, "/100")

        class AccentLine(Flowable):
            """Colored left-accent section header."""
            def __init__(self, text, accent=None):
                Flowable.__init__(self)
                self.text = text.upper()
                self.accent = accent or CYAN
            def wrap(self, aw, ah):
                self._w = aw
                return (aw, 20)
            def draw(self):
                self.canv.setFillColor(self.accent)
                self.canv.rect(0, 3, 4, 14, fill=1, stroke=0)
                self.canv.setFillColor(NAVY)
                self.canv.setFont("Helvetica-Bold", 11)
                self.canv.drawString(11, 5, self.text)

        # ── Page template (header + footer on every page) ─
        def _page(canvas, doc):
            canvas.saveState()
            w, h = doc.pagesize
            # Header band
            canvas.setFillColor(NAVY)
            canvas.rect(0, h - 44*mm, w, 44*mm, fill=1, stroke=0)
            # Brand
            canvas.setFillColor(CYAN)
            canvas.setFont("Helvetica-Bold", 26)
            canvas.drawString(HMARGIN, h - 17*mm, "VEXIS")
            canvas.setFillColor(SLATE)
            canvas.setFont("Helvetica", 8)
            canvas.drawString(HMARGIN, h - 23*mm, "AI VEHICLE INTELLIGENCE PLATFORM")
            # Thin separator
            canvas.setStrokeColor(rc.HexColor("#334155"))
            canvas.setLineWidth(0.5)
            canvas.line(HMARGIN, h - 26*mm, w - HMARGIN, h - 26*mm)
            # Vehicle name
            vname = vehicle_name[:40]
            canvas.setFillColor(rc.white)
            canvas.setFont("Helvetica-Bold", 13)
            canvas.drawString(HMARGIN, h - 33*mm, vname)
            if vehicle_model:
                canvas.setFont("Helvetica", 9)
                canvas.setFillColor(SLATE)
                canvas.drawString(HMARGIN, h - 38*mm, vehicle_model[:50])
            # Right meta
            rx = w - HMARGIN
            canvas.setFont("Helvetica-Bold", 8)
            canvas.setFillColor(SLATE)
            canvas.drawRightString(rx, h - 18*mm, "VEHICLE HEALTH REPORT")
            canvas.setFont("Helvetica", 8)
            canvas.drawRightString(rx, h - 23*mm, f"Generated: {GEN_DATE}")
            canvas.drawRightString(rx, h - 28*mm, f"Readings: {len(results)}   Quality: {quality}")
            canvas.drawRightString(rx, h - 33*mm, "Powered by Vexis ML Engine")
            # Footer band
            canvas.setFillColor(LGRAY)
            canvas.rect(0, 0, w, 11*mm, fill=1, stroke=0)
            canvas.setStrokeColor(BORDER)
            canvas.setLineWidth(0.5)
            canvas.line(0, 11*mm, w, 11*mm)
            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica", 7)
            canvas.drawString(HMARGIN, 3.5*mm,
                "This report is generated by Vexis AI using machine learning. "
                "Consult a certified mechanic for official diagnosis.")
            canvas.drawRightString(w - HMARGIN, 3.5*mm, f"Page {doc.page}")
            canvas.restoreState()

        # ── Doc setup ─────────────────────────────────────
        buf  = _io.BytesIO()
        TOP  = 44*mm + 8*mm   # below header
        BOT  = 11*mm + 6*mm   # above footer
        frame = Frame(HMARGIN, BOT, PAGE_W - 2*HMARGIN, PAGE_H - TOP - BOT,
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        tmpl  = PageTemplate(id='main', frames=[frame], onPage=_page)
        pdoc  = BaseDocTemplate(buf, pagesize=A4, pageTemplates=[tmpl])

        # ── Style helpers ─────────────────────────────────
        def ps(name, **kw):
            return ParagraphStyle(name, **kw)

        body_style  = ps('body',  fontSize=9,  textColor=NAVY,  leading=14)
        muted_style = ps('muted', fontSize=8,  textColor=MUTED, leading=12)
        center9     = ps('c9',    fontSize=9,  textColor=NAVY,  alignment=TA_CENTER, leading=14)
        center8     = ps('c8',    fontSize=8,  textColor=MUTED, alignment=TA_CENTER, leading=12)
        bold9       = ps('b9',    fontSize=9,  textColor=NAVY,  fontName='Helvetica-Bold', leading=14)
        white_bold  = ps('wb',    fontSize=9,  textColor=rc.white, fontName='Helvetica-Bold', leading=14)
        white_sm    = ps('wsm',   fontSize=8,  textColor=rc.HexColor('#cbd5e1'), leading=12)

        story = []

        # ── 1. Overall Score Card ─────────────────────────
        ov_label, ov_color = score_info(overall_score)
        risk_txt   = "AT RISK" if failure_risk else "HEALTHY"
        risk_color = RED if failure_risk else GREEN

        # Score circle + summary in a side-by-side table
        circle = ScoreCircle(overall_score, ov_color, size=88)

        score_detail = Table([
            [Paragraph("OVERALL HEALTH SCORE", ps('ot', fontSize=8, textColor=SLATE, fontName='Helvetica-Bold', leading=12))],
            [Paragraph(f"<font size=28 color='#{ov_color.hexval()[1:]}'><b>{int(overall_score)}</b></font><font size=11 color='#64748b'> / 100</font>",
                ps('sc', fontSize=10, leading=34))],
            [Paragraph(ov_label, ps('sl', fontSize=12, textColor=ov_color, fontName='Helvetica-Bold', leading=16))],
            [Paragraph(risk_txt,  ps('rl', fontSize=9,  textColor=risk_color, fontName='Helvetica-Bold', leading=14))],
        ], colWidths=[120])
        score_detail.setStyle(TableStyle([
            ('LEFTPADDING',  (0,0),(-1,-1), 0),
            ('RIGHTPADDING', (0,0),(-1,-1), 0),
            ('TOPPADDING',   (0,0),(-1,-1), 2),
            ('BOTTOMPADDING',(0,0),(-1,-1), 2),
        ]))

        header_card = Table(
            [[circle, score_detail,
              Table([
                [Paragraph("ENGINE",     white_sm), Paragraph(f"<b>{int(engine_score)}</b>",     white_bold)],
                [Paragraph("FUEL",       white_sm), Paragraph(f"<b>{int(fuel_score)}</b>",       white_bold)],
                [Paragraph("EFFICIENCY", white_sm), Paragraph(f"<b>{int(efficiency_score)}</b>", white_bold)],
                [Paragraph("DRIVING",    white_sm), Paragraph(f"<b>{int(driving_score)}</b>",    white_bold)],
                [Paragraph("THERMAL",    white_sm), Paragraph(f"<b>{int(thermal_score)}</b>",    white_bold)],
              ], colWidths=[65, 30],
                style=TableStyle([
                  ('BACKGROUND',   (0,0),(-1,-1), NAVY2),
                  ('TEXTCOLOR',    (0,0),(-1,-1), rc.white),
                  ('TOPPADDING',   (0,0),(-1,-1), 4),
                  ('BOTTOMPADDING',(0,0),(-1,-1), 4),
                  ('LEFTPADDING',  (0,0),(0,-1),  8),
                  ('RIGHTPADDING', (1,0),(1,-1),  8),
                  ('ALIGN',        (1,0),(1,-1),  'RIGHT'),
                  ('LINEBELOW',    (0,0),(-1,-2), 0.4, rc.HexColor('#334155')),
                ]))
            ]],
            colWidths=[96, 128, 111]
        )
        header_card.setStyle(TableStyle([
            ('BACKGROUND',   (0,0),(0,0), LGRAY),
            ('BACKGROUND',   (1,0),(1,0), rc.white),
            ('ALIGN',        (0,0),(0,0), 'CENTER'),
            ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
            ('TOPPADDING',   (0,0),(-1,-1), 12),
            ('BOTTOMPADDING',(0,0),(-1,-1), 12),
            ('LEFTPADDING',  (0,0),(-1,-1), 10),
            ('RIGHTPADDING', (0,0),(-1,-1), 10),
            ('BOX',          (0,0),(-1,-1), 0.8, BORDER),
            ('LINEAFTER',    (0,0),(0,0),   0.8, BORDER),
            ('LINEAFTER',    (1,0),(1,0),   0.8, BORDER),
            ('ROUNDEDCORNERS', [6]),
        ]))
        story.append(header_card)
        story.append(Spacer(1, 14))

        # ── 2. Component Scores ───────────────────────────
        story.append(AccentLine("Component Health Scores"))
        story.append(Spacer(1, 8))

        components = [
            ("Engine",     engine_score),
            ("Fuel System",fuel_score),
            ("Efficiency", efficiency_score),
            ("Driving",    driving_score),
            ("Thermal",    thermal_score),
        ]

        def comp_cell(name, score):
            lbl, clr = score_info(score)
            bar = ScoreBar(score, clr, width=160, height=7)
            tbl = Table([
                [Paragraph(f"<b>{name}</b>", ps('cn', fontSize=9, textColor=NAVY, leading=13)),
                 Paragraph(f"<font color='#{clr.hexval()[1:]}'><b>{int(score)}</b></font>",
                           ps('cs', fontSize=14, fontName='Helvetica-Bold', leading=16, alignment=TA_RIGHT))],
                [bar, Paragraph(lbl, ps('cl', fontSize=7.5, textColor=clr, fontName='Helvetica-Bold',
                                        leading=10, alignment=TA_RIGHT))],
            ], colWidths=[100, 60])
            tbl.setStyle(TableStyle([
                ('LEFTPADDING',  (0,0),(-1,-1), 0),
                ('RIGHTPADDING', (0,0),(-1,-1), 0),
                ('TOPPADDING',   (0,0),(-1,-1), 2),
                ('BOTTOMPADDING',(0,0),(-1,-1), 2),
                ('SPAN',         (0,1),(0,1)),
                ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
            ]))
            return tbl

        # 2 columns: 3 left, 2 right + padding
        comp_left  = [[comp_cell(n, s)] for n, s in components[:3]]
        comp_right = [[comp_cell(n, s)] for n, s in components[3:]]
        comp_right += [[Spacer(1, 1)]]  # filler

        def comp_panel(rows):
            t = Table(rows, colWidths=[175])
            t.setStyle(TableStyle([
                ('BACKGROUND',   (0,0),(-1,-1), rc.white),
                ('BOX',          (0,0),(-1,-1), 0.6, BORDER),
                ('LINEBELOW',    (0,0),(-1,-2), 0.4, BORDER),
                ('TOPPADDING',   (0,0),(-1,-1), 10),
                ('BOTTOMPADDING',(0,0),(-1,-1), 10),
                ('LEFTPADDING',  (0,0),(-1,-1), 12),
                ('RIGHTPADDING', (0,0),(-1,-1), 12),
                ('ROUNDEDCORNERS', [5]),
            ]))
            return t

        comp_grid = Table(
            [[comp_panel(comp_left), comp_panel(comp_right)]],
            colWidths=[185, 185], spaceAfter=14
        )
        comp_grid.setStyle(TableStyle([
            ('LEFTPADDING',  (0,0),(-1,-1), 0),
            ('RIGHTPADDING', (0,0),(-1,-1), 0),
            ('TOPPADDING',   (0,0),(-1,-1), 0),
            ('BOTTOMPADDING',(0,0),(-1,-1), 0),
            ('ALIGN',        (0,0),(-1,-1), 'LEFT'),
            ('VALIGN',       (0,0),(-1,-1), 'TOP'),
            ('INNERGRID',    (0,0),(-1,-1), 0, rc.white),
            ('COLPADDING',   (0,0),(0,-1),  [0,8,0,0]),
        ]))
        story.append(comp_grid)
        story.append(Spacer(1, 4))

        # ── 3. Detected Issues ────────────────────────────
        story.append(AccentLine("Detected Issues", accent=RED if persist_issues else GREEN))
        story.append(Spacer(1, 8))

        if persist_issues:
            rows = [[Paragraph("#", white_bold),
                     Paragraph("Issue Description", white_bold),
                     Paragraph("Frequency", white_bold)]]
            for i, iss in enumerate(persist_issues, 1):
                cnt = issue_counts[iss]
                pct = round(cnt / len(results) * 100)
                rows.append([
                    Paragraph(str(i), center9),
                    Paragraph(iss, body_style),
                    Paragraph(f"{pct}%", center9),
                ])
            issue_tbl = Table(rows, colWidths=[22, 290, 60])
            issue_tbl.setStyle(TableStyle([
                ('BACKGROUND',   (0,0),(-1,0),  RED),
                ('TEXTCOLOR',    (0,0),(-1,0),  rc.white),
                ('FONTNAME',     (0,0),(-1,0),  'Helvetica-Bold'),
                ('FONTSIZE',     (0,0),(-1,-1), 9),
                ('ALIGN',        (0,0),(0,-1),  'CENTER'),
                ('ALIGN',        (2,0),(2,-1),  'CENTER'),
                ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
                ('TOPPADDING',   (0,0),(-1,-1), 7),
                ('BOTTOMPADDING',(0,0),(-1,-1), 7),
                ('LEFTPADDING',  (0,0),(-1,-1), 8),
                ('ROWBACKGROUNDS',(0,1),(-1,-1), [rc.HexColor("#fef2f2"), rc.white]),
                ('GRID',         (0,0),(-1,-1), 0.4, rc.HexColor("#fecaca")),
                ('ROUNDEDCORNERS', [4]),
            ]))
            story.append(issue_tbl)
        else:
            ok = Table([[Paragraph("No persistent issues detected across all readings.",
                         ps('ok', fontSize=9, textColor=GREEN, fontName='Helvetica-Bold', leading=14))]],
                       colWidths=[372])
            ok.setStyle(TableStyle([
                ('BACKGROUND',   (0,0),(-1,-1), rc.HexColor("#f0fdf4")),
                ('BOX',          (0,0),(-1,-1), 0.6, GREEN),
                ('TOPPADDING',   (0,0),(-1,-1), 10),
                ('BOTTOMPADDING',(0,0),(-1,-1), 10),
                ('LEFTPADDING',  (0,0),(-1,-1), 12),
                ('ROUNDEDCORNERS', [4]),
            ]))
            story.append(ok)

        story.append(Spacer(1, 14))

        # ── 4. Recommendations ────────────────────────────
        story.append(AccentLine("Recommendations", accent=AMBER))
        story.append(Spacer(1, 8))

        recs = []
        if engine_score     < 60: recs.append("Engine health is below optimal. Schedule a full engine diagnostic immediately.")
        if fuel_score       < 60: recs.append("Fuel system efficiency is low. Check fuel injectors and O2 sensors.")
        if thermal_score    < 60: recs.append("Thermal stress is elevated. Inspect the cooling system and coolant levels.")
        if driving_score    < 60: recs.append("Driving pattern shows aggressive inputs. Reduce hard acceleration and braking.")
        if efficiency_score < 60: recs.append("Engine efficiency is poor. Inspect air filter and spark plugs.")
        if not recs:              recs.append("Vehicle is in good health. Maintain regular service intervals.")

        rec_rows = []
        for i, r in enumerate(recs, 1):
            bg = rc.HexColor("#fffbeb") if i % 2 else rc.white
            rec_rows.append([
                Paragraph(f"<b>{i}</b>", ps('rn', fontSize=9, textColor=AMBER, fontName='Helvetica-Bold',
                                             leading=14, alignment=TA_CENTER)),
                Paragraph(r, body_style)
            ])
        rec_tbl = Table(rec_rows, colWidths=[22, 350])
        rec_tbl.setStyle(TableStyle([
            ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
            ('TOPPADDING',   (0,0),(-1,-1), 7),
            ('BOTTOMPADDING',(0,0),(-1,-1), 7),
            ('LEFTPADDING',  (0,0),(-1,-1), 8),
            ('BOX',          (0,0),(-1,-1), 0.5, BORDER),
            ('LINEBELOW',    (0,0),(-1,-2), 0.4, BORDER),
            ('ROWBACKGROUNDS',(0,0),(-1,-1), [rc.HexColor("#fffbeb"), rc.white]),
            ('ROUNDEDCORNERS', [4]),
        ]))
        story.append(rec_tbl)
        story.append(Spacer(1, 14))

        # ── 5. Scan Summary footer card ───────────────────
        summary_data = [
            [Paragraph("READINGS ANALYSED", muted_style), Paragraph("DATA QUALITY", muted_style),
             Paragraph("ANALYSIS ENGINE", muted_style),   Paragraph("REPORT DATE", muted_style)],
            [Paragraph(f"<b>{len(results)}</b>", bold9),  Paragraph(f"<b>{quality}</b>", bold9),
             Paragraph("<b>Vexis ML v1.0</b>", bold9),    Paragraph(f"<b>{GEN_DATE}</b>", bold9)],
        ]
        sum_tbl = Table(summary_data, colWidths=[90, 90, 100, 92])
        sum_tbl.setStyle(TableStyle([
            ('BACKGROUND',   (0,0),(-1,-1), LGRAY),
            ('BOX',          (0,0),(-1,-1), 0.5, BORDER),
            ('INNERGRID',    (0,0),(-1,-1), 0.4, BORDER),
            ('TOPPADDING',   (0,0),(-1,-1), 7),
            ('BOTTOMPADDING',(0,0),(-1,-1), 7),
            ('LEFTPADDING',  (0,0),(-1,-1), 10),
            ('ALIGN',        (0,0),(-1,-1), 'LEFT'),
            ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
            ('ROUNDEDCORNERS', [4]),
        ]))
        story.append(sum_tbl)




        pdoc.build(story)
        pdf_bytes = buf.getvalue()
        buf.close()

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

