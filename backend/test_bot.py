import os
os.environ['FIREBASE_CREDENTIALS_PATH'] = 'firebase-service-account.json'
from utils.firebase_auth import init_firebase
init_firebase()
from firebase_admin import firestore
db = firestore.client()
uid = 'test'
try:
    vehicles_ref = db.collection('vehicles').where('userId', '==', uid).limit(5).stream()
    vehicles = [v.to_dict() | {'id': v.id} for v in vehicles_ref]
    print(vehicles)
except Exception as e:
    import traceback
    traceback.print_exc()
