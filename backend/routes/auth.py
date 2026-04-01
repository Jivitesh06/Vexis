from flask import Blueprint, request, jsonify, redirect
import bcrypt
import secrets
import datetime
from database import execute_query
from utils.jwt_helper import generate_token, jwt_required
from utils.validators import validate_signup
from utils.mailer import send_verification_email, send_welcome_email, send_reset_email
from config import Config

auth_bp = Blueprint('auth', __name__)


# ──────────────────────────────────────────────────────────────────
# POST /signup
# ──────────────────────────────────────────────────────────────────
@auth_bp.route('/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json()

        # 1. Validate fields
        valid, error = validate_signup(data)
        if not valid:
            return jsonify({"error": error}), 400

        email = data['email'].strip().lower()
        name  = data['name'].strip()

        # 2. Check duplicate email
        existing = execute_query(
            "SELECT id FROM users WHERE email = %s",
            (email,), fetchone=True
        )
        if existing:
            return jsonify({"error": "Email already registered"}), 409

        # 3. Hash password
        password_hash = bcrypt.hashpw(
            data['password'].encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

        # 4. Insert user (unverified)
        execute_query(
            "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
            (name, email, password_hash),
            commit=True
        )

        # 5. Generate verification token
        token  = secrets.token_urlsafe(32)
        expiry = datetime.datetime.utcnow() + datetime.timedelta(
            hours=Config.VERIFY_TOKEN_EXPIRY_HOURS
        )

        # 6. Save token to DB
        execute_query(
            """UPDATE users
               SET verify_token = %s, verify_token_expiry = %s
               WHERE email = %s""",
            (token, expiry, email),
            commit=True
        )

        # 7. Send verification email (non-blocking — failure is non-fatal)
        send_verification_email(email, name, token)

        return jsonify({
            "message": "Account created! Please check your email to verify your account.",
            "email":    email,
            "verified": False
        }), 201

    except Exception as e:
        print(f"[signup error] {e}")
        return jsonify({"error": "Server error"}), 500


# ──────────────────────────────────────────────────────────────────
# POST /login
# ──────────────────────────────────────────────────────────────────
@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()

        if not data or not data.get('email') or not data.get('password'):
            return jsonify({"error": "Email and password required"}), 400

        user = execute_query(
            "SELECT id, name, email, password_hash, is_verified FROM users WHERE email = %s",
            (data['email'].strip().lower(),),
            fetchone=True
        )
        if not user:
            return jsonify({"error": "Invalid email or password"}), 401

        if not bcrypt.checkpw(
            data['password'].encode('utf-8'),
            user['password_hash'].encode('utf-8')
        ):
            return jsonify({"error": "Invalid email or password"}), 401

        # Block unverified users
        if not user['is_verified']:
            return jsonify({
                "error": "Please verify your email before logging in. Check your inbox."
            }), 403

        token = generate_token(user['id'], user['email'])
        return jsonify({
            "token": token,
            "user": {
                "id":    user['id'],
                "name":  user['name'],
                "email": user['email']
            }
        }), 200

    except Exception as e:
        print(f"[login error] {e}")
        return jsonify({"error": "Server error"}), 500


# ──────────────────────────────────────────────────────────────────
# GET /me  (protected)
# ──────────────────────────────────────────────────────────────────
@auth_bp.route('/me', methods=['GET'])
@jwt_required
def me():
    try:
        user_id = request.user['user_id']
        user = execute_query(
            "SELECT id, name, email, is_verified, created_at FROM users WHERE id = %s",
            (user_id,), fetchone=True
        )
        if not user:
            return jsonify({"error": "User not found"}), 404

        return jsonify({
            "user": {
                "id":          user['id'],
                "name":        user['name'],
                "email":       user['email'],
                "is_verified": user['is_verified'],
                "created_at":  str(user['created_at'])
            }
        }), 200

    except Exception as e:
        print(f"[me error] {e}")
        return jsonify({"error": "Server error"}), 500


# ──────────────────────────────────────────────────────────────────
# GET /verify  — email verification link handler
# ──────────────────────────────────────────────────────────────────
@auth_bp.route('/verify', methods=['GET'])
def verify():
    try:
        token = request.args.get('token')
        if not token:
            return jsonify({"error": "Token missing"}), 400

        # Find user by token
        user = execute_query(
            "SELECT * FROM users WHERE verify_token = %s",
            (token,), fetchone=True
        )
        if not user:
            return jsonify({"error": "Invalid or expired verification link"}), 400

        # Check expiry
        expiry = user['verify_token_expiry']
        if expiry and datetime.datetime.utcnow() > expiry:
            return jsonify({
                "error": "Link expired. Please signup again or request a new verification email."
            }), 400

        # Mark as verified — clear token
        execute_query(
            """UPDATE users
               SET is_verified = TRUE,
                   verify_token = NULL,
                   verify_token_expiry = NULL
               WHERE id = %s""",
            (user['id'],),
            commit=True
        )

        # Send welcome email (non-fatal)
        send_welcome_email(user['email'], user['name'])

        # Redirect to login with success flag
        return redirect(f"{Config.FRONTEND_URL}/login.html?verified=true")

    except Exception as e:
        print(f"[verify error] {e}")
        return jsonify({"error": "Server error"}), 500


# ──────────────────────────────────────────────────────────────────
# POST /resend-verification
# ──────────────────────────────────────────────────────────────────
@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    try:
        data  = request.get_json()
        email = (data.get('email') or '').strip().lower()

        if not email:
            return jsonify({"error": "Email is required"}), 400

        user = execute_query(
            "SELECT id, name, email, is_verified FROM users WHERE email = %s",
            (email,), fetchone=True
        )
        if not user:
            return jsonify({"error": "No account found with that email"}), 404

        if user['is_verified']:
            return jsonify({"message": "Email already verified. You can login now."}), 200

        # Generate fresh token
        token  = secrets.token_urlsafe(32)
        expiry = datetime.datetime.utcnow() + datetime.timedelta(
            hours=Config.VERIFY_TOKEN_EXPIRY_HOURS
        )

        execute_query(
            """UPDATE users
               SET verify_token = %s, verify_token_expiry = %s
               WHERE email = %s""",
            (token, expiry, email),
            commit=True
        )

        send_verification_email(email, user['name'], token)

        return jsonify({
            "message": "Verification email resent. Please check your inbox."
        }), 200

    except Exception as e:
        print(f"[resend_verification error] {e}")
        return jsonify({"error": "Server error"}), 500


# ──────────────────────────────────────────────────────────────────
# POST /forgot-password
# ──────────────────────────────────────────────────────────────────
@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    try:
        data  = request.get_json()
        email = (data.get('email') or '').strip().lower()

        if not email:
            return jsonify({"error": "Email is required"}), 400

        # Always return same response to avoid email enumeration
        generic_ok = {"message": "If that email exists, a reset link will be sent"}, 200

        user = execute_query(
            "SELECT id, name, email FROM users WHERE email = %s",
            (email,), fetchone=True
        )
        if not user:
            return jsonify(generic_ok[0]), generic_ok[1]

        # Generate reset token valid for 1 hour
        token  = secrets.token_urlsafe(32)
        expiry = datetime.datetime.utcnow() + datetime.timedelta(hours=1)

        # Ensure columns exist (idempotent migration)
        execute_query(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token TEXT",
            commit=True
        )
        execute_query(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expiry TIMESTAMP",
            commit=True
        )

        execute_query(
            """UPDATE users
               SET reset_token = %s, reset_token_expiry = %s
               WHERE email = %s""",
            (token, expiry, email),
            commit=True
        )

        send_reset_email(email, user['name'], token)

        return jsonify({"message": "Reset link sent to your email"}), 200

    except Exception as e:
        print(f"[forgot_password error] {e}")
        return jsonify({"error": "Server error"}), 500


# ──────────────────────────────────────────────────────────────────
# POST /reset-password
# ──────────────────────────────────────────────────────────────────
@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    try:
        data         = request.get_json()
        token        = (data.get('token') or '').strip()
        new_password = (data.get('new_password') or '').strip()

        if not token:
            return jsonify({"error": "Reset token is required"}), 400

        if len(new_password) < 8:
            return jsonify({"error": "Password must be at least 8 characters"}), 400

        user = execute_query(
            "SELECT id, reset_token_expiry FROM users WHERE reset_token = %s",
            (token,), fetchone=True
        )
        if not user:
            return jsonify({"error": "Invalid reset link"}), 400

        expiry = user['reset_token_expiry']
        if not expiry or datetime.datetime.utcnow() > expiry:
            return jsonify({"error": "Reset link has expired. Please request a new one."}), 400

        password_hash = bcrypt.hashpw(
            new_password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

        execute_query(
            """UPDATE users
               SET password_hash = %s,
                   reset_token = NULL,
                   reset_token_expiry = NULL
               WHERE id = %s""",
            (password_hash, user['id']),
            commit=True
        )

        return jsonify({"message": "Password reset successful"}), 200

    except Exception as e:
        print(f"[reset_password error] {e}")
        return jsonify({"error": "Server error"}), 500
