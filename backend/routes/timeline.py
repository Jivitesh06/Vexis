"""
Vexis Timeline API
Returns full service intelligence data for a vehicle.
"""
from flask import Blueprint, request, jsonify
from utils.firebase_auth import firebase_required
from utils.degradation_predictor import predict_degradation, service_recommendations

timeline_bp = Blueprint('timeline', __name__)


def _db():
    from firebase_admin import firestore
    return firestore.client()


# ── GET /api/vehicles/<vehicle_id>/timeline ──────────────────────────────────
@timeline_bp.route('/vehicles/<string:vehicle_id>/timeline', methods=['GET'])
@firebase_required
def get_vehicle_timeline(vehicle_id):
    """
    Returns full service intelligence for a vehicle:
    - Current timeline (tier, score, faults, component risks)
    - AI degradation prediction (when will it hit POOR / CRITICAL)
    - Ranked service recommendations
    """
    try:
        uid = request.user['uid']
        db  = _db()

        # ── Verify vehicle ownership ────────────────────────────────────────
        vehicle_doc = db.collection('vehicles').document(vehicle_id).get()
        if not vehicle_doc.exists:
            return jsonify({'error': 'Vehicle not found'}), 404
        vehicle_data = vehicle_doc.to_dict()
        if vehicle_data.get('userId') != uid:
            return jsonify({'error': 'Not authorized'}), 403

        # ── Load notification_meta/current ──────────────────────────────────
        meta_doc = db.collection('vehicles').document(vehicle_id)\
                     .collection('notification_meta').document('current').get()

        timeline = meta_doc.to_dict() if meta_doc.exists else {}

        # ── Load historical reports (for degradation prediction) ────────────
        history_docs = db.collection('users').document(uid)\
                         .collection('reports')\
                         .where('vehicle_id', '==', vehicle_id)\
                         .stream()

        report_history = [d.to_dict() for d in history_docs]
        report_history.sort(key=lambda x: x.get('timestamp', '') or '', reverse=True)
        report_history = report_history[:15]

        # ── Run degradation prediction ──────────────────────────────────────
        prediction = predict_degradation(report_history)

        # ── Generate ranked service recommendations ─────────────────────────
        recs = service_recommendations(timeline, prediction)

        # ── Build response ──────────────────────────────────────────────────
        return jsonify({
            'success':      True,
            'vehicle_id':   vehicle_id,
            'vehicle_name': vehicle_data.get('name', 'Unknown'),
            'vehicle_model':vehicle_data.get('model', ''),

            # Current health state from timeline engine
            'tier':               timeline.get('tier', 'GOOD'),
            'tier_label':         timeline.get('tier_label', 'ROUTINE CHECK'),
            'overall_score':      timeline.get('overall_score', prediction.get('current_score', 75)),
            'trend':              timeline.get('trend', {'direction': 'stable', 'delta': 0.0}),
            'fault_timelines':    timeline.get('fault_timelines', []),
            'component_risks':    timeline.get('component_risks', []),
            'next_notification':  timeline.get('next_notification'),
            'email_freq_days':    timeline.get('email_freq_days', 7),
            'generated_at':       timeline.get('generated_at'),

            # AI Degradation Forecast
            'prediction': {
                'current_score':          prediction['current_score'],
                'velocity':               prediction['velocity'],
                'trend':                  prediction['trend'],
                'confidence':             prediction['confidence'],
                'report_count':           prediction['report_count'],
                'needs_service_now':      prediction['needs_service_now'],
                'days_until_poor':        prediction['days_until_poor'],
                'days_until_critical':    prediction['days_until_critical'],
                'predicted_poor_date':    prediction['predicted_poor_date'],
                'predicted_critical_date':prediction['predicted_critical_date'],
            },

            # Ranked service actions
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
    Used to power the "Service Intelligence" card without knowing vehicle_id.
    """
    try:
        uid = request.user['uid']
        db  = _db()

        # Get all user vehicles
        vehicles = db.collection('vehicles').where('userId', '==', uid)\
                     .limit(20).stream()

        worst   = None
        worst_score = 100.0

        for veh_doc in vehicles:
            veh_data   = veh_doc.to_dict()
            vehicle_id = veh_doc.id

            # Get the timeline for this vehicle
            meta_doc = db.collection('vehicles').document(vehicle_id)\
                         .collection('notification_meta').document('current').get()
            if not meta_doc.exists:
                continue

            timeline = meta_doc.to_dict()
            score    = timeline.get('overall_score', 100)

            if score < worst_score:
                worst_score = score
                worst = {
                    'vehicle_id':   vehicle_id,
                    'vehicle_name': veh_data.get('name', 'Unknown'),
                    'vehicle_model':veh_data.get('model', ''),
                    'timeline':     timeline,
                }

        if not worst:
            return jsonify({'success': True, 'has_data': False}), 200

        # Run prediction on this vehicle's history (sort in python to avoid index requirement)
        history_docs = db.collection('users').document(uid)\
                         .collection('reports')\
                         .where('vehicle_id', '==', worst['vehicle_id'])\
                         .stream()
        report_history = [d.to_dict() for d in history_docs]
        report_history.sort(key=lambda x: x.get('timestamp', '') or '', reverse=True)
        report_history = report_history[:15]
        prediction     = predict_degradation(report_history)
        recs           = service_recommendations(worst['timeline'], prediction)

        return jsonify({
            'success':   True,
            'has_data':  True,
            'vehicle_id':   worst['vehicle_id'],
            'vehicle_name': worst['vehicle_name'],
            'vehicle_model':worst['vehicle_model'],
            'overall_score': worst_score,
            'tier':       worst['timeline'].get('tier', 'GOOD'),
            'tier_label': worst['timeline'].get('tier_label', 'ROUTINE CHECK'),
            'trend':      worst['timeline'].get('trend', {'direction': 'stable', 'delta': 0}),
            'fault_timelines': worst['timeline'].get('fault_timelines', [])[:3],
            'component_risks': worst['timeline'].get('component_risks', []),
            'next_notification': worst['timeline'].get('next_notification'),
            'prediction': {
                'velocity':             prediction['velocity'],
                'trend':                prediction['trend'],
                'confidence':           prediction['confidence'],
                'report_count':         prediction['report_count'],
                'days_until_poor':      prediction['days_until_poor'],
                'days_until_critical':  prediction['days_until_critical'],
                'predicted_poor_date':  prediction['predicted_poor_date'],
                'predicted_critical_date': prediction['predicted_critical_date'],
                'needs_service_now':    prediction['needs_service_now'],
            },
            'service_recommendations': recs[:4],  # Top 4 for dashboard card
        }), 200

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500
