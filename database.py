import sqlite3
from contextlib import contextmanager

DB_PATH = "dashboard.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db_cursor(commit=False):
    conn = get_connection()
    cur = conn.cursor()
    try:
        yield cur
        if commit:
            conn.commit()
    finally:
        conn.close()


def init_db():
    with db_cursor(commit=True) as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS team_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL DEFAULT '',
                fb_access_token TEXT NOT NULL DEFAULT '',
                fb_ad_account_id TEXT NOT NULL DEFAULT '',
                google_developer_token TEXT NOT NULL DEFAULT '',
                google_client_id TEXT NOT NULL DEFAULT '',
                google_client_secret TEXT NOT NULL DEFAULT '',
                google_refresh_token TEXT NOT NULL DEFAULT '',
                google_customer_id TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                member_id INTEGER NOT NULL,
                traffic_channel TEXT NOT NULL DEFAULT 'facebook',
                rule_object TEXT NOT NULL DEFAULT 'campaign',
                campaign_filter TEXT NOT NULL DEFAULT '',
                schedule_minutes INTEGER NOT NULL DEFAULT 5,
                notify_email TEXT NOT NULL DEFAULT '',
                notify_webhook TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (member_id) REFERENCES team_members(id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS rule_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER NOT NULL,
                action TEXT NOT NULL DEFAULT 'pause',
                scale_value REAL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (rule_id) REFERENCES rules(id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS action_conditions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_id INTEGER NOT NULL,
                metric TEXT NOT NULL,
                operator TEXT NOT NULL DEFAULT 'gte',
                value REAL NOT NULL DEFAULT 0,
                time_range TEXT NOT NULL DEFAULT 'today',
                FOREIGN KEY (action_id) REFERENCES rule_actions(id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                action TEXT NOT NULL,
                object_id TEXT,
                object_name TEXT,
                object_type TEXT,
                traffic_channel TEXT,
                member_name TEXT,
                cost REAL,
                rule_name TEXT,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS monitor_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id TEXT NOT NULL,
                object_name TEXT NOT NULL,
                object_type TEXT NOT NULL DEFAULT 'campaign',
                traffic_channel TEXT NOT NULL DEFAULT 'facebook',
                member_name TEXT NOT NULL DEFAULT '',
                platform_id TEXT NOT NULL DEFAULT '',
                cost REAL NOT NULL DEFAULT 0,
                revenue REAL NOT NULL DEFAULT 0,
                roi REAL NOT NULL DEFAULT 0,
                matched_rule TEXT,
                matched_action TEXT,
                pause_status TEXT NOT NULL,
                monitored_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('dry_run', 'true')")
        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('redtrack_api_key', 'COLE_SUA_API_KEY_AQUI')")


def get_setting(key: str, default: str = "") -> str:
    with db_cursor() as cur:
        cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with db_cursor(commit=True) as cur:
        cur.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
