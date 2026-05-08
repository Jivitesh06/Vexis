"""
Vexis Email Sender — Gmail SMTP
Handles sending vehicle health notifications via Gmail App Password.
"""
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """
    Send a single HTML email via Gmail SMTP.
    Requires env vars: GMAIL_SENDER, GMAIL_APP_PASSWORD
    Returns True on success, False on failure.
    """
    sender     = os.getenv('GMAIL_SENDER')
    app_pass   = os.getenv('GMAIL_APP_PASSWORD')

    if not sender or not app_pass:
        print('[EMAIL] GMAIL_SENDER or GMAIL_APP_PASSWORD not set. Skipping.')
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = f'Vexis AI <{sender}>'
        msg['To']      = to_email

        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, app_pass)
            server.sendmail(sender, to_email, msg.as_string())

        print(f'[EMAIL] Sent "{subject}" → {to_email}')
        return True

    except Exception as e:
        print(f'[EMAIL] Failed to send to {to_email}: {e}')
        return False
