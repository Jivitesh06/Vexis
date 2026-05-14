"""
Vexis Payments Blueprint — Razorpay Integration
Handles subscription plan creation, payment verification, and status checks.
"""
import os
import hmac
import hashlib
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from utils.firebase_auth import firebase_required

payments_bp = Blueprint('payments', __name__)

# ── Plan definitions ─────────────────────────────────────────────────────────
PLANS = {
    'single': {
        'name':         'Single Report',
        'amount':       4900,           # ₹49 in paise
        'duration_days': None,          # No expiry — just 1 use
        'reports':      1,
        'description':  '1 AI Analysis or PDF Report',
    },
    'explorer': {
        'name':         'Explorer',
        'amount':       9900,           # ₹99 in paise
        'duration_days': 7,
        'reports':      None,           # Unlimited
        'description':  'Unlimited for 7 Days',
    },
    'pro': {
        'name':         'Pro',
        'amount':       19900,          # ₹199 in paise
        'duration_days': 30,
        'reports':      None,
        'description':  'Unlimited for 30 Days',
    },
    'elite': {
        'name':         'Elite',
        'amount':       49900,          # ₹499 in paise
        'duration_days': 365,
        'reports':      None,
        'description':  'Unlimited for 1 Year',
    },
}


def _get_razorpay_client():
    import razorpay
    # Fallback to the test key if env var is missing
    key_id     = os.getenv('RAZORPAY_KEY_ID', 'rzp_test_Sp78k3JIxzjZH1')
    key_secret = os.getenv('RAZORPAY_KEY_SECRET', '')
    return razorpay.Client(auth=(key_id, key_secret))


def _fs():
    from firebase_admin import firestore
    return firestore.client()


def check_subscription(uid: str) -> dict:
    """
    Check if a user has an active subscription.
    Returns {'active': bool, 'plan': str, 'reports_remaining': int|None, 'valid_until': str|None}
    """
    try:
        doc = _fs().collection('users').document(uid) \
                   .collection('subscription').document('current').get()

        if not doc.exists:
            return {'active': False, 'plan': 'free'}

        data = doc.to_dict()
        plan = data.get('plan', 'free')

        if plan == 'single':
            remaining = data.get('reports_remaining', 0)
            if remaining and remaining > 0:
                return {'active': True, 'plan': plan, 'reports_remaining': remaining}
            return {'active': False, 'plan': 'free', 'reports_remaining': 0}

        # Time-based plans
        valid_until = data.get('valid_until')
        if valid_until:
            try:
                expiry = datetime.fromisoformat(valid_until)
                if datetime.utcnow() < expiry:
                    return {
                        'active':      True,
                        'plan':        plan,
                        'valid_until': valid_until,
                        'reports_remaining': None,
                    }
            except Exception:
                pass

        return {'active': False, 'plan': 'free'}

    except Exception as e:
        print(f'[PAYMENTS] check_subscription error: {e}')
        return {'active': False, 'plan': 'free'}


def consume_single_report(uid: str):
    """Decrement reports_remaining for single-plan users. Call after successful analysis."""
    try:
        ref = _fs().collection('users').document(uid) \
                   .collection('subscription').document('current')
        doc = ref.get()
        if doc.exists:
            data = doc.to_dict()
            if data.get('plan') == 'single':
                remaining = data.get('reports_remaining', 0)
                ref.update({'reports_remaining': max(0, remaining - 1)})
    except Exception as e:
        print(f'[PAYMENTS] consume_single_report error: {e}')


