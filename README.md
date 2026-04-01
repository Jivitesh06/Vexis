# Vexis — AI Vehicle Health Intelligence

AI-powered vehicle health scoring system
using OBD-II sensor data and Isolation
Forest ML models.

## Tech Stack
- Frontend: HTML, CSS, JavaScript
- Backend: Python Flask + Flask-SocketIO
- Database: PostgreSQL (Supabase)
- ML: 5x Isolation Forest models
- OBD: USB ELM327 via Web Serial API
- Email: Gmail SMTP
- Deploy: Render + Netlify + Supabase

## Features
- Real-time OBD data via Web Serial API
- Live metrics dashboard
- AI health analysis (batch prediction)
- Email verification system
- JWT authentication
- PDF health reports
- Forgot password flow
- Responsive design (mobile/tablet/desktop)

## Local Setup

### Backend
```bash
cd vexis/backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your values
python database.py
python app.py
```

### Frontend
```bash
cd vexis/frontend
python -m http.server 3000
# Open: http://localhost:3000
```

## ML Models
5 Isolation Forest models trained on
Vehicle Energy Dataset (VED) Kaggle.
Components: Engine | Fuel | Efficiency | Driving | Thermal

Scoring: decision_function() → 0-100
Final: Weighted median aggregation

## OBD Connection
1. Plug USB ELM327 into car OBD port
2. Open dashboard in Chrome
3. Click "Connect OBD Scanner"
4. Select COM port from browser
5. Live data streams automatically
6. Click "Start Health Analysis"
   for ML-powered scoring

## API
```
GET  /api/health             → server status
POST /api/auth/signup
POST /api/auth/login
POST /api/predict/batch      → main ML endpoint
GET  /api/reports            → past reports
GET  /api/reports/download/<id> → PDF
```

## Deployment
| Service  | Platform        |
|----------|----------------|
| Database | Supabase.com (free PostgreSQL) |
| Backend  | Render.com (free tier)         |
| Frontend | Netlify.com (free tier)        |

## College Project
AI/ML Vehicle Health Scoring System  
Training data: Vehicle Energy Dataset (VED) from Kaggle  
~100K rows, 5 components
