from flask import Blueprint, request, jsonify
from utils.firebase_auth import (
    firebase_required,
    verify_firebase_token,
    get_or_create_user,
    init_firebase
)
from database import execute_query

auth_bp = Blueprint('auth', __name__)

# Initialize Firebase on import
init_firebase()

@auth_bp.route('/verify-token', methods=['POST'])
def verify_token():
    """
    Frontend sends Firebase ID token.
    Backend verifies and creates/returns user.
    """
    data = request.get_json()
    token = data.get('token')
    
    if not token:
        return jsonify({
            "error": "Token required"
        }), 400
    
    user = verify_firebase_token(token)
    
    if not user:
        return jsonify({
            "error": "Invalid token"
        }), 401
    
    # Get or create in PostgreSQL
    db_user = get_or_create_user(
        user['uid'],
        user['email'],
        user['name']
    )
    
    return jsonify({
        "success": True,
        "user": {
            "id": db_user['id'],
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
    Get current user info.
    request.user is set by decorator.
    """
    user = request.user
    
    db_user = execute_query(
        "SELECT * FROM users WHERE firebase_uid = %s",
        (user['uid'],),
        fetchone=True
    )
    
    if not db_user:
        return jsonify({
            "error": "User not found"
        }), 404
    
    return jsonify({
        "user": {
            "id": db_user['id'],
            "uid": user['uid'],
            "email": user['email'],
            "name": user['name'],
            "email_verified": user['email_verified'],
            "profile_photo_url": db_user.get('profile_photo_url', ''),
            "alternate_contact": db_user.get('alternate_contact', ''),
            "created_at": str(db_user['created_at'])
        }
    }), 200

@auth_bp.route('/profile', methods=['PUT'])
@firebase_required
def update_profile():
    """
    Update user profile information.
    """
    user = request.user
    data = request.get_json() or {}
    
    name = data.get('name')
    profile_photo_url = data.get('profile_photo_url')
    alternate_contact = data.get('alternate_contact')
    
    update_fields = []
    params = []
    
    if name is not None:
        update_fields.append("name = %s")
        params.append(name)
    if profile_photo_url is not None:
        update_fields.append("profile_photo_url = %s")
        params.append(profile_photo_url)
    if alternate_contact is not None:
        update_fields.append("alternate_contact = %s")
        params.append(alternate_contact)
        
    if not update_fields:
        return jsonify({"error": "No fields to update"}), 400
        
    query = "UPDATE users SET " + ", ".join(update_fields) + " WHERE firebase_uid = %s"
    params.append(user['uid'])
    
    try:
        execute_query(query, tuple(params), commit=True)
        return jsonify({"success": True, "message": "Profile updated"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

