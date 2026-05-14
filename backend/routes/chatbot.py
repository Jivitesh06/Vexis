"""
Vexis VexBot — Automobile AI Chatbot with user context from Firestore.
Uses Google Gemini 1.5 Flash (free tier) with RAG pattern.
"""

import os
import traceback
from flask        import Blueprint, request, jsonify
from utils.firebase_auth import firebase_required
from firebase_admin import firestore

chatbot_bp = Blueprint('chatbot', __name__)

def _fs():
    return firestore.client()

# ── Gemini client (lazy-loaded) ──────────────────────────────────────────────
def _get_gemini():
    import google.generativeai as genai
    api_key = os.getenv('GEMINI_API_KEY', '')
    if not api_key:
        raise ValueError('GEMINI_API_KEY environment variable is not set.')
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-1.5-flash')


# ── Fetch user context from Firestore ────────────────────────────────────────
def _build_user_context(uid: str) -> str:
    """
    Fetches the user's vehicles, latest reports, and subscription from
    Firestore and formats them into a context string for the AI prompt.
    """
    try:
        db = _fs()
        lines = []

        # 1. Vehicles
        vehicles_ref = db.collection('vehicles') \
                         .where('userId', '==', uid) \
                         .limit(5) \
                         .stream()
        vehicles = [v.to_dict() | {'id': v.id} for v in vehicles_ref]

        if vehicles:
            lines.append('=== USER VEHICLES ===')
            for v in vehicles:
                lines.append(
                    f"• {v.get('name', 'Unknown')} "
                    f"({v.get('model', 'Unknown model')}) "
                    f"— Last analysed: {v.get('last_analysed', 'Never')[:10]}"
                )

        # 2. Latest Reports (max 3)
        reports_ref = db.collection('users').document(uid) \
                        .collection('reports') \
                        .order_by('timestamp', direction='DESCENDING') \
                        .limit(3) \
                        .stream()
        reports = [r.to_dict() for r in reports_ref]

        if reports:
            lines.append('\n=== LATEST HEALTH REPORTS ===')
            for i, rep in enumerate(reports):
                ts  = str(rep.get('timestamp', 'Unknown'))[:10]
                veh = rep.get('vehicle_name', 'Unknown vehicle')
                src = rep.get('source', '')
                src_label = '(Live OBD)' if src == 'live_obd' else '(CSV Upload)'

                lines.append(
                    f"\nReport {i+1} — {veh} {src_label} — {ts}"
                )
                lines.append(
                    f"  Overall Score   : {rep.get('overall_score', 'N/A')}/100"
                )
                lines.append(
                    f"  Engine Score    : {rep.get('engine_score', 'N/A')}/100"
                )
                lines.append(
                    f"  Fuel Score      : {rep.get('fuel_score', 'N/A')}/100"
                )
                lines.append(
                    f"  Efficiency Score: {rep.get('efficiency_score', 'N/A')}/100"
                )
                lines.append(
                    f"  Driving Score   : {rep.get('driving_score', 'N/A')}/100"
                )
                lines.append(
                    f"  Thermal Score   : {rep.get('thermal_score', 'N/A')}/100"
                )
                lines.append(
                    f"  Status          : {rep.get('status_label', 'N/A')}"
                )
                lines.append(
                    f"  Failure Risk    : {'YES ⚠️' if rep.get('failure_risk') else 'No'}"
                )
                issues = rep.get('issues', [])
                if issues:
                    lines.append(f"  Detected Issues : {', '.join(issues[:5])}")

        # 3. Service Intelligence timeline (per vehicle)
        if vehicles:
            lines.append('\n=== SERVICE INTELLIGENCE ===')
            for v in vehicles[:2]:  # max 2 vehicles
                try:
                    tl_ref = db.collection('vehicles').document(v['id']) \
                               .collection('notification_meta') \
                               .document('current') \
                               .get()
                    if tl_ref.exists:
                        tl = tl_ref.to_dict()
                        pred = tl.get('prediction', {})
                        recs = tl.get('service_recommendations', [])
                        lines.append(
                            f"• {v.get('name', 'Vehicle')}: "
                            f"Trend={tl.get('trend', {}).get('direction', 'stable')}, "
                            f"Score={round(tl.get('overall_score', 0))}/100, "
                            f"Days to critical={pred.get('days_to_poor', 'N/A')}"
                        )
                        if recs:
                            lines.append(
                                f"  Recommendations: {'; '.join(recs[:3])}"
                            )
                except Exception:
                    pass

        # 4. Subscription
        try:
            sub_ref = db.collection('users').document(uid) \
                        .collection('subscription').document('current').get()
            if sub_ref.exists:
                sub = sub_ref.to_dict()
                lines.append(
                    f"\n=== SUBSCRIPTION ==="
                    f"\n  Plan: {sub.get('plan', 'free')} | "
                    f"Active: {sub.get('active', False)}"
                )
        except Exception:
            pass

        if not lines:
            return 'The user has no vehicle data or reports yet in Vexis.'

        return '\n'.join(lines)

    except Exception as e:
        print(f'[VexBot] context fetch error: {e}')
        return 'Could not load user vehicle data at this time.'


