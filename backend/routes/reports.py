from flask import Blueprint, request, jsonify, make_response
from utils.firebase_auth import firebase_required, get_or_create_user
from database import execute_query
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
import json
import io
from datetime import datetime

reports_bp = Blueprint('reports', __name__)


def _score_label(score):
    if score is None: return "N/A"
    s = float(score)
    if s >= 90: return "Excellent"
    if s >= 75: return "Good"
    if s >= 60: return "Fair"
    if s >= 40: return "Poor"
    return "Critical"


def _get_user_id(uid, email):
    """Get DB user_id — returns None if DB unavailable."""
    try:
        db_user = get_or_create_user(uid, email)
        return db_user['id'] if db_user else None
    except Exception as e:
        print(f"[WARN] DB unavailable: {e}")
        return None


# ─────────────────────────────────────────────────────────────────
# GET /reports
# Optional ?vehicle_name=X  for per-vehicle filter
# ─────────────────────────────────────────────────────────────────
@reports_bp.route('/reports', methods=['GET'])
@firebase_required
def get_reports():
    try:
        user_id = _get_user_id(request.user['uid'], request.user['email'])
        if user_id is None:
            return jsonify({"success": True, "reports": [], "count": 0,
                            "warning": "Database unavailable"}), 200

        vehicle_filter = request.args.get('vehicle_name', '').strip()

        if vehicle_filter:
            rows = execute_query(
                """SELECT id, timestamp, overall_score, status_label,
                          engine_score, fuel_score, stress_score,
                          failure_risk, raw_input, issues
                   FROM reports
                   WHERE user_id = %s AND raw_input::text ILIKE %s
                   ORDER BY timestamp DESC""",
                (user_id, f'%{vehicle_filter}%'),
                fetchall=True
            )
        else:
            rows = execute_query(
                """SELECT id, timestamp, overall_score, status_label,
                          engine_score, fuel_score, stress_score,
                          failure_risk, raw_input, issues
                   FROM reports
                   WHERE user_id = %s
                   ORDER BY timestamp DESC""",
                (user_id,),
                fetchall=True
            )

        reports = []
        for row in (rows or []):
            raw, issues = {}, []
            try:
                raw = json.loads(row['raw_input']) if row['raw_input'] else {}
            except Exception:
                pass
            try:
                issues = json.loads(row['issues']) if row['issues'] else []
            except Exception:
                pass

            reports.append({
                "id":            row['id'],
                "timestamp":     str(row['timestamp']),
                "overall_score": float(row['overall_score'] or 0),
                "status_label":  row['status_label'] or _score_label(row['overall_score']),
                "engine_score":  float(row['engine_score'] or 0),
                "fuel_score":    float(row['fuel_score']   or 0),
                "stress_score":  float(row['stress_score'] or 0),
                "failure_risk":  bool(row['failure_risk']),
                "vehicle_name":  raw.get('vehicle_name') or raw.get('vehicle'),
                "vehicle_model": raw.get('vehicle_model'),
                "vehicle_id":    raw.get('vehicle_id'),
                "source":        raw.get('source', 'live_obd'),
                "issues":        issues,
            })

        return jsonify({"success": True, "reports": reports, "count": len(reports)}), 200

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────
# DELETE /reports/<id>
# ─────────────────────────────────────────────────────────────────
@reports_bp.route('/reports/<int:report_id>', methods=['DELETE'])
@firebase_required
def delete_report(report_id):
    try:
        user_id = _get_user_id(request.user['uid'], request.user['email'])
        if user_id is None:
            return jsonify({"error": "Database unavailable"}), 503

        existing = execute_query(
            "SELECT id FROM reports WHERE id = %s AND user_id = %s",
            (report_id, user_id), fetchone=True
        )
        if not existing:
            return jsonify({"error": "Report not found"}), 404

        execute_query(
            "DELETE FROM reports WHERE id = %s AND user_id = %s",
            (report_id, user_id), commit=True
        )
        return jsonify({"success": True, "message": "Report deleted"}), 200

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────
# GET /reports/<id>
# ─────────────────────────────────────────────────────────────────
@reports_bp.route('/reports/<int:report_id>', methods=['GET'])
@firebase_required
def get_report(report_id):
    try:
        user_id = _get_user_id(request.user['uid'], request.user['email'])
        if user_id is None:
            return jsonify({"error": "Database unavailable"}), 503

        report = execute_query(
            "SELECT * FROM reports WHERE id = %s AND user_id = %s",
            (report_id, user_id), fetchone=True
        )
        if not report:
            return jsonify({"error": "Report not found"}), 404

        raw = report['raw_input']
        issues = report['issues']
        if isinstance(raw, str):    raw    = json.loads(raw)
        if isinstance(issues, str): issues = json.loads(issues)

        return jsonify({"success": True, "report": {
            "id":            report['id'],
            "timestamp":     str(report['timestamp']),
            "overall_score": float(report['overall_score'] or 0),
            "engine_score":  float(report['engine_score']  or 0),
            "fuel_score":    float(report['fuel_score']    or 0),
            "stress_score":  float(report['stress_score']  or 0),
            "failure_risk":  bool(report['failure_risk']),
            "status_label":  report['status_label'],
            "raw_input":     raw,
            "issues":        issues
        }}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────
# GET /reports/download/<id>
# ─────────────────────────────────────────────────────────────────
@reports_bp.route('/reports/download/<int:report_id>', methods=['GET'])
@firebase_required
def download_report(report_id):
    try:
        user_id = _get_user_id(request.user['uid'], request.user['email'])
        if user_id is None:
            return jsonify({"error": "Database unavailable"}), 503

        report = execute_query(
            "SELECT * FROM reports WHERE id = %s AND user_id = %s",
            (report_id, user_id), fetchone=True
        )
        if not report:
            return jsonify({"error": "Not found"}), 404

        issues = report['issues']
        raw    = report['raw_input']
        if isinstance(issues, str): issues = json.loads(issues)
        if isinstance(raw, str):    raw    = json.loads(raw)
        if not isinstance(raw, dict): raw  = {}

        vehicle_name  = raw.get('vehicle_name') or raw.get('vehicle', 'Unknown Vehicle')
        vehicle_model = raw.get('vehicle_model', '')
        source        = raw.get('source', 'live_obd')

        engine_score  = float(report['engine_score']  or 0)
        fuel_score    = float(report['fuel_score']    or 0)
        driving_score = float(report['stress_score']  or 0)
        overall_score = float(report['overall_score'] or 0)

        buffer = io.BytesIO()
        doc    = SimpleDocTemplate(buffer, pagesize=letter,
                                   rightMargin=50, leftMargin=50,
                                   topMargin=60, bottomMargin=40)
        styles = getSampleStyleSheet()
        story  = []

        story.append(Paragraph("VEXIS — Vehicle Health Report", styles['Title']))
        story.append(Spacer(1, 4))
        veh_str = vehicle_name + (f" — {vehicle_model}" if vehicle_model else "")
        story.append(Paragraph(f"Vehicle: <b>{veh_str}</b>", styles['Normal']))
        src_str = "CSV Upload" if 'csv' in source else "Live OBD Scan"
        story.append(Paragraph(
            f"Source: {src_str}  |  Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}",
            styles['Normal']
        ))
        story.append(Spacer(1, 20))

        story.append(Paragraph("<b>Health Summary</b>", styles['Heading2']))
        story.append(Spacer(1, 8))
        summary_data = [
            ["Component",     "Score",                  "Status"],
            ["Engine",        f"{engine_score:.1f}",    _score_label(engine_score)],
            ["Fuel System",   f"{fuel_score:.1f}",      _score_label(fuel_score)],
            ["Driving",       f"{driving_score:.1f}",   _score_label(driving_score)],
            ["Overall Score", f"{overall_score:.1f}",   report['status_label'] or "N/A"],
        ]
        table = Table(summary_data, colWidths=[180, 120, 150])
        table.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0), colors.black),
            ('TEXTCOLOR',     (0,0), (-1,0), colors.white),
            ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0,0), (-1,-1), 10),
            ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING',    (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('GRID',          (0,0), (-1,-1), 0.5, colors.grey),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.whitesmoke, colors.lightgrey]),
        ]))
        story.append(table)
        story.append(Spacer(1, 20))

        story.append(Paragraph("<b>Detected Issues</b>", styles['Heading2']))
        story.append(Spacer(1, 8))
        if issues:
            for issue in issues:
                story.append(Paragraph(f"• {issue}", styles['Normal']))
                story.append(Spacer(1, 4))
        else:
            story.append(Paragraph("No issues detected. Vehicle in good health.", styles['Normal']))

        story.append(Spacer(1, 20))
        story.append(Paragraph("<b>Risk Assessment</b>", styles['Heading2']))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            f"Failure Risk: <b>{'At Risk' if report['failure_risk'] else 'Healthy'}</b>",
            styles['Normal']
        ))
        story.append(Paragraph(
            f"Overall Status: <b>{report['status_label'] or 'N/A'}</b>",
            styles['Normal']
        ))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        resp = make_response(pdf_bytes)
        resp.headers['Content-Type']        = 'application/pdf'
        resp.headers['Content-Disposition'] = f'attachment; filename=vexis_report_{report_id}.pdf'
        return resp

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": "PDF generation failed"}), 500
