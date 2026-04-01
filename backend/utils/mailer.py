"""
mailer.py — Email sending utility for Vexis.
Uses Python's built-in smtplib (no extra packages needed).
Sends via Gmail SMTP on port 465 (SSL).
"""

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import Config


# ──────────────────────────────────────────────────────────────────
# FUNCTION 1 — send_email
# ──────────────────────────────────────────────────────────────────
def send_email(to_email, subject, html_body):
    import smtplib, ssl, traceback
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from config import Config

    print(f"[MAIL] Attempting send")
    print(f"[MAIL] From: {Config.MAIL_EMAIL}")
    print(f"[MAIL] To: {to_email}")
    print(f"[MAIL] Password SET: {bool(Config.MAIL_PASSWORD)}")

    if not Config.MAIL_EMAIL or not Config.MAIL_PASSWORD:
        print("[MAIL] ❌ Credentials missing in .env")
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{Config.MAIL_NAME} <{Config.MAIL_EMAIL}>"
        msg['To'] = to_email
        msg.attach(MIMEText(html_body, 'html'))

        context = ssl.create_default_context()
        print("[MAIL] Connecting smtp.gmail.com:465")

        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as server:
            print("[MAIL] Connected ✅")
            server.login(Config.MAIL_EMAIL, Config.MAIL_PASSWORD)
            print("[MAIL] Logged in ✅")
            server.sendmail(Config.MAIL_EMAIL, to_email, msg.as_string())
            print(f"[MAIL] ✅ Sent to {to_email}")
            return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"[MAIL] ❌ AUTH ERROR: {e}")
        print("[MAIL] Check App Password - no spaces")
        return False

    except smtplib.SMTPException as e:
        print(f"[MAIL] ❌ SMTP ERROR: {e}")
        traceback.print_exc()
        return False

    except Exception as e:
        print(f"[MAIL] ❌ ERROR: {e}")
        traceback.print_exc()
        return False