# ── POST /api/payments/create-order ─────────────────────────────────────────
@payments_bp.route('/payments/create-order', methods=['POST'])
@firebase_required
def create_order():
    """Create a Razorpay order and return the order_id + key_id to frontend."""
    try:
        body    = request.get_json() or {}
        plan_id = body.get('plan_id', '')

        if plan_id not in PLANS:
            return jsonify({'error': f'Invalid plan: {plan_id}'}), 400

        plan   = PLANS[plan_id]
        client = _get_razorpay_client()

        order = client.order.create({
            'amount':          plan['amount'],
            'currency':        'INR',
            'payment_capture': 1,
            'notes': {
                'plan_id': plan_id,
                'uid':     request.user['uid'],
            },
        })

        return jsonify({
            'order_id':  order['id'],
            'amount':    plan['amount'],
            'currency':  'INR',
            'plan_name': plan['name'],
            'key_id':    os.getenv('RAZORPAY_KEY_ID', 'rzp_test_Sp78k3JIxzjZH1'),
        }), 200

    except Exception as e:
        print(f'[PAYMENTS] create_order error: {e}')
        return jsonify({'error': str(e)}), 500


# ── POST /api/payments/verify ────────────────────────────────────────────────
@payments_bp.route('/payments/verify', methods=['POST'])
@firebase_required
def verify_payment():
    """
    Verify Razorpay signature and activate the subscription in Firestore.
    Called by frontend after Razorpay checkout success callback.
    """
    try:
        body         = request.get_json() or {}
        payment_id   = body.get('razorpay_payment_id', '')
        order_id     = body.get('razorpay_order_id', '')
        signature    = body.get('razorpay_signature', '')
        plan_id      = body.get('plan_id', '')

        if not all([payment_id, order_id, signature, plan_id]):
            return jsonify({'error': 'Missing required payment fields'}), 400

        if plan_id not in PLANS:
            return jsonify({'error': 'Invalid plan'}), 400

        # ── Verify HMAC-SHA256 signature ─────────────────────────────────────
        secret = os.getenv('RAZORPAY_KEY_SECRET', '').encode()
        message = f'{order_id}|{payment_id}'.encode()
        expected_sig = hmac.new(secret, message, hashlib.sha256).hexdigest()

        if expected_sig != signature:
            return jsonify({'error': 'Payment signature verification failed'}), 400

        # ── Activate subscription in Firestore ───────────────────────────────
        plan = PLANS[plan_id]
        now  = datetime.utcnow()
        uid  = request.user['uid']

        sub_data = {
            'plan':                plan_id,
            'razorpay_payment_id': payment_id,
            'razorpay_order_id':   order_id,
            'activated_at':        now.isoformat(),
        }

        if plan['duration_days']:
            sub_data['valid_until']        = (now + timedelta(days=plan['duration_days'])).isoformat()
            sub_data['reports_remaining']  = None
        else:
            # Single-report plan
            sub_data['valid_until']        = None
            sub_data['reports_remaining']  = plan['reports']

        _fs().collection('users').document(uid) \
             .collection('subscription').document('current').set(sub_data)

        print(f'[PAYMENTS] Activated plan={plan_id} for uid={uid} payment={payment_id}')

        return jsonify({
            'success':      True,
            'plan':         plan_id,
            'plan_name':    plan['name'],
            'valid_until':  sub_data.get('valid_until'),
        }), 200

    except Exception as e:
        print(f'[PAYMENTS] verify_payment error: {e}')
        return jsonify({'error': str(e)}), 500


# ── GET /api/payments/status ─────────────────────────────────────────────────
@payments_bp.route('/payments/status', methods=['GET'])
@firebase_required
def payment_status():
    """Return current subscription status for the authenticated user."""
    uid    = request.user['uid']
    status = check_subscription(uid)
    return jsonify(status), 200


# ── GET /api/payments/plans ──────────────────────────────────────────────────
@payments_bp.route('/payments/plans', methods=['GET'])
def get_plans():
    """Return available plans (public endpoint, no auth needed)."""
    return jsonify({
        pid: {
            'name':        p['name'],
            'amount':      p['amount'],
            'amount_inr':  p['amount'] // 100,
            'description': p['description'],
        }
        for pid, p in PLANS.items()
    }), 200
