import eventlet
eventlet.monkey_patch()
import os
import firebase_admin
from firebase_admin import credentials
from google.cloud import firestore

cred = credentials.Certificate("firebase-service-account.json")
firebase_admin.initialize_app(cred)

try:
    db = firestore.Client(
        credentials=cred.get_credential(),
        project=cred.project_id,
        client_options={"api_endpoint": "firestore.googleapis.com"}
    )
    # The actual way to force REST in google-cloud-firestore python SDK is using the `transport` kwarg.
    from google.cloud.firestore_v1.services.firestore.transports.rest import FirestoreRestTransport
    db = firestore.Client(
        credentials=cred.get_credential(),
        project=cred.project_id,
        transport=FirestoreRestTransport(credentials=cred.get_credential())
    )
    docs = db.collection("users").limit(1).get()
    print("Success with explicit REST transport!", len(docs))
except Exception as e:
    print("Failed explicit:", e)
