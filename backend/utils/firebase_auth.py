import firebase_admin
from firebase_admin import credentials, auth
from flask import request, jsonify
from functools import wraps
import os

# Initialize Firebase Admin SDK
def init_firebase():
    cred_path = os.getenv(
        'FIREBASE_CREDENTIALS_PATH',
        'firebase-service-account.json'
    )
    
    if not firebase_admin._apps:
        try:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            print("[FIREBASE] Admin SDK initialized")
        except Exception as e:
            print(f"[FIREBASE] SDK init error: {e}")

def verify_firebase_token(token):
    """
    Verify Firebase ID token.
    Returns user dict with uid, email, name
    or None if invalid.
    """
    try:
        decoded = auth.verify_id_token(token)
        return {
            'uid': decoded['uid'],
            'email': decoded.get('email'),
            'name': decoded.get('name', ''),
            'email_verified': decoded.get(
                'email_verified', False
            )
        }
    except Exception as e:
        print(f"[FIREBASE] Token verify error: {e}")
        return None

def firebase_required(f):
    """
    Decorator to protect routes.
    Reads Authorization: Bearer <token>
    Sets request.user = decoded user dict
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get(
            'Authorization', ''
        )
        
        if not auth_header.startswith(
            'Bearer '
        ):
            return jsonify({
                "error": "Authorization header missing"
            }), 401
        
        try:
            token = auth_header.split(' ')[1]
            user = verify_firebase_token(token)
        except IndexError:
            return jsonify({
                "error": "Invalid Authorization header format"
            }), 401
        
        if not user:
            return jsonify({
                "error": "Invalid or expired token"
            }), 401
        
        request.user = user
        return f(*args, **kwargs)
    
    return decorated

def get_or_create_user(uid, email, name=''):
    """
    Get or create user in PostgreSQL.
    Links Firebase UID to local DB.
    """
    from database import execute_query
    
    # Check if user exists by firebase_uid
    user = execute_query(
        "SELECT * FROM users WHERE firebase_uid = %s",
        (uid,),
        fetchone=True
    )
    if user:
        return user
    
    # Fallback: check if user exists by email (legacy users)
    if email:
        user_by_email = execute_query(
            "SELECT * FROM users WHERE email = %s",
            (email,),
            fetchone=True
        )
        if user_by_email:
            # Link the firebase_uid to this existing user
            execute_query(
                "UPDATE users SET firebase_uid = %s WHERE email = %s",
                (uid, email),
                commit=True
            )
            return execute_query(
                "SELECT * FROM users WHERE firebase_uid = %s",
                (uid,),
                fetchone=True
            )
    
    # Create new user
    execute_query(
        """INSERT INTO users 
        (firebase_uid, email, name, created_at)
        VALUES (%s, %s, %s, CURRENT_TIMESTAMP)""",
        (uid, email, name),
        commit=True
    )
    
    # Return created user
    return execute_query(
        "SELECT * FROM users WHERE firebase_uid = %s",
        (uid,),
        fetchone=True
    )
