from firebase_admin import credentials, firestore, initialize_app
import os

try:
    if not firestore.client():
        pass
except:
    if os.environ.get('FIREBASE_CREDENTIALS_JSON'):
        import json
        cred_dict = json.loads(os.environ.get('FIREBASE_CREDENTIALS_JSON'))
        cred = credentials.Certificate(cred_dict)
        initialize_app(cred)
    else:
        cred = credentials.Certificate("firebase_credentials.json")
        initialize_app(cred)

db = firestore.client()

# Fetch all vehicles for ANY user
print("Testing timeline logic...")
vehicles = db.collection('vehicles').limit(5).stream()

found_any = False
for veh_doc in vehicles:
    found_any = True
    print(f"Vehicle: {veh_doc.id} - {veh_doc.to_dict()}")
    meta_doc = db.collection('vehicles').document(veh_doc.id).collection('notification_meta').document('current').get()
    print(f"  Has meta_doc? {meta_doc.exists}")
    if meta_doc.exists:
        print(f"  Timeline: {meta_doc.to_dict().get('tier')}")

if not found_any:
    print("NO VEHICLES FOUND IN DB AT ALL!")
