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

# ── GET /api/notifications ───────────────────────────────────────────────────
@notifications_bp.route('/notifications', methods=['GET'])
@firebase_required
def get_user_notifications():
    """Fetches user-specific vehicle notifications based on service intelligence."""
    try:
        from firebase_admin import firestore
        db = firestore.client()
        uid = request.user['uid']
        
        vehicles_ref = db.collection('vehicles').where('userId', '==', uid).stream()
        vehicles = [v.to_dict() | {'id': v.id} for v in vehicles_ref]
        
        notifications = []
        
        for v in vehicles:
            meta_doc = db.collection('vehicles').document(v['id']).collection('notification_meta').document('current').get()
            if not meta_doc.exists:
                continue
                
            meta = meta_doc.to_dict()
            veh_name = v.get('name', 'Unknown Vehicle')
            
            # Extract risks
            risks = meta.get('component_risks', [])
            for r in risks:
                notifications.append({
                    'id': f"risk_{v['id']}_{r.get('system')}",
                    'vehicle_id': v['id'],
                    'vehicle_name': veh_name,
                    'type': 'critical' if r.get('risk_level') == 'CRITICAL' else 'warning',
                    'title': f"{str(r.get('system', '')).title()} Issue",
                    'message': f"{r.get('issue')} (Confidence: {r.get('confidence')})",
                    'timestamp': meta.get('generated_at', datetime.utcnow().isoformat())
                })
            
            # Extract prediction
            pred = meta.get('prediction', {})
            if pred.get('needs_service_now'):
                notifications.append({
                    'id': f"srv_{v['id']}",
                    'vehicle_id': v['id'],
                    'vehicle_name': veh_name,
                    'type': 'critical',
                    'title': 'Service Required Immediately',
                    'message': f"Overall score is {int(meta.get('overall_score', 0))}/100. Please service your vehicle.",
                    'timestamp': meta.get('generated_at', datetime.utcnow().isoformat())
                })
            elif pred.get('days_until_poor') is not None and pred.get('days_until_poor') <= 7:
                notifications.append({
                    'id': f"srv_warn_{v['id']}",
                    'vehicle_id': v['id'],
                    'vehicle_name': veh_name,
                    'type': 'warning',
                    'title': 'Upcoming Service Recommended',
                    'message': f"Score dropping fast. Estimated poor health in {pred.get('days_until_poor')} days.",
                    'timestamp': meta.get('generated_at', datetime.utcnow().isoformat())
                })
                
            # Extract service recommendations (limit to 1 or 2 so we don't spam)
            recs = meta.get('service_recommendations', [])
            for i, rec in enumerate(recs[:2]):
                notifications.append({
                    'id': f"rec_{v['id']}_{i}",
                    'vehicle_id': v['id'],
                    'vehicle_name': veh_name,
                    'type': 'info',
                    'title': 'Maintenance Tip',
                    'message': rec,
                    'timestamp': meta.get('generated_at', datetime.utcnow().isoformat())
                })

        # Sort notifications by urgency (critical first) then timestamp
        type_priority = {'critical': 0, 'warning': 1, 'info': 2}
        notifications.sort(key=lambda x: (type_priority.get(x['type'], 3), x['timestamp']), reverse=False)
        
        return jsonify({'success': True, 'notifications': notifications}), 200

    except Exception as e:
        print(f"[Notifications API Error] {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


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


# ── GET /api/notifications/test-email  — DEBUG ONLY ─────────────────────────
@notifications_bp.route('/notifications/test-email', methods=['GET'])
def test_email_endpoint():
    """
    Diagnostic endpoint: tries to send a test email synchronously.
    Shows exactly what env vars are set and what error occurs.
    Protected by same cron secret.
    """
    secret = request.args.get('secret') or request.headers.get('X-Cron-Secret', '')
    expected_secret = os.getenv('CRON_SECRET', 'vexis-secret-cron-key')
    if secret != expected_secret:
        return jsonify({'error': 'Unauthorized'}), 401

    mail_email    = os.getenv('MAIL_EMAIL', '')
    mail_password = os.getenv('MAIL_PASSWORD', '')
    to_email      = request.args.get('to', mail_email) or 'jiviteshgarg30@gmail.com'

    env_status = {
        'MAIL_EMAIL_set':    bool(mail_email),
        'MAIL_EMAIL':        mail_email[:4] + '***' if mail_email else 'NOT SET',
        'MAIL_PASSWORD_set': bool(mail_password),
        'CRON_SECRET_set':   bool(os.getenv('CRON_SECRET')),
    }

    if not mail_email or not mail_password:
        return jsonify({
            'success': False,
            'error': 'MAIL_EMAIL or MAIL_PASSWORD not set on this server!',
            'env': env_status
        }), 500

    ok, msg = send_email(
        to_email,
        'Vexis Test Email — Cron Diagnostic',
        '<h2>Vexis Test Email</h2><p>If you see this, email sending works on Render!</p>'
    )
    return jsonify({'success': ok, 'message': msg, 'to': to_email, 'env': env_status}), 200 if ok else 500


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
