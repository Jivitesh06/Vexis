import eventlet
eventlet.monkey_patch()
import os
os.environ["GRPC_POLL_STRATEGY"] = "epoll1"
import firebase_admin
from firebase_admin import credentials, firestore

os.environ["GRPC_DNS_RESOLVER"] = "native"

cred = credentials.Certificate("firebase-service-account.json")
firebase_admin.initialize_app(cred)

db = firestore.client()
try:
    print("Fetching users...")
    docs = db.collection("users").limit(1).get()
    print("Success!", len(docs))
except Exception as e:
    print("Error:", e)