# ──────────────────────────────────────────────────────────────────
# FUNCTION 2 — send_verification_email
# ──────────────────────────────────────────────────────────────────
def send_verification_email(to_email: str, name: str, token: str) -> bool:
    """
    Send account verification email with a secure one-time link.
    """
    url = f"{Config.FRONTEND_URL}/api/auth/verify?token={token}"

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width">
  <style>
    body {{
      margin: 0; padding: 0;
      background: #050810;
      font-family: Arial, sans-serif;
    }}
    .container {{
      max-width: 560px;
      margin: 40px auto;
      background: #090d1a;
      border: 1px solid rgba(0,229,255,0.2);
      border-radius: 16px;
      overflow: hidden;
    }}
    .header {{
      background: linear-gradient(135deg, #00e5ff20, #7c4dff20);
      padding: 32px;
      text-align: center;
      border-bottom: 1px solid rgba(0,229,255,0.15);
    }}
    .logo-text {{
      font-size: 28px;
      font-weight: 900;
      color: #00e5ff;
      letter-spacing: 4px;
    }}
    .tagline {{
      color: #6b7a99;
      font-size: 13px;
      margin-top: 4px;
    }}
    .body {{
      padding: 40px 32px;
    }}
    h2 {{
      color: #e8eaf0;
      font-size: 22px;
      margin-bottom: 12px;
    }}
    p {{
      color: #a0aec0;
      font-size: 15px;
      line-height: 1.6;
      margin-bottom: 16px;
    }}
    .btn {{
      display: block;
      width: fit-content;
      margin: 28px auto;
      padding: 14px 36px;
      background: linear-gradient(135deg, #00e5ff, #7c4dff);
      color: #000000;
      font-size: 15px;
      font-weight: 700;
      text-decoration: none;
      border-radius: 8px;
      letter-spacing: 1px;
    }}
    .url-box {{
      background: #0d1225;
      border: 1px solid rgba(0,229,255,0.1);
      border-radius: 8px;
      padding: 12px 16px;
      font-size: 12px;
      color: #6b7a99;
      word-break: break-all;
      margin-top: 8px;
    }}
    .footer {{
      background: #030609;
      padding: 24px 32px;
      text-align: center;
      border-top: 1px solid rgba(0,229,255,0.1);
    }}
    .footer p {{
      color: #6b7a99;
      font-size: 12px;
      margin: 0;
    }}
    .expire-note {{
      background: rgba(255,234,0,0.08);
      border: 1px solid rgba(255,234,0,0.2);
      border-radius: 8px;
      padding: 10px 16px;
      color: #ffea00;
      font-size: 13px;
      text-align: center;
      margin-top: 20px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="logo-text">VEXIS</div>
      <div class="tagline">AI Vehicle Health Intelligence</div>
    </div>
    <div class="body">
      <h2>Welcome, {name}! 👋</h2>
      <p>Thank you for creating your Vexis account.
      You are one step away from AI-powered vehicle diagnostics.</p>
      <p>Click the button below to verify your email address and activate your account:</p>
      <a href="{url}" class="btn">✅ VERIFY MY ACCOUNT</a>
      <p style="text-align:center; font-size:13px; color:#6b7a99;">
        Or copy this link into your browser:
      </p>
      <div class="url-box">{url}</div>
      <div class="expire-note">⏱ This link expires in 24 hours</div>
    </div>
    <div class="footer">
      <p>If you did not create a Vexis account, ignore this email.</p>
      <p style="margin-top:8px;">© 2025 Vexis — AI Vehicle Intelligence</p>
    </div>
  </div>
</body>
</html>"""

    return send_email(
        to_email,
        "Verify your Vexis account ✅",
        html
    )


# ──────────────────────────────────────────────────────────────────
# FUNCTION 3 — send_welcome_email
# ──────────────────────────────────────────────────────────────────
def send_welcome_email(to_email: str, name: str) -> bool:
    """
    Send a welcome email after successful email verification.
    """
    login_url = f"{Config.FRONTEND_URL}/login.html"

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width">
  <style>
    body {{
      margin: 0; padding: 0;
      background: #050810;
      font-family: Arial, sans-serif;
    }}
    .container {{
      max-width: 560px;
      margin: 40px auto;
      background: #090d1a;
      border: 1px solid rgba(0,229,255,0.2);
      border-radius: 16px;
      overflow: hidden;
    }}
    .header {{
      background: linear-gradient(135deg, #00e67620, #00e5ff20);
      padding: 32px;
      text-align: center;
      border-bottom: 1px solid rgba(0,230,118,0.2);
    }}
    .logo-text {{
      font-size: 28px;
      font-weight: 900;
      color: #00e5ff;
      letter-spacing: 4px;
    }}
    .tagline {{
      color: #6b7a99;
      font-size: 13px;
      margin-top: 4px;
    }}
    .check-icon {{
      font-size: 48px;
      margin-bottom: 8px;
    }}
    .body {{
      padding: 40px 32px;
    }}
    h2 {{
      color: #00e676;
      font-size: 22px;
      margin-bottom: 12px;
    }}
    p {{
      color: #a0aec0;
      font-size: 15px;
      line-height: 1.6;
      margin-bottom: 16px;
    }}
    .btn {{
      display: block;
      width: fit-content;
      margin: 28px auto;
      padding: 14px 36px;
      background: linear-gradient(135deg, #00e5ff, #7c4dff);
      color: #000000;
      font-size: 15px;
      font-weight: 700;
      text-decoration: none;
      border-radius: 8px;
      letter-spacing: 1px;
    }}
    .features {{
      background: #0d1225;
      border: 1px solid rgba(0,229,255,0.1);
      border-radius: 8px;
      padding: 20px 24px;
      margin: 20px 0;
    }}
    .feature-item {{
      display: flex;
      align-items: center;
      gap: 10px;
      color: #a0aec0;
      font-size: 14px;
      margin-bottom: 10px;
    }}
    .footer {{
      background: #030609;
      padding: 24px 32px;
      text-align: center;
      border-top: 1px solid rgba(0,229,255,0.1);
    }}
    .footer p {{
      color: #6b7a99;
      font-size: 12px;
      margin: 0;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="check-icon">✅</div>
      <div class="logo-text">VEXIS</div>
      <div class="tagline">AI Vehicle Health Intelligence</div>
    </div>
    <div class="body">
      <h2>Welcome aboard, {name}!</h2>
      <p>Your account is now active and fully verified. You can now login and start using Vexis to monitor your vehicle's health in real-time.</p>
      <div class="features">
        <div class="feature-item">🔌 Connect your OBD-II USB scanner</div>
        <div class="feature-item">🤖 Get AI-powered health scores in seconds</div>
        <div class="feature-item">📊 View engine, fuel, thermal &amp; driving analytics</div>
        <div class="feature-item">📄 Download detailed PDF health reports</div>
      </div>
      <a href="{login_url}" class="btn">🚗 GO TO DASHBOARD</a>
    </div>
    <div class="footer">
      <p>© 2025 Vexis — AI Vehicle Intelligence</p>
    </div>
  </div>
</body>
</html>"""

    return send_email(
        to_email,
        "Welcome to Vexis! 🚗",
        html
    )


# ──────────────────────────────────────────────────────────────────
# FUNCTION 4 — send_reset_email
# ──────────────────────────────────────────────────────────────────
def send_reset_email(to_email: str, name: str, token: str) -> bool:
    """
    Send password reset email with a secure one-time link.
    """
    from config import Config
    url = f"{Config.FRONTEND_URL}/reset-password.html?token={token}"

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width">
  <style>
    body {{
      margin: 0; padding: 0;
      background: #050810;
      font-family: Arial, sans-serif;
    }}
    .container {{
      max-width: 560px;
      margin: 40px auto;
      background: #090d1a;
      border: 1px solid rgba(0,229,255,0.2);
      border-radius: 16px;
      overflow: hidden;
    }}
    .header {{
      background: linear-gradient(135deg, #7c4dff20, #ff6d0020);
      padding: 32px;
      text-align: center;
      border-bottom: 1px solid rgba(124,77,255,0.2);
    }}
    .logo-text {{
      font-size: 28px;
      font-weight: 900;
      color: #00e5ff;
      letter-spacing: 4px;
    }}
    .tagline {{
      color: #6b7a99;
      font-size: 13px;
      margin-top: 4px;
    }}
    .key-icon {{
      font-size: 48px;
      margin-bottom: 8px;
    }}
    .body {{
      padding: 40px 32px;
    }}
    h2 {{
      color: #e8eaf0;
      font-size: 22px;
      margin-bottom: 12px;
    }}
    p {{
      color: #a0aec0;
      font-size: 15px;
      line-height: 1.6;
      margin-bottom: 16px;
    }}
    .btn {{
      display: block;
      width: fit-content;
      margin: 28px auto;
      padding: 14px 36px;
      background: linear-gradient(135deg, #7c4dff, #ff6d00);
      color: #ffffff;
      font-size: 15px;
      font-weight: 700;
      text-decoration: none;
      border-radius: 8px;
      letter-spacing: 1px;
    }}
    .url-box {{
      background: #0d1225;
      border: 1px solid rgba(0,229,255,0.1);
      border-radius: 8px;
      padding: 12px 16px;
      font-size: 12px;
      color: #6b7a99;
      word-break: break-all;
      margin-top: 8px;
    }}
    .footer {{
      background: #030609;
      padding: 24px 32px;
      text-align: center;
      border-top: 1px solid rgba(0,229,255,0.1);
    }}
    .footer p {{
      color: #6b7a99;
      font-size: 12px;
      margin: 0;
    }}
    .expire-note {{
      background: rgba(255,109,0,0.08);
      border: 1px solid rgba(255,109,0,0.25);
      border-radius: 8px;
      padding: 10px 16px;
      color: #ff6d00;
      font-size: 13px;
      text-align: center;
      margin-top: 20px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="key-icon">🔑</div>
      <div class="logo-text">VEXIS</div>
      <div class="tagline">AI Vehicle Health Intelligence</div>
    </div>
    <div class="body">
      <h2>Reset your password, {name}</h2>
      <p>We received a request to reset your Vexis account password.
      Click the button below to choose a new password:</p>
      <a href="{url}" class="btn">Reset My Password</a>
      <p style="text-align:center; font-size:13px; color:#6b7a99;">
        Or copy this link into your browser:
      </p>
      <div class="url-box">{url}</div>
      <div class="expire-note">⏱ This link expires in 1 hour</div>
      <p style="margin-top:20px; font-size:13px; color:#6b7a99;">
        If you did not request a password reset, you can safely ignore this email.
        Your password will not be changed.
      </p>
    </div>
    <div class="footer">
      <p>If you did not request this, ignore this email.</p>
      <p style="margin-top:8px;">© 2025 Vexis — AI Vehicle Intelligence</p>
    </div>
  </div>
</body>
</html>"""

    return send_email(
        to_email,
        "Reset your Vexis password 🔑",
        html
    )
