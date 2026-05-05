import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # App
    SECRET_KEY = os.getenv("SECRET_KEY", "vexis-secret-key-change-in-production")
    DEBUG = os.getenv("DEBUG", "False") == "True"
    PORT  = int(os.getenv("PORT", 5000))

    # PostgreSQL Database
    DB_HOST     = os.getenv("DB_HOST", "localhost")
    DB_PORT     = os.getenv("DB_PORT", "5432")
    DB_NAME     = os.getenv("DB_NAME", "vexis_db")
    DB_USER     = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD")

    # ML Models
    ML_MODELS_PATH = "models_pkl/"

    # CORS
    CORS_ORIGINS = os.getenv(
        "CORS_ORIGINS", 
        "http://localhost:3000,http://localhost:5000,https://vexis-527f2.web.app"
    ).split(",")

    # Firebase
    FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase-service-account.json")

    # Email / SMTP
    MAIL_EMAIL    = os.getenv("MAIL_EMAIL")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_NAME     = os.getenv("MAIL_NAME", "Vexis")
    FRONTEND_URL  = os.getenv("FRONTEND_URL", "http://localhost:5000")
    BACKEND_URL   = os.getenv(
        "BACKEND_URL",
        "http://localhost:5000"
    )

    # OBD Feature names (must match exactly what models were trained on)
    OBD_FEATURES = [
        'engine_rpm',
        'vehicle_speed',
        'coolant_temp',
        'engine_load_pct',
        'throttle_pos',
        'short_fuel_trim',
        'long_fuel_trim',
        'intake_air_temp',
        'maf',
        'fuel_level',
        'o2_voltage'
    ]

    # Score → Status label mapping
    SCORE_LABELS = [
        (80, 100, "Excellent"),
        (60, 79,  "Good"),
        (40, 59,  "Moderate"),
        (0,  39,  "Critical")
    ]

    @staticmethod
    def get_status_label(score):
        for low, high, label in Config.SCORE_LABELS:
            if low <= score <= high:
                return label
        return "Unknown"
