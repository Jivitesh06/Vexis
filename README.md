<div align="center">
  <img src="frontend/assets/logo.png" alt="Vexis Logo" width="120" />
  <h1>Vexis — AI Vehicle Health Intelligence</h1>
  <p><strong>Predictive maintenance and real-time vehicle health scoring using OBD-II sensor data and Machine Learning.</strong></p>
</div>

## 🚀 Overview

Vexis is a cutting-edge, web-based platform that brings enterprise-level vehicle diagnostics to everyday drivers. By connecting an OBD-II scanner directly to your browser via the **Web Serial API**, Vexis streams live engine data to an **AI-powered backend**. 

Instead of just showing raw numbers, our **Isolation Forest ML models** analyze the data across 5 core components to generate a human-readable Health Score (0-100), predict future degradation, and provide actionable service recommendations before critical failures occur.

## ✨ Key Features

- 🏎️ **Live OBD-II Streaming:** Connects directly via USB/Bluetooth ELM327 using the browser's Web Serial API. No native app required.
- 🧠 **AI Service Intelligence:** 5 specialized ML models evaluate Engine, Fuel, Efficiency, Driving, and Thermal systems to detect anomalies.
- 🔮 **Predictive Degradation Forecast:** Calculates the velocity of health decline and predicts how many days until your vehicle reaches a POOR or CRITICAL state.
- 📊 **Manual CSV Reports:** Upload offline OBD data files for instant batch analysis and PDF report generation.
- 🔔 **Automated Cron Notifications:** Daily background tasks evaluate your vehicle's timeline and send HTML email alerts if urgent service is needed.
- 📱 **Premium UI/UX:** Built with a stunning dark-mode glassmorphism design, interactive Chart.js visualizations, and responsive layouts.

## 🛠️ Technology Stack

Vexis underwent a major architectural upgrade to ensure high availability and robust performance.

### Frontend
- **Core:** Vanilla JS (ES Modules), HTML5, CSS3
- **Styling:** Custom CSS with Glassmorphism, CSS Variables, and Orbitron typography
- **Data Viz:** Chart.js
- **PDF Generation:** jsPDF
- **Hosting:** Firebase Hosting

### Backend & ML
- **Framework:** Python, Flask, Flask-SocketIO (Eventlet)
- **Machine Learning:** Scikit-Learn (Isolation Forests), Pandas, NumPy
- **Email:** Gmail SMTP (Port 587 STARTTLS)
- **Hosting:** Render (Web Service)

### Database & Auth
- **Provider:** Firebase / Google Cloud
- **Authentication:** Firebase Auth (Email/Password)
- **Database:** Cloud Firestore (NoSQL Document Store)
- **Storage:** Firebase Storage (for PDF archiving)

### Automation
- **Cron Jobs:** cron-job.org triggering secure backend Flask endpoints.

## ⚙️ Local Development Setup

### 1. Backend Setup
```bash
# Navigate to backend
cd vexis/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Environment Variables
# Create a .env file based on .env.example
# Ensure you have your Firebase Admin SDK JSON file ready and linked in the .env

# Run the Flask Server
python app.py
```
*Backend will run on `http://127.0.0.1:5000`*

### 2. Frontend Setup
```bash
# Navigate to frontend
cd vexis/frontend

# Start a local Python HTTP server
python -m http.server 3000
```
*Open `http://localhost:3000` in your browser. Note: Update `js/api.js` to point to `http://127.0.0.1:5000/api` for local testing.*

## 🔌 OBD Connection Guide

1. Plug a USB or Bluetooth ELM327 adapter into your car's OBD-II port.
2. Open the Vexis Dashboard in Google Chrome or Microsoft Edge (Safari/Firefox do not support Web Serial).
3. Click **"Connect OBD Scanner"**.
4. Select the appropriate COM port from the browser prompt.
5. Live sensor data will begin streaming automatically via WebSockets.
6. Click **"Start Health Analysis"** to trigger the AI scoring engine.

## 🤖 ML Models & Training

Our models were trained on a subset of the **Vehicle Energy Dataset (VED)** from Kaggle, comprising over 100,000 rows of real-world driving data.
- **Algorithm:** Isolation Forest (unsupervised anomaly detection)
- **Scoring:** `decision_function()` mapped to a normalized 0-100 scale.
- **Final Output:** A weighted median aggregation of the 5 component scores determines the overall Vehicle Health Tier (EXCELLENT, GOOD, FAIR, POOR, CRITICAL).

## 🌍 Production Environment

| Service | Platform |
|---------|----------|
| **Frontend UI** | Firebase Hosting (`vexis-527f2.web.app`) |
| **Backend API** | Render (`vexis-backend-kklg.onrender.com`) |
| **Database** | Google Cloud Firestore |
| **Cron Triggers** | cron-job.org |

## 🎓 Academic Context
This project was developed as a comprehensive AI/ML College Project focusing on predictive maintenance and IoT edge-to-cloud integration.
