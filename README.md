<div align="center">

<img src="frontend/assets/logo.png" alt="Vexis Logo" width="100" />

# Vexis — AI Vehicle Health Intelligence

**Predictive maintenance & real-time vehicle health scoring powered by OBD-II data, Machine Learning, and a Razorpay subscription model.**

[![Firebase Hosting](https://img.shields.io/badge/Frontend-Firebase_Hosting-orange?logo=firebase&logoColor=white)](https://vexis-527f2.web.app)
[![Backend](https://img.shields.io/badge/Backend-Render-4353FF?logo=render&logoColor=white)](https://vexis-backend-kklg.onrender.com)
[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

[🌐 Live Demo](https://vexis-527f2.web.app) · [🐛 Report Bug](https://github.com/Jivitesh06/Vexis/issues) · [💡 Request Feature](https://github.com/Jivitesh06/Vexis/issues)

</div>

---

## 📖 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Tech Stack](#-tech-stack)
- [Architecture](#-architecture)
- [Subscription Plans](#-subscription-plans)
- [Local Development](#-local-development)
- [Environment Variables](#-environment-variables)
- [Deployment](#-deployment)
- [API Reference](#-api-reference)
- [Project Structure](#-project-structure)

---

## 🚀 Overview

Vexis is a full-stack, AI-powered vehicle diagnostics platform that brings enterprise-level predictive maintenance to everyday drivers. By connecting an OBD-II scanner directly to the browser via the **Web Serial API**, Vexis streams live engine sensor data to a Flask ML backend.

Our **Isolation Forest ML models** analyze sensor readings across 5 core vehicle systems to generate a human-readable Health Score (0–100), forecast degradation velocity, and send proactive email alerts — all without requiring a native app.

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🏎️ **Live OBD-II Streaming** | Connects to ELM327 USB/Bluetooth via Web Serial API — no app needed |
| 🧠 **AI Health Scoring** | 5 Isolation Forest models analyse Engine, Fuel, Efficiency, Driving & Thermal |
| 🔮 **Predictive Degradation** | Calculates health-decline velocity & forecasts days until critical failure |
| 📄 **Manual CSV Reports** | Upload offline OBD data → instant batch analysis → downloadable PDF |
| 💳 **Subscription Payments** | Razorpay-powered plans gate AI features with pay-per-use or recurring access |
| 💬 **VexBot AI Assistant** | Context-aware RAG chatbot powered by Gemini 2.5 Flash for personalized automotive advice |
| 🔔 **Daily Email Alerts** | GitHub Actions cron sends HTML health summaries every morning at 8 AM IST |
| 📊 **Service Intelligence** | Trend analysis, service recommendations, and risk forecasting per vehicle |
| 🔐 **Firebase Auth** | Email/password auth with token-based API protection |

---

## 🛠️ Tech Stack

### Frontend
| Layer | Technology |
|-------|-----------|
| Core | Vanilla JS (ES Modules), HTML5, CSS3 |
| Styling | Custom CSS, Glassmorphism, CSS Variables, Orbitron font |
| Data Viz | Chart.js |
| Auth | Firebase Auth SDK |
| Hosting | Firebase Hosting |
| Payments | Razorpay Checkout JS (lazy-loaded) |

### Backend & ML
| Layer | Technology |
|-------|-----------|
| Framework | Python 3.11, Flask 3.0, Flask-SocketIO (Eventlet) |
| ML Models | Scikit-Learn (Isolation Forests), XGBoost, Pandas, NumPy |
| LLM API | Google Generative AI (Gemini 2.5 Flash + RAG) |
| PDF Engine | ReportLab |
| Email | Gmail SMTP (Port 587 + STARTTLS) |
| Payments | Razorpay Python SDK |
| Hosting | Render (Web Service, Free Tier) |

### Database & Infrastructure
| Layer | Technology |
|-------|-----------|
| Auth | Firebase Authentication |
| Database | Cloud Firestore (NoSQL) |
| Storage | Firebase Storage |
| Automation | GitHub Actions (daily cron at 02:30 UTC) |
| Version Control | Git + GitHub |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER BROWSER                             │
│   Firebase Hosting (vexis-527f2.web.app)                       │
│   Vanilla JS + Chart.js + Razorpay Checkout SDK                │
└──────────────┬──────────────────────┬───────────────────────────┘
               │ REST API             │ Firebase SDK
               ▼                      ▼
┌──────────────────────┐  ┌──────────────────────────────────────┐
│  Render Backend      │  │  Firebase / Google Cloud             │
│  Flask + SocketIO    │  │  ├─ Authentication                   │
│  ├─ ML Models        │  │  ├─ Firestore (reports, subscriptions│
│  ├─ PDF Generator    │  │  └─ Storage (PDF archive)            │
│  ├─ VexBot (Gemini)  │  └──────────────────────────────────────┘
│  ├─ Razorpay SDK     │
│  └─ SMTP Email       │
└──────────────────────┘
               ▲
               │ Scheduled Trigger (daily 08:00 IST)
┌──────────────────────┐
│  GitHub Actions      │
│  cron_notifications  │
│  .py                 │
└──────────────────────┘
```

---

## 💳 Subscription Plans

AI Health Analysis and Manual PDF Reports are gated behind a subscription. Live OBD data streaming is always free.

| Plan | Price | Duration | Access |
|------|-------|----------|--------|
| **Single Report** | ₹49 | 1 use | 1 AI analysis or PDF report |
| **Explorer** | ₹99 | 7 days | Unlimited analyses & reports |
| **Pro** | ₹199 | 30 days | Unlimited analyses & reports |
| **Elite** | ₹499 | 1 year | Unlimited everything — best value |

Payments are processed via **Razorpay** (HMAC-SHA256 signature verified server-side). Subscription state is stored in Firestore under `users/{uid}/subscription/current`.

---

## ⚙️ Local Development

### Prerequisites
- Python 3.11+
- Node.js (for Firebase CLI)
- Firebase CLI: `npm install -g firebase-tools`
- A Razorpay account (test keys)
- A Firebase project with Auth + Firestore enabled

### 1. Clone the Repository

```bash
git clone https://github.com/Jivitesh06/Vexis.git
cd Vexis
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

Create `backend/.env`:

```env
FIREBASE_CREDENTIALS_PATH=firebase-service-account.json
MAIL_EMAIL=your-email@gmail.com
MAIL_PASSWORD=your-gmail-app-password
RAZORPAY_KEY_ID=rzp_test_XXXXXXXXXXXXXXX
RAZORPAY_KEY_SECRET=your_razorpay_test_secret
CRON_SECRET=your-cron-secret
```

Place your Firebase service account JSON at `backend/firebase-service-account.json`.

Run the backend:

```bash
python app.py
# Runs on http://localhost:5000
```

### 3. Frontend Setup

```bash
cd frontend
# No build step needed — pure HTML/JS/CSS
# Open index.html or use Firebase emulator
firebase serve
```

---

## 🔐 Environment Variables

### Backend (Render / `.env`)

| Variable | Description |
|----------|-------------|
| `FIREBASE_CREDENTIALS_JSON` | Full Firebase service account JSON (for production) |
| `FIREBASE_CREDENTIALS_PATH` | Path to service account file (for local dev) |
| `GEMINI_API_KEY` | Google AI Studio API Key for VexBot |
| `MAIL_EMAIL` | Gmail address for sending notifications |
| `MAIL_PASSWORD` | Gmail App Password (16-char, not regular password) |
| `RAZORPAY_KEY_ID` | Razorpay API Key ID |
| `RAZORPAY_KEY_SECRET` | Razorpay API Key Secret |
| `CRON_SECRET` | Secret key for protecting the cron HTTP endpoint |

### GitHub Actions Secrets

| Secret | Description |
|--------|-------------|
| `FIREBASE_CREDENTIALS_JSON` | Firebase service account JSON content |
| `MAIL_EMAIL` | Gmail address |
| `MAIL_PASSWORD` | Gmail App Password |

---

## 🚀 Deployment

### Frontend → Firebase Hosting

```bash
firebase login
firebase deploy --only hosting
```

### Backend → Render

1. Connect GitHub repo to Render
2. Set **Root Directory** to `backend`
3. Set **Build Command** to `pip install -r requirements.txt`
4. Set **Start Command** to `python app.py`
5. Add all environment variables listed above

### Automated Cron → GitHub Actions

The daily cron runs automatically via `.github/workflows/daily_cron.yml` every day at **02:30 UTC (08:00 AM IST)**. No manual setup needed after pushing to `main`.

To trigger manually: **GitHub → Actions → Vexis Daily Email Notifications → Run workflow**

---

## 📡 API Reference

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login |
| GET | `/api/auth/me` | Get current user profile |

### Predictions
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/predict` | ✅ | Single OBD reading → health scores |
| POST | `/api/predict/batch` | ✅ 💳 | Multi-row live analysis → report (subscription required) |
| POST | `/api/predict/csv` | ✅ 💳 | CSV upload → PDF report (subscription required) |
| GET | `/api/live-metrics` | ✅ | Simulated live OBD metrics |
| POST | `/api/chatbot/message` | ✅ | VexBot Gemini API with RAG context injection |

### Payments
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/payments/plans` | ❌ | List all subscription plans |
| GET | `/api/payments/status` | ✅ | Get current user subscription status |
| POST | `/api/payments/create-order` | ✅ | Create Razorpay order |
| POST | `/api/payments/verify` | ✅ | Verify payment + activate subscription |

### Vehicles & Reports
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/vehicles` | ✅ | List user vehicles |
| POST | `/api/vehicles` | ✅ | Add vehicle |
| GET | `/api/reports` | ✅ | List past reports |
| GET | `/api/health` | ❌ | Backend health check |
| GET | `/api/keep-alive` | ❌ | Prevents Render cold start |

---

## 📁 Project Structure

```
Vexis/
├── .github/
│   └── workflows/
│       └── daily_cron.yml          # GitHub Actions daily email cron
├── backend/
│   ├── ml/
│   │   └── model_loader.py         # Isolation Forest ML model loader
│   ├── models/                     # Trained .pkl model files
│   ├── routes/
│   │   ├── auth.py                 # Firebase auth endpoints
│   │   ├── notifications.py        # Email notification routes
│   │   ├── payments.py             # Razorpay payment gateway
│   │   ├── predict.py              # ML prediction endpoints (subscription gated)
│   │   ├── pdf_generator.py        # PDF report generation
│   │   ├── reports.py              # Report history routes
│   │   ├── timeline.py             # Vehicle health timeline
│   │   └── vehicles.py             # Vehicle management
│   ├── utils/
│   │   ├── email_sender.py         # SMTP email via Gmail
│   │   ├── email_templates.py      # HTML email templates
│   │   ├── firebase_auth.py        # Firebase SDK init + JWT middleware
│   │   └── validators.py           # OBD input validation
│   ├── app.py                      # Flask app entry point
│   ├── config.py                   # App configuration
│   ├── cron_notifications.py       # Standalone daily cron script
│   ├── obd_reader.py               # OBD-II WebSerial data handler
│   └── requirements.txt
├── frontend/
│   ├── css/
│   │   ├── global.css              # Design tokens + base styles
│   │   ├── dashboard.css           # Dashboard + sidebar styles
│   │   └── payments.css            # Pricing modal + payment UI
│   ├── js/
│   │   ├── api.js                  # Centralized API communication layer
│   │   ├── dashboard.js            # All dashboard section logic
│   │   ├── firebase.js             # Firebase SDK configuration
│   │   ├── manual-report.js        # CSV upload + PDF analysis flow
│   │   ├── obd_serial.js           # Web Serial API OBD connector
│   │   ├── payments.js             # Razorpay checkout + pricing modal
│   │   └── sidebar.js              # Navigation sidebar
│   ├── index.html                  # Login / landing page
│   ├── dashboard.html              # Main dashboard
│   ├── manual-report.html          # CSV upload page
│   └── reports.html                # Past reports page
└── README.md
```

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

<div align="center">
  <p>Built with ❤️ by <a href="https://github.com/Jivitesh06">Jivitesh</a></p>
  <p>
    <a href="https://vexis-527f2.web.app">🌐 Live Demo</a> ·
    <a href="https://vexis-backend-kklg.onrender.com/api/health">🔧 API Status</a>
  </p>
</div>
