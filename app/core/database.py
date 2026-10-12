import os
import sqlite3
from yoyo import get_backend, read_migrations
from app.core.config import config

def get_db() -> sqlite3.Connection:
    """Returns a raw SQLite connection."""
    conn = sqlite3.connect(config.database.path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def run_database_migrations():
    """Runs pending Yoyo raw SQL migrations automatically on startup."""
    print("[*] Running database migrations...")

    # Ensure local data directory exists
    db_dir = os.path.dirname(config.database.path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    # Configure Yoyo backend for SQLite
    backend_url = f"sqlite:///{config.database.path}"
    migrations_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../migrations"))

    backend = get_backend(backend_url)
    migrations = read_migrations(migrations_dir)

    with backend.lock():
        backend.apply_migrations(backend.to_apply(migrations))

    print("[+] Database migrations completed successfully.")