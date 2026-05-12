"""
Vexis Email Sender — Gmail SMTP
Handles sending vehicle health notifications via Gmail App Password.
"""
import smtplib
import os
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header

# Force UTF-8 output so emoji in subject lines don't crash on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass


def send_email(to_email: str, subject: str, html_body: str) -> tuple[bool, str]:
    """
    Send a single HTML email via Gmail SMTP.
    Requires env vars: MAIL_EMAIL, MAIL_PASSWORD
    Returns (True, "Success") on success, (False, "Error message") on failure.
    """
    sender     = os.getenv('MAIL_EMAIL', os.getenv('GMAIL_SENDER'))
    app_pass   = os.getenv('MAIL_PASSWORD', os.getenv('GMAIL_APP_PASSWORD'))

    if not sender or not app_pass:
        print('[EMAIL] MAIL_EMAIL or MAIL_PASSWORD not set. Skipping.')
        return False, "MAIL_EMAIL or MAIL_PASSWORD environment variables are missing."

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = Header(subject, 'utf-8').encode()
        msg['From']    = f'Vexis AI <{sender}>'
        msg['To']      = to_email

        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, app_pass)
            server.sendmail(sender, to_email, msg.as_bytes())

        try:
            print(f'[EMAIL] Sent "{subject}" → {to_email}')
        except UnicodeEncodeError:
            print('[EMAIL] Sent successfully (subject contains emoji)')
        return True, "Email sent successfully"

    except Exception as e:
        print(f'[EMAIL] Failed to send to {to_email}: {e}')
        return False, str(e)
