"""
Vexis Timeline API — Bulletproof version
All queries are safe: no order_by (no composite index needed),
None-safe sorts, and every block is individually wrapped in try/except.
"""
from flask import Blueprint, request, jsonify
from utils.firebase_auth import firebase_required
from utils.degradation_predictor import predict_degradation, service_recommendations

timeline_bp = Blueprint('timeline', __name__)


def _db():
    from firebase_admin import firestore
    return firestore.client()


def _safe_sort_key(val):
    """Return a sortable string from any timestamp format."""
    if not val:
        return ''
    if hasattr(val, 'isoformat'):          # datetime object
        return val.isoformat()
    if hasattr(val, 'ToDatetime'):         # Firestore Timestamp
        return val.ToDatetime().isoformat()
    return str(val)


# ── GET /api/vehicles/<vehicle_id>/timeline ──────────────────────────────────
@timeline_bp.route('/vehicles/<string:vehicle_id>/timeline', methods=['GET'])
@firebase_required
def get_vehicle_timeline(vehicle_id):
    try:
        uid = request.user['uid']
        db  = _db()

        vehicle_doc = db.collection('vehicles').document(vehicle_id).get()
        if not vehicle_doc.exists:
            return jsonify({'error': 'Vehicle not found'}), 404
        vehicle_data = vehicle_doc.to_dict() or {}
        if vehicle_data.get('userId') != uid:
            return jsonify({'error': 'Not authorized'}), 403

        meta_doc = db.collection('vehicles').document(vehicle_id)\
                     .collection('notification_meta').document('current').get()
        timeline = meta_doc.to_dict() if meta_doc.exists else {}

        # Fetch reports without order_by (no composite index required)
        try:
            history_docs = db.collection('users').document(uid)\
                             .collection('reports')\
                             .where('vehicle_id', '==', vehicle_id)\
                             .stream()
            report_history = [d.to_dict() for d in history_docs]
            report_history.sort(key=lambda x: _safe_sort_key(x.get('timestamp')), reverse=True)
            report_history = report_history[:15]
        except Exception:
            report_history = []

        try:
            prediction = predict_degradation(report_history)
        except Exception:
            prediction = {
                'current_score': timeline.get('overall_score', 75),
                'velocity': 0.0, 'days_until_poor': None, 'days_until_critical': None,
                'predicted_poor_date': None, 'predicted_critical_date': None,
                'confidence': 'INSUFFICIENT', 'trend': 'stable',
                'needs_service_now': False, 'report_count': 0,
            }

        try:
            recs = service_recommendations(timeline, prediction)
        except Exception:
            recs = []

        return jsonify({
            'success':      True,
            'vehicle_id':   vehicle_id,
            'vehicle_name': vehicle_data.get('name', 'Unknown'),
            'vehicle_model':vehicle_data.get('model', ''),
            'tier':               timeline.get('tier', 'GOOD'),
            'tier_label':         timeline.get('tier_label', 'ROUTINE CHECK'),
            'overall_score':      timeline.get('overall_score', prediction.get('current_score', 75)),
            'trend':              timeline.get('trend', {'direction': 'stable', 'delta': 0.0}),
            'fault_timelines':    timeline.get('fault_timelines', []),
            'component_risks':    timeline.get('component_risks', []),
            'next_notification':  timeline.get('next_notification'),
            'email_freq_days':    timeline.get('email_freq_days', 7),
            'generated_at':       timeline.get('generated_at'),
            'prediction': {
                'current_score':           prediction.get('current_score', 75),
                'velocity':                prediction.get('velocity', 0),
                'trend':                   prediction.get('trend', 'stable'),
                'confidence':              prediction.get('confidence', 'INSUFFICIENT'),
                'report_count':            prediction.get('report_count', 0),
                'needs_service_now':       prediction.get('needs_service_now', False),
                'days_until_poor':         prediction.get('days_until_poor'),
                'days_until_critical':     prediction.get('days_until_critical'),
                'predicted_poor_date':     prediction.get('predicted_poor_date'),
                'predicted_critical_date': prediction.get('predicted_critical_date'),
            },
            'service_recommendations': recs,
        }), 200

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ── GET /api/dashboard/timeline-summary ─────────────────────────────────────
@timeline_bp.route('/dashboard/timeline-summary', methods=['GET'])
@firebase_required
def dashboard_timeline_summary():
    """
    Returns a lightweight summary for the dashboard home card.
    Finds the user's MOST CRITICAL vehicle and returns its prediction.
    This endpoint NEVER returns a 500 — every sub-operation is wrapped in try/except.
    """
    try:
        uid = request.user['uid']
        db  = _db()

        # Step 1: Get all user vehicles
        try:
            vehicles_stream = db.collection('vehicles').where('userId', '==', uid).limit(20).stream()
        except Exception:
            return jsonify({'success': True, 'has_data': False}), 200

        worst       = None
        worst_score = 100.0

        for veh_doc in vehicles_stream:
            try:
                veh_data   = veh_doc.to_dict() or {}
                vehicle_id = veh_doc.id

                meta_doc = db.collection('vehicles').document(vehicle_id)\
                             .collection('notification_meta').document('current').get()
                if not meta_doc.exists:
                    continue

                timeline = meta_doc.to_dict() or {}
                score    = float(timeline.get('overall_score') or 100)

                if score < worst_score:
                    worst_score = score
                    worst = {
                        'vehicle_id':    vehicle_id,
                        'vehicle_name':  veh_data.get('name', 'Unknown'),
                        'vehicle_model': veh_data.get('model', ''),
                        'timeline':      timeline,
                    }
            except Exception:
                continue   # Skip broken vehicle docs silently

        if not worst:
            return jsonify({'success': True, 'has_data': False}), 200

        # Step 2: Load history (without order_by to avoid composite index requirement)
        try:
            history_stream = db.collection('users').document(uid)\
                               .collection('reports')\
                               .where('vehicle_id', '==', worst['vehicle_id'])\
                               .stream()
            report_history = [d.to_dict() for d in history_stream]
            report_history.sort(key=lambda x: _safe_sort_key(x.get('timestamp')), reverse=True)
            report_history = report_history[:15]
        except Exception:
            report_history = []

        # Step 3: Run degradation prediction
        try:
            prediction = predict_degradation(report_history)
        except Exception:
            prediction = {
                'current_score': worst_score, 'velocity': 0.0,
                'days_until_poor': None, 'days_until_critical': None,
                'predicted_poor_date': None, 'predicted_critical_date': None,
                'confidence': 'INSUFFICIENT', 'trend': 'stable',
                'needs_service_now': worst_score < 60, 'report_count': 0,
            }

        # Step 4: Generate service recommendations
        try:
            recs = service_recommendations(worst['timeline'], prediction)
        except Exception:
            recs = []

        return jsonify({
            'success':      True,
            'has_data':     True,
            'vehicle_id':   worst['vehicle_id'],
            'vehicle_name': worst['vehicle_name'],
            'vehicle_model':worst['vehicle_model'],
            'overall_score': worst_score,
            'tier':          worst['timeline'].get('tier', 'GOOD'),
            'tier_label':    worst['timeline'].get('tier_label', 'ROUTINE CHECK'),
            'trend':         worst['timeline'].get('trend', {'direction': 'stable', 'delta': 0}),
            'fault_timelines':    worst['timeline'].get('fault_timelines', [])[:3],
            'component_risks':    worst['timeline'].get('component_risks', []),
            'next_notification':  worst['timeline'].get('next_notification'),
            'prediction': {
                'velocity':                prediction.get('velocity', 0),
                'trend':                   prediction.get('trend', 'stable'),
                'confidence':              prediction.get('confidence', 'INSUFFICIENT'),
                'report_count':            prediction.get('report_count', 0),
                'days_until_poor':         prediction.get('days_until_poor'),
                'days_until_critical':     prediction.get('days_until_critical'),
                'predicted_poor_date':     prediction.get('predicted_poor_date'),
                'predicted_critical_date': prediction.get('predicted_critical_date'),
                'needs_service_now':       prediction.get('needs_service_now', False),
            },
            'service_recommendations': recs[:4],
        }), 200

    except Exception as e:
        import traceback; traceback.print_exc()
        # Even the outer catch returns a valid JSON, never a raw 500
        return jsonify({'success': True, 'has_data': False, '_error': str(e)}), 200
