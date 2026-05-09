import psycopg2
import psycopg2.extras
import time
from config import Config


# ──────────────────────────────────────────────
# FUNCTION 1 — get_db()
# Returns a new psycopg2 connection using Config
# Includes TCP keepalive to prevent SSL drops
# ──────────────────────────────────────────────
def get_db():
    ssl_mode = 'require' if Config.DB_HOST != 'localhost' else 'prefer'
    conn = psycopg2.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        dbname=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        sslmode=ssl_mode,
        connect_timeout=5,      # fail fast — don't block for 20s per attempt
        # TCP keepalive — prevents SSL drop on idle connections
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )
    conn.cursor_factory = psycopg2.extras.RealDictCursor
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
                firebase_uid VARCHAR(128) UNIQUE,
                email VARCHAR(255) UNIQUE NOT NULL,
                name VARCHAR(100),
                profile_photo_url VARCHAR(500),
                alternate_contact VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Migrate existing tables — add column if it doesn't exist
        cursor.execute("""
            ALTER TABLE users
                ADD COLUMN IF NOT EXISTS firebase_uid VARCHAR(128) UNIQUE,
                ADD COLUMN IF NOT EXISTS profile_photo_url VARCHAR(500),
                ADD COLUMN IF NOT EXISTS alternate_contact VARCHAR(255);
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
                plate_number VARCHAR(50),
                purchase_year VARCHAR(20),
                owner_number INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("""
            ALTER TABLE vehicles
                ADD COLUMN IF NOT EXISTS plate_number VARCHAR(50),
                ADD COLUMN IF NOT EXISTS purchase_year VARCHAR(20),
                ADD COLUMN IF NOT EXISTS owner_number INTEGER;
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
        raise   # let app.py know init failed

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ──────────────────────────────────────────────
# FUNCTION 3 — execute_query()
# Retries up to 3 times on SSL/connection errors
# (handles Neon / Render PostgreSQL cold-starts)
# ──────────────────────────────────────────────
def execute_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    MAX_RETRIES = 2  # 2 retries × 5s timeout = max 10s blocked, not 3 min
    last_error  = None

    for attempt in range(1, MAX_RETRIES + 1):
        conn   = None
        cursor = None
        try:
            conn   = get_db()
            cursor = conn.cursor()
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

        except psycopg2.OperationalError as e:
            last_error = e
            err_str = str(e).lower()
            # SSL drop / connection reset — worth retrying
            if any(k in err_str for k in ('ssl', 'connection', 'closed', 'reset', 'timeout')):
                print(f"[DB] Attempt {attempt}/{MAX_RETRIES} failed (SSL/conn): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(attempt * 1.5)   # 1.5s, 3s backoff
                    continue
            raise   # non-retriable operational error

        except psycopg2.Error as e:
            # Non-retriable DB error (syntax, constraint, etc.)
            print(f"Database error in execute_query: {e}")
            raise

        finally:
            if cursor:
                try: cursor.close()
                except Exception: pass
            if conn:
                try: conn.close()
                except Exception: pass

    # All retries exhausted
    print(f"[DB] All {MAX_RETRIES} retries failed: {last_error}")
    raise last_error


# ──────────────────────────────────────────────
# Entry point — run directly to initialize DB
# ──────────────────────────────────────────────
def test_connection():
    try:
        conn = get_db()
        cur  = conn.cursor()
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
