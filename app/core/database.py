import os
import logging

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection
from yoyo import get_backend, read_migrations

from app.core.config import config

logger = logging.getLogger(__name__)

_BEGIN_OPTION = "sqlite_begin"
_BEGIN_MODES = {"DEFERRED": "DEFERRED", "IMMEDIATE": "IMMEDIATE"}

class Database:
    """Owns the SQLAlchemy Engine and hands out connections."""

    def __init__(self, url: str):
        self.url = url
        self._engine = create_engine(url, connect_args={"check_same_thread": False}, future=True)

        @event.listens_for(self._engine, "connect")
        def _on_connect(dbapi_connection, connection_record):
            dbapi_connection.isolation_level = None
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")
            cursor.close()

        @event.listens_for(self._engine, "begin")
        def _on_begin(conn):
            mode = _BEGIN_MODES[conn.get_execution_options().get(_BEGIN_OPTION, "DEFERRED")]
            conn.exec_driver_sql(f"BEGIN {mode}")

    @classmethod
    def from_config(cls) -> "Database":
        return cls(f"sqlite:///{config.database.path}")

    def connect(self) -> Connection:
        return self._engine.connect()

    @contextmanager
    def begin(self) -> Iterator[Connection]:
        with self.connect() as conn:
            conn.execution_options(**{_BEGIN_OPTION: "IMMEDIATE"})
            with conn.begin():
                yield conn


db = Database.from_config()

def run_database_migrations():
    """Runs pending Yoyo raw SQL migrations automatically on startup."""
    logger.info("Running database migrations...")

    # Ensure local data directory exists
    db_dir = os.path.dirname(config.database.path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    migrations_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../migrations"))

    backend = get_backend(db.url)
    migrations = read_migrations(migrations_dir)

    with backend.lock():
        backend.apply_migrations(backend.to_apply(migrations))

    logger.info("Database migrations completed successfully.")