"""
Vexis Cron Job - Automated Health Notifications
Runs periodically to check vehicle timelines and dispatch emails.
"""
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

import firebase_admin
from firebase_admin import credentials, firestore

from utils.email_sender import send_email
from utils.email_templates import build_health_email

load_dotenv()

def init_firebase():
    if not firebase_admin._apps:
        cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH', 'firebase-service-account.json')
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        print("[CRON] Firebase initialized.")
    return firestore.client()

def run_cron():
    print(f"==================================================")
    print(f"[START] VEXIS CRON: Starting Notification Check at {datetime.utcnow().isoformat()}")
    print(f"==================================================")
    
    db = init_firebase()
    now = datetime.utcnow()
    emails_sent = 0

    try:
        # Fetch all 'current' documents in any 'notification_meta' collection
        # We process in memory to avoid needing complex composite Firestore indexes
        print("[CRON] Fetching timeline meta documents...")
        meta_docs = db.collection_group('notification_meta').get()
        
        for doc in meta_docs:
            if doc.id != 'current':
                continue
                
            data = doc.to_dict()
            if not data.get('active', False):
                continue
                
            next_ts = data.get('next_notification')
            if not next_ts:
                continue
                
            try:
                next_date = datetime.fromisoformat(next_ts)
            except ValueError:
                continue
                
            # If the notification is not due yet, skip
            if now < next_date:
                continue

            # It's due! Let's check if the user actually wants emails.
            uid = data.get('uid')
            user_email = data.get('user_email')
            if not uid or not user_email:
                continue

            prefs_doc = db.collection('users').document(uid).collection('settings').document('notifications').get()
            prefs = prefs_doc.to_dict() if prefs_doc.exists else {'enabled': True}
            
            if not prefs.get('enabled', True):
                print(f"[CRON] Skipping {user_email} — notifications disabled.")
                continue

            # Generate the email
            print(f"[CRON] Processing Due Notification for {user_email} (Vehicle: {data.get('vehicle_name', 'Unknown')})")
            email_data = build_health_email(
                user_name="Vexis User", # Optional, can fetch from user profile if needed
                user_email=user_email,
                vehicle_name=data.get('vehicle_name', 'Your Vehicle'),
                vehicle_model=data.get('vehicle_model', ''),
                timeline=data,
            )

            # Send the email
            ok, err_msg = send_email(user_email, email_data['subject'], email_data['html'])
            
            if ok:
                emails_sent += 1
                # Update next_notification so we don't spam them
                freq_days = data.get('email_freq_days', 7)
                new_next_date = now + timedelta(days=freq_days)
                
                # We need the exact document reference to update
                doc.reference.update({
                    'next_notification': new_next_date.isoformat(),
                    'last_sent': now.isoformat()
                })
                print(f"       -> [SUCCESS] Sent successfully. Next update scheduled for {new_next_date.isoformat()}")
            else:
                print(f"       -> [ERROR] Failed to send: {err_msg}")

    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"[CRON] Error during execution: {e}")

    print(f"==================================================")
    print(f"[DONE] VEXIS CRON: Finished. Sent {emails_sent} emails.")
    print(f"==================================================")

if __name__ == "__main__":
    run_cron()
