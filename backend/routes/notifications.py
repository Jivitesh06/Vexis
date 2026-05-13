"""
Vexis Notification Blueprint
REST endpoints for notification preferences and test emails.
"""
from flask import Blueprint, request, jsonify
import os
import threading
from utils.firebase_auth import firebase_required
from utils.email_sender import send_email
from utils.email_templates import build_health_email
from datetime import datetime

notifications_bp = Blueprint('notifications', __name__)

# ── Keep-alive endpoint — ping every 13 min to prevent Render sleep ──────────
@notifications_bp.route('/keep-alive', methods=['GET'])
def keep_alive():
    """Lightweight endpoint to keep Render from sleeping on free tier."""
    return jsonify({'status': 'alive', 'ts': datetime.utcnow().isoformat()}), 200


# ── Dedup guard — prevents double-run if cron-job.org retries ────────────────
_cron_lock = threading.Lock()
_last_cron_run = None
_MIN_CRON_INTERVAL_SECONDS = 300  # Don't re-run within 5 minutes of last run


# ── GET /api/notifications/trigger-cron ─────────────────────────────────────
@notifications_bp.route('/notifications/trigger-cron', methods=['GET', 'POST'])
def trigger_cron_endpoint():
    """
    Secure endpoint to trigger the daily cron job via external services (cron-job.org).
    - Protected by secret key
    - Returns 200 IMMEDIATELY so cron-job.org never times out
    - Has a dedup guard: won't run twice within 5 minutes (handles retries)
    - Background thread does the actual work
    """
    global _last_cron_run

    secret = request.args.get('secret') or request.headers.get('X-Cron-Secret', '')
    expected_secret = os.getenv('CRON_SECRET', 'vexis-secret-cron-key')

    if secret != expected_secret:
        return jsonify({'error': 'Unauthorized'}), 401

    now = datetime.utcnow()

    # Dedup guard — if already ran within last 5 mins, skip silently
    if _last_cron_run is not None:
        elapsed = (now - _last_cron_run).total_seconds()
        if elapsed < _MIN_CRON_INTERVAL_SECONDS:
            return jsonify({
                'success': True,
                'message': 'Skipped — already ran recently.',
                'last_run': _last_cron_run.isoformat(),
                'next_eligible_in_seconds': int(_MIN_CRON_INTERVAL_SECONDS - elapsed)
            }), 200

    # Mark as running immediately to block concurrent retries
    _last_cron_run = now

    def _run():
        try:
            from cron_notifications import run_cron
            run_cron()
            print(f'[CRON] Completed at {datetime.utcnow().isoformat()}')
        except Exception as e:
            print(f'[CRON BACKGROUND ERROR] {e}')
            import traceback; traceback.print_exc()

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return jsonify({
        'success': True,
        'message': 'Cron job started in background.',
        'started_at': now.isoformat()
    }), 200


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
