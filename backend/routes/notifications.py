"""
Vexis Notification Blueprint
REST endpoints for notification preferences and test emails.
"""
from flask import Blueprint, request, jsonify
import os
from utils.firebase_auth import firebase_required
from utils.email_sender import send_email
from utils.email_templates import build_health_email
from datetime import datetime

notifications_bp = Blueprint('notifications', __name__)

# ── GET /api/notifications/trigger-cron ─────────────────────────────────
@notifications_bp.route('/notifications/trigger-cron', methods=['GET'])
def trigger_cron_endpoint():
    """
    Secure endpoint to trigger the daily cron job via external services (cron-job.org).
    Requires a secret token to prevent unauthorized execution.
    """
    secret = request.args.get('secret')
    expected_secret = os.getenv('CRON_SECRET', 'vexis-secret-cron-key')
    
    if secret != expected_secret:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        from cron_notifications import run_cron
        # Run it synchronously since it only takes a few seconds
        run_cron()
        return jsonify({'success': True, 'message': 'Cron job executed successfully.'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── GET /api/notifications/preferences ──────────────────────────────────
@notifications_bp.route('/notifications/preferences', methods=['GET'])
@firebase_required
def get_preferences():
    """Return the user's current notification settings from Firestore."""
    try:
        import firebase_admin
        from firebase_admin import firestore
        db  = firestore.client()
        uid = request.user['uid']
        doc = db.collection('users').document(uid)\
                .collection('settings').document('notifications').get()
        data = doc.to_dict() if doc.exists else {
            'enabled': True,
            'frequency': 'auto',  # auto | daily | weekly | monthly
        }
        return jsonify({'success': True, 'preferences': data}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── POST /api/notifications/preferences ─────────────────────────────────
@notifications_bp.route('/notifications/preferences', methods=['POST'])
@firebase_required
def update_preferences():
    """Update the user's notification preferences in Firestore."""
    try:
        import firebase_admin
        from firebase_admin import firestore
        db   = firestore.client()
        uid  = request.user['uid']
        body = request.get_json() or {}

        prefs = {
            'enabled':   body.get('enabled', True),
            'frequency': body.get('frequency', 'auto'),
            'updated_at': datetime.utcnow().isoformat(),
        }
        db.collection('users').document(uid)\
          .collection('settings').document('notifications').set(prefs)

        return jsonify({'success': True, 'preferences': prefs}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── POST /api/notifications/test ────────────────────────────────────────
@notifications_bp.route('/notifications/test', methods=['POST'])
@firebase_required
def send_test_email():
    """Send a test health notification email to the authenticated user."""
    try:
        user = request.user
        body = request.get_json() or {}

        # Build a sample timeline for the test
        sample_timeline = {
            'tier': 'FAIR',
            'tier_label': 'SERVICE REQUIRED',
            'overall_score': 62,
            'trend': {'direction': 'declining', 'delta': -8.0},
            'next_notification': datetime.utcnow().isoformat(),
            'email_freq_days': 7,
            'fault_timelines': [
                {
                    'issue': 'High RPM fluctuation detected',
                    'frequency_pct': 75,
                    'priority': 'URGENT',
                    'priority_label': 'URGENT',
                    'color': '#ef4444',
                    'repair_by': '16 May 2026',
                    'days_remaining': 7,
                },
                {
                    'issue': 'Fuel trim out of range',
                    'frequency_pct': 45,
                    'priority': 'HIGH',
                    'priority_label': 'HIGH',
                    'color': '#f97316',
                    'repair_by': '23 May 2026',
                    'days_remaining': 14,
                },
            ],
            'component_risks': [
                {
                    'component': 'Engine',
                    'score': 55,
                    'tier': 'POOR',
                    'action': 'Service Engine within 7 days.',
                }
            ],
        }

        email_data = build_health_email(
            user_name    = user.get('name', ''),
            user_email   = user['email'],
            vehicle_name = body.get('vehicle_name', 'Test Vehicle'),
            vehicle_model= body.get('vehicle_model', ''),
            timeline     = sample_timeline,
        )

        try:
            ok, err_msg = send_email(user['email'], email_data['subject'], email_data['html'])
        except Exception as smtp_err:
            ok, err_msg = False, str(smtp_err)
            
        if ok:
            return jsonify({'success': True, 'message': f'Test email sent to {user["email"]}'}), 200
        else:
            return jsonify({'error': f'Email sending failed: {err_msg}'}), 500

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500
