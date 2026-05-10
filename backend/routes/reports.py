"""
reports.py — Firestore-only report management
No PostgreSQL dependency.
"""
from flask import Blueprint, request, jsonify, make_response
from utils.firebase_auth import firebase_required
from datetime import datetime
import base64

reports_bp = Blueprint('reports', __name__)


def _db():
    from firebase_admin import firestore
    return firestore.client()


def _score_label(score):
    if score is None: return "N/A"
    s = float(score)
    if s >= 90: return "Excellent"
    if s >= 75: return "Good"
    if s >= 60: return "Fair"
    if s >= 40: return "Poor"
    return "Critical"


# ── GET /api/reports ─────────────────────────────────────────────────────
@reports_bp.route('/reports', methods=['GET'])
@firebase_required
def get_reports():
    try:
        uid          = request.user['uid']
        db           = _db()
        vehicle_filter = request.args.get('vehicle_name', '').strip().lower()

        docs = db.collection('users').document(uid)\
                 .collection('reports')\
                 .order_by('timestamp', direction='DESCENDING')\
                 .limit(50)\
                 .stream()

        reports = []
        for doc in docs:
            d = doc.to_dict()
            # Filter by vehicle name if requested
            vname = (d.get('vehicle_name') or '').lower()
            if vehicle_filter and vehicle_filter not in vname:
                continue

            # Normalize timestamp
            ts = d.get('timestamp', '')
            if hasattr(ts, 'isoformat'):
                ts = ts.isoformat()

            reports.append({
                "id":            doc.id,
                "timestamp":     ts,
                "overall_score": float(d.get('overall_score') or 0),
                "status_label":  d.get('status_label') or _score_label(d.get('overall_score')),
                "engine_score":  float(d.get('engine_score')  or 0),
                "fuel_score":    float(d.get('fuel_score')    or 0),
                "efficiency_score": float(d.get('efficiency_score') or 0),
                "driving_score": float(d.get('driving_score') or 0),
                "thermal_score": float(d.get('thermal_score') or 0),
                "failure_risk":  bool(d.get('failure_risk')),
                "vehicle_name":  d.get('vehicle_name'),
                "vehicle_model": d.get('vehicle_model'),
                "vehicle_id":    d.get('vehicle_id'),
                "source":        d.get('source', 'csv_upload'),
                "issues":        d.get('issues', []),
                "quality":       d.get('quality', ''),
                "has_pdf":       bool(d.get('pdf_base64')),
            })

        return jsonify({"success": True, "reports": reports, "count": len(reports)}), 200

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ── GET /api/reports/<id> ────────────────────────────────────────────────
@reports_bp.route('/reports/<string:report_id>', methods=['GET'])
@firebase_required
def get_report(report_id):
    try:
        uid = request.user['uid']
        db  = _db()
        doc = db.collection('users').document(uid)\
                .collection('reports').document(report_id).get()

        if not doc.exists:
            return jsonify({"error": "Report not found"}), 404

        d  = doc.to_dict()
        ts = d.get('timestamp', '')
        if hasattr(ts, 'isoformat'):
            ts = ts.isoformat()

        return jsonify({"success": True, "report": {
            "id":            doc.id,
            "timestamp":     ts,
            "overall_score": float(d.get('overall_score') or 0),
            "engine_score":  float(d.get('engine_score')  or 0),
            "fuel_score":    float(d.get('fuel_score')    or 0),
            "efficiency_score": float(d.get('efficiency_score') or 0),
            "driving_score": float(d.get('driving_score') or 0),
            "thermal_score": float(d.get('thermal_score') or 0),
            "failure_risk":  bool(d.get('failure_risk')),
            "status_label":  d.get('status_label'),
            "issues":        d.get('issues', []),
            "vehicle_name":  d.get('vehicle_name'),
            "vehicle_model": d.get('vehicle_model'),
            "has_pdf":       bool(d.get('pdf_base64')),
        }}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── DELETE /api/reports/<id> ─────────────────────────────────────────────
@reports_bp.route('/reports/<string:report_id>', methods=['DELETE'])
@firebase_required
def delete_report(report_id):
    try:
        uid = request.user['uid']
        db  = _db()
        ref = db.collection('users').document(uid)\
                .collection('reports').document(report_id)

        if not ref.get().exists:
            return jsonify({"error": "Report not found"}), 404

        ref.delete()
        return jsonify({"success": True, "message": "Report deleted"}), 200

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ── GET /api/reports/download/<id> ──────────────────────────────────────
@reports_bp.route('/reports/download/<string:report_id>', methods=['GET'])
@firebase_required
def download_report(report_id):
    """Return the stored premium PDF for a given report."""
    try:
        uid = request.user['uid']
        db  = _db()
        doc = db.collection('users').document(uid)\
                .collection('reports').document(report_id).get()

        if not doc.exists:
            return jsonify({"error": "Report not found"}), 404

        d = doc.to_dict()
        pdf_b64 = d.get('pdf_base64')

        if not pdf_b64:
            return jsonify({"error": "PDF not available for this report"}), 404

        pdf_bytes = base64.b64decode(pdf_b64)
        vname     = (d.get('vehicle_name') or 'report').replace(' ', '_')

        resp = make_response(pdf_bytes)
        resp.headers['Content-Type']        = 'application/pdf'
        resp.headers['Content-Disposition'] = f'attachment; filename=vexis_{vname}_{report_id[:8]}.pdf'
        return resp

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": "PDF download failed"}), 500
