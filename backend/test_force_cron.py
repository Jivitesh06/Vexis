import eventlet
eventlet.monkey_patch(os=True, select=True, socket=True, thread=False, time=True)
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore
from cron_notifications import run_cron
from dotenv import load_dotenv
import os

load_dotenv()
cred = credentials.Certificate(os.getenv('FIREBASE_CREDENTIALS_PATH', 'firebase-service-account.json'))
firebase_admin.initialize_app(cred)
db = firestore.client()

print("1. Fast-forwarding time in Firestore...")
docs = db.collection_group('notification_meta').get()
for doc in docs:
    if doc.id == 'current':
        yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
        doc.reference.update({'next_notification': yesterday})
        print(f" -> Set {doc.get('user_email')} to be OVERDUE (yesterday).")

print("\n2. Executing the Cron Job Engine...")
run_cron()