# ── System Prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are VexBot — the AI vehicle health assistant built into the Vexis platform.

YOUR ROLE:
- Answer questions about the user's specific vehicle health, OBD-II data, scores, issues, and maintenance
- Explain automotive topics: engines, fuel systems, transmissions, cooling, sensors, OBD codes
- Interpret the user's health scores and detected issues in plain language
- Give practical maintenance advice based on the user's actual report data
- Help users understand how to use Vexis features (live analysis, CSV upload, reports, subscriptions)

STRICT RULES:
- ONLY answer vehicle, automobile, car maintenance, and Vexis-related questions
- If asked about anything else (coding, politics, movies, general chat etc.), respond:
  "I'm VexBot 🚗 — I can only help with vehicle health and automobile questions. Ask me about your car's scores, engine issues, or maintenance tips!"
- Always refer to the user's actual data (provided below) when answering questions about THEIR car
- Keep answers concise but complete — use bullet points for lists
- Use simple language — not all users are mechanics
- When failure risk is detected, be empathetic but clear about urgency
- Respond in the same language the user writes in (Hindi/English/Hinglish)

VEXIS PLATFORM KNOWLEDGE:
- Vexis scores vehicles 0-100 across: Engine, Fuel, Efficiency, Driving, Thermal systems
- Scores: 80-100 = Excellent, 60-79 = Good, 40-59 = Fair, 20-39 = Poor, 0-19 = Critical
- Data comes from OBD-II sensors: RPM, Speed, Load, Coolant Temp, MAF, STFT, LTFT, Throttle, Intake Temp
- Isolation Forest ML models detect anomalies in each system
- Users can connect live via ELM327 OBD scanner or upload a CSV file
- Daily email alerts are sent for vehicles in Poor/Critical condition
"""


# ── POST /api/chatbot/message ────────────────────────────────────────────────
@chatbot_bp.route('/chatbot/message', methods=['POST'])
@firebase_required
def chat_message():
    try:
        uid  = request.user['uid']
        body = request.get_json(silent=True) or {}

        user_message = (body.get('message') or '').strip()
        history      = body.get('history', [])   # [{role, text}, ...]

        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400

        if len(user_message) > 1000:
            return jsonify({'error': 'Message too long (max 1000 chars)'}), 400

        # 1. Fetch user context from Firestore
        user_context = _build_user_context(uid)

        # 2. Build full prompt
        full_system = (
            SYSTEM_PROMPT
            + f"\n\n--- USER'S VEHICLE DATA (from Vexis database) ---\n{user_context}\n---\n"
        )

        # 3. Build Gemini chat history
        model = _get_gemini()
        gemini_history = []
        for msg in history[-8:]:   # last 8 messages for context window
            role = 'user' if msg.get('role') == 'user' else 'model'
            gemini_history.append({
                'role': role,
                'parts': [msg.get('text', '')]
            })

        # 4. Start chat session with system instruction
        chat = model.start_chat(history=gemini_history)

        # Inject system prompt into first turn if history is empty
        if not gemini_history:
            full_message = full_system + '\n\nUser: ' + user_message
        else:
            full_message = user_message

        response = chat.send_message(
            full_message if not gemini_history else user_message,
            generation_config={
                'temperature':     0.7,
                'max_output_tokens': 512,
            }
        )

        # If history was empty, the system prompt was bundled — send context inline
        if not gemini_history:
            # Rebuild with system context in first message for proper conversation
            chat2 = model.start_chat(history=[])
            resp2 = chat2.send_message(
                full_system + '\n\nNow the user will ask questions. '
                'First user message:\n' + user_message,
                generation_config={
                    'temperature':       0.7,
                    'max_output_tokens': 512,
                }
            )
            bot_reply = resp2.text
        else:
            bot_reply = response.text

        return jsonify({
            'reply': bot_reply,
            'success': True
        }), 200

    except ValueError as ve:
        # GEMINI_API_KEY not set
        return jsonify({'error': str(ve), 'reply': '⚙️ VexBot is not configured yet. Ask the admin to set the GEMINI_API_KEY.'}), 503

    except Exception as e:
        print(f'[VexBot] error: {e}')
        traceback.print_exc()
        return jsonify({
            'error':  f'VexBot encountered an error: {str(e)}',
            'reply':  f'🔧 VexBot is temporarily unavailable. Error: {str(e)}'
        }), 500
