import eventlet
eventlet.monkey_patch(os=True, select=True, socket=True, thread=False, time=True)
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

load_dotenv()
cred = credentials.Certificate(os.getenv('FIREBASE_CREDENTIALS_PATH', 'firebase-service-account.json'))
firebase_admin.initialize_app(cred)
db = firestore.client()

yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
dummy_data = {
    'active': True,
    'uid': 'test_user_id',
    'user_email': 'jiviteshgarg30@gmail.com',
    'vehicle_name': 'Test Honda Civic',
    'vehicle_model': '2024',
    'next_notification': yesterday,
    'email_freq_days': 7,
    'tier': 'FAIR',
    'tier_label': 'SERVICE REQUIRED',
    'overall_score': 62,
    'trend': {'direction': 'declining', 'delta': -8.0},
    'fault_timelines': [
        {
            'issue': 'High RPM fluctuation',
            'frequency_pct': 75,
            'priority': 'URGENT',
            'priority_label': 'URGENT',
            'color': '#ef4444',
            'repair_by': '16 May 2026',
            'days_remaining': 7,
        }
    ],
    'component_risks': []
}

db.collection('vehicles').document('dummy_test_vid').collection('notification_meta').document('current').set(dummy_data)
print("✅ Injected dummy timeline into database!")
