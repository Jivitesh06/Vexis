import os
os.environ['FIREBASE_CREDENTIALS_PATH'] = 'firebase-service-account.json'
os.environ['GEMINI_API_KEY'] = 'fake_key' # Just to test initialization
from utils.firebase_auth import init_firebase
init_firebase()

def test_gemini():
    import google.generativeai as genai
    genai.configure(api_key=os.environ['GEMINI_API_KEY'])
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    gemini_history = []
    # Test starting chat with empty history
    chat = model.start_chat(history=gemini_history)
    print("Chat started successfully")

try:
    test_gemini()
except Exception as e:
    import traceback
    traceback.print_exc()
