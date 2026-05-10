"""
auth.py — Firestore-only authentication routes
No PostgreSQL dependency.
"""
from flask import Blueprint, request, jsonify
from utils.firebase_auth import firebase_required, verify_firebase_token, init_firebase
from datetime import datetime

auth_bp = Blueprint('auth', __name__)
init_firebase()


def _db():
    from firebase_admin import firestore
    return firestore.client()


# ── POST /api/auth/verify-token ──────────────────────────────────────────
@auth_bp.route('/verify-token', methods=['POST'])
def verify_token():
    try:
        data  = request.get_json() or {}
        token = data.get('token')
        if not token:
            return jsonify({"error": "Token required"}), 400

        user = verify_firebase_token(token)
        if not user:
            return jsonify({"error": "Invalid token"}), 401

        # Upsert basic profile in Firestore (best-effort)
        try:
            db = _db()
            db.collection('users').document(user['uid']).set({
                'email':      user['email'],
                'name':       user.get('name', ''),
                'last_login': datetime.utcnow().isoformat(),
            }, merge=True)
        except Exception as fs_err:
            print(f"[WARN] Firestore profile upsert failed: {fs_err}")

        return jsonify({
            "success": True,
            "user": {
                "uid":            user['uid'],
                "email":          user['email'],
                "name":           user.get('name', ''),
                "email_verified": user['email_verified'],
            }
        }), 200

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ── GET /api/auth/me ─────────────────────────────────────────────────────
@auth_bp.route('/me', methods=['GET'])
@firebase_required
def get_me():
    try:
        user = request.user
        db   = _db()
        doc  = db.collection('users').document(user['uid']).get()
        profile = doc.to_dict() if doc.exists else {}

        return jsonify({
            "user": {
                "uid":               user['uid'],
                "email":             user['email'],
                "name":              profile.get('name', user.get('name', '')),
                "email_verified":    user['email_verified'],
                "profile_photo_url": profile.get('profile_photo_url', ''),
                "alternate_contact": profile.get('alternate_contact', ''),
                "created_at":        profile.get('created_at', ''),
            }
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── PUT /api/auth/profile ────────────────────────────────────────────────
@auth_bp.route('/profile', methods=['PUT'])
@firebase_required
def update_profile():
    try:
        user = request.user
        data = request.get_json() or {}

        update = {}
        for field in ('name', 'profile_photo_url', 'alternate_contact'):
            if field in data:
                update[field] = data[field]

        if not update:
            return jsonify({"error": "No fields to update"}), 400

        update['updated_at'] = datetime.utcnow().isoformat()
        _db().collection('users').document(user['uid']).set(update, merge=True)

        return jsonify({"success": True, "message": "Profile updated"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
