from flask import Blueprint, request, jsonify, make_response
from utils.jwt_helper import jwt_required
from database import execute_query
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
import json
import io
from datetime import datetime

reports_bp = Blueprint('reports', __name__)


# ──────────────────────────────────────────────────────────────────
# Helper — derive status label from a numeric score
# ──────────────────────────────────────────────────────────────────
def _score_label(score):
    if score is None:
        return "N/A"
    s = float(score)
    if s >= 90: return "Excellent"
    if s >= 75: return "Good"
    if s >= 60: return "Fair"
    if s >= 40: return "Poor"
    return "Critical"


# ──────────────────────────────────────────────────────────────────
# GET /reports  [jwt_required]
# ──────────────────────────────────────────────────────────────────
@reports_bp.route('/reports', methods=['GET'])
@jwt_required
def get_reports():
    try:
        user_id = request.user['user_id']

        rows = execute_query(
            """
            SELECT id, timestamp, overall_score, status_label,
                   engine_score, fuel_score, stress_score, failure_risk
            FROM reports
            WHERE user_id = %s
            ORDER BY timestamp DESC
            """,
            (user_id,),
            fetchall=True
        )

        reports = []
        for row in (rows or []):
            reports.append({
                "id":            row['id'],
                "timestamp":     str(row['timestamp']),
                "overall_score": row['overall_score'],
                "status_label":  row['status_label'],
                "engine_score":  row['engine_score'],
                "fuel_score":    row['fuel_score'],
                "stress_score":  row['stress_score'],
                "failure_risk":  row['failure_risk']
            })

        return jsonify({
            "success": True,
            "reports": reports,
            "count":   len(reports)
        }), 200

    except Exception as e:
        print(f"[get_reports error] {e}")
        return jsonify({"error": "Failed"}), 500


# ──────────────────────────────────────────────────────────────────
# GET /reports/<report_id>  [jwt_required]
# ──────────────────────────────────────────────────────────────────
@reports_bp.route('/reports/<int:report_id>', methods=['GET'])
@jwt_required
def get_report(report_id):
    try:
        user_id = request.user['user_id']

        report = execute_query(
            "SELECT * FROM reports WHERE id = %s AND user_id = %s",
            (report_id, user_id),
            fetchone=True
        )
        if not report:
            return jsonify({"error": "Report not found"}), 404

        # Safely parse JSON strings stored in DB
        raw_input = report['raw_input']
        issues    = report['issues']
        if isinstance(raw_input, str):
            raw_input = json.loads(raw_input)
        if isinstance(issues, str):
            issues = json.loads(issues)

        return jsonify({
            "success": True,
            "report": {
                "id":            report['id'],
                "user_id":       report['user_id'],
                "timestamp":     str(report['timestamp']),
                "engine_score":  report['engine_score'],
                "fuel_score":    report['fuel_score'],
                "stress_score":  report['stress_score'],
                "overall_score": report['overall_score'],
                "failure_risk":  report['failure_risk'],
                "status_label":  report['status_label'],
                "raw_input":     raw_input,
                "issues":        issues
            }
        }), 200

    except Exception as e:
        print(f"[get_report error] {e}")
        return jsonify({"error": "Failed"}), 500


# ──────────────────────────────────────────────────────────────────
# GET /reports/download/<report_id>  [jwt_required]
# ──────────────────────────────────────────────────────────────────
@reports_bp.route('/reports/download/<int:report_id>', methods=['GET'])
@jwt_required
def download_report(report_id):
    try:
        user_id = request.user['user_id']

        report = execute_query(
            "SELECT * FROM reports WHERE id = %s AND user_id = %s",
            (report_id, user_id),
            fetchone=True
        )
        if not report:
            return jsonify({"error": "Not found"}), 404

        # Parse issues JSON
        issues = report['issues']
        if isinstance(issues, str):
            issues = json.loads(issues)

        # ── Build PDF in memory ───────────────────────────────────
        buffer = io.BytesIO()
        doc    = SimpleDocTemplate(buffer, pagesize=letter,
                                   rightMargin=50, leftMargin=50,
                                   topMargin=60, bottomMargin=40)
        styles  = getSampleStyleSheet()
        story   = []

        # ── Title ─────────────────────────────────────────────────
        title_style = styles['Title']
        story.append(Paragraph("VEXIS — Vehicle Health Report", title_style))
        story.append(Spacer(1, 6))

        sub_style = styles['Normal']
        generated = datetime.now().strftime('%Y-%m-%d %H:%M')
        story.append(Paragraph(f"Generated: {generated}", sub_style))
        story.append(Spacer(1, 20))

        # ── Section 1: Health Summary Table ───────────────────────
        story.append(Paragraph("<b>Health Summary</b>", styles['Heading2']))
        story.append(Spacer(1, 8))

        engine_score  = float(report['engine_score']  or 0)
        fuel_score    = float(report['fuel_score']    or 0)
        driving_score = float(report['stress_score']  or 0)
        overall_score = float(report['overall_score'] or 0)

        summary_data = [
            ["Component",     "Score",                        "Status"],
            ["Engine",        f"{engine_score:.1f}",          _score_label(engine_score)],
            ["Fuel System",   f"{fuel_score:.1f}",            _score_label(fuel_score)],
            ["Driving",       f"{driving_score:.1f}",         _score_label(driving_score)],
            ["Overall Score", f"{overall_score:.1f}",         report['status_label'] or "N/A"],
        ]

        col_widths = [180, 120, 150]
        table      = Table(summary_data, colWidths=col_widths)
        table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND',    (0, 0), (-1, 0),  colors.black),
            ('TEXTCOLOR',     (0, 0), (-1, 0),  colors.white),
            ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, 0),  11),
            ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUND', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            # Alternating row colours
            ('BACKGROUND',    (0, 1), (-1, 1),  colors.whitesmoke),
            ('BACKGROUND',    (0, 2), (-1, 2),  colors.lightgrey),
            ('BACKGROUND',    (0, 3), (-1, 3),  colors.whitesmoke),
            ('BACKGROUND',    (0, 4), (-1, 4),  colors.lightgrey),
            ('FONTSIZE',      (0, 1), (-1, -1), 10),
            ('TOPPADDING',    (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID',          (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(table)
        story.append(Spacer(1, 20))

        # ── Section 2: Detected Issues ────────────────────────────
        story.append(Paragraph("<b>Detected Issues</b>", styles['Heading2']))
        story.append(Spacer(1, 8))

        if issues:
            for issue in issues:
                story.append(Paragraph(f"• {issue}", styles['Normal']))
                story.append(Spacer(1, 4))
        else:
            story.append(Paragraph("No issues detected.", styles['Normal']))
        story.append(Spacer(1, 20))

        # ── Section 3: Risk Assessment ────────────────────────────
        story.append(Paragraph("<b>Risk Assessment</b>", styles['Heading2']))
        story.append(Spacer(1, 8))

        risk_text   = "At Risk" if report['failure_risk'] else "Healthy"
        status_text = report['status_label'] or "N/A"
        story.append(Paragraph(f"Failure Risk:  <b>{risk_text}</b>",  styles['Normal']))
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"Overall Status: <b>{status_text}</b>", styles['Normal']))

        # ── Build and return PDF ───────────────────────────────────
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        response = make_response(pdf_bytes)
        response.headers['Content-Type']        = 'application/pdf'
        response.headers['Content-Disposition'] = (
            f'attachment; filename=vexis_report_{report_id}.pdf'
        )
        return response

    except Exception as e:
        print(f"[download_report error] {e}")
        return jsonify({"error": "PDF generation failed"}), 500
