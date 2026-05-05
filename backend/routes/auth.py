from flask import Blueprint, request, jsonify
from utils.firebase_auth import (
    firebase_required,
    verify_firebase_token,
    init_firebase
)

auth_bp = Blueprint('auth', __name__)

# Initialize Firebase on import
init_firebase()

@auth_bp.route('/verify-token', methods=['POST'])
def verify_token():
    """
    Frontend sends Firebase ID token.
    Backend verifies user. User data is managed purely in Firestore on frontend.
    """
    data = request.get_json()
    token = data.get('token')
    
    if not token:
        return jsonify({"error": "Token required"}), 400
    
    user = verify_firebase_token(token)
    
    if not user:
        return jsonify({"error": "Invalid token"}), 401
    
    # We no longer sync to PostgreSQL. The frontend handles Firestore.
    return jsonify({
        "success": True,
        "user": {
            "uid": user['uid'],
            "email": user['email'],
            "name": user['name'],
            "email_verified": user['email_verified']
        }
    }), 200

@auth_bp.route('/me', methods=['GET'])
@firebase_required
def get_me():
    """
    Get current user info from token (frontend should fetch full profile from Firestore).
    """
    user = request.user
    return jsonify({"user": user}), 200

@auth_bp.route('/profile', methods=['PUT'])
@firebase_required
def update_profile():
    """
    Frontend directly updates Firestore now.
    This route can be deprecated or kept as a no-op if needed.
    """
    return jsonify({"success": True, "message": "Update profile via Firestore"}), 200

