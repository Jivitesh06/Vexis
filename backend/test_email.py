from utils.email_sender import send_email
from utils.email_templates import build_health_email
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

print("Building email template...")
sample_timeline = {
    'tier': 'FAIR',
    'tier_label': 'SERVICE REQUIRED',
    'overall_score': 62,
    'trend': {'direction': 'declining', 'delta': -8.0},
    'next_notification': datetime.utcnow().isoformat(),
    'email_freq_days': 7,
    'fault_timelines': [
        {
            'issue': 'High RPM fluctuation detected',
            'frequency_pct': 75,
            'priority': 'URGENT',
            'priority_label': 'URGENT',
            'color': '#ef4444',
            'repair_by': '16 May 2026',
            'days_remaining': 7,
        }
    ],
    'component_risks': [
        {
            'component': 'Engine',
            'score': 55,
            'tier': 'POOR',
            'action': 'Service Engine within 7 days.',
        }
    ],
}

email_data = build_health_email(
    user_name="Jivitesh Garg",
    user_email="jiviteshgarg30@gmail.com",  # It doesn't matter, just for the template
    vehicle_name="Test Honda Civic",
    vehicle_model="2024",
    timeline=sample_timeline,
)

# Put your actual receiving email here!
receiver = "REPLACE_ME@gmail.com"

print(f"Attempting to send email to {receiver}...")
success, err = send_email(receiver, email_data['subject'], email_data['html'])

if success:
    print("✅ SUCCESS! Check your inbox.")
else:
    print(f"❌ FAILED! Error: {err}")
