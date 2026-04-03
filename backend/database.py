import psycopg2
import psycopg2.extras
from config import Config


# ──────────────────────────────────────────────
# FUNCTION 1 — get_db()
# Returns a new psycopg2 connection using Config
# ──────────────────────────────────────────────
def get_db():
    conn = psycopg2.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        dbname=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        sslmode='require',
        connect_timeout=15
    )
    conn.cursor_factory = \
        psycopg2.extras.RealDictCursor
    return conn


# ──────────────────────────────────────────────
# FUNCTION 2 — init_db()
# Creates all required tables if they don't exist
# ──────────────────────────────────────────────
def init_db():
    conn = None
    cursor = None
    try:
        conn = get_db()
        cursor = conn.cursor()

        # TABLE 1: users
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_verified BOOLEAN DEFAULT FALSE,
                verify_token TEXT,
                verify_token_expiry TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Migrate existing tables — add columns if they don't exist
        cursor.execute("""
            ALTER TABLE users
                ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;
        """)
        cursor.execute("""
            ALTER TABLE users
                ADD COLUMN IF NOT EXISTS verify_token TEXT;
        """)
        cursor.execute("""
            ALTER TABLE users
                ADD COLUMN IF NOT EXISTS verify_token_expiry TIMESTAMP;
        """)
        print("Table 'users' ready.")

        # TABLE 2: vehicles
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(100),
                model VARCHAR(100),
                vin VARCHAR(50),
                year INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("Table 'vehicles' ready.")

        # TABLE 3: reports
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                vehicle_id INTEGER REFERENCES vehicles(id) ON DELETE SET NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                engine_score FLOAT,
                fuel_score FLOAT,
                stress_score FLOAT,
                overall_score FLOAT,
                failure_risk INTEGER,
                status_label VARCHAR(20),
                raw_input JSONB,
                issues JSONB
            );
        """)
        print("Table 'reports' ready.")

        conn.commit()

    except Exception as e:
        print(f"Error during init_db: {e}")

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ──────────────────────────────────────────────
# FUNCTION 3 — execute_query()
# General-purpose safe query executor
# ──────────────────────────────────────────────
def execute_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = None
    cursor = None
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Always use parameterized queries — never string formatting
        cursor.execute(query, params)

        if commit:
            conn.commit()

        if fetchone:
            row = cursor.fetchone()
            return dict(row) if row else None

        if fetchall:
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        return None

    except psycopg2.Error as e:
        print(f"Database error in execute_query: {e}")
        raise

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ──────────────────────────────────────────────
# Entry point — run directly to initialize DB
# ──────────────────────────────────────────────
def test_connection():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT version();")
        result = cur.fetchone()
        print(f"DB Connected: {result}")
        conn.close()
        return True
    except Exception as e:
        print(f"DB Connection failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()
    init_db()
