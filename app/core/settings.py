"""Bot-wide key/value settings and the active war. Shared by every feature."""
from app.core.database import get_db


def get_setting(key: str) -> str | None:
    with get_db() as conn:
        row = conn.execute("SELECT value FROM bot_config WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None


def set_setting(key: str, value: str):
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO bot_config (key, value) VALUES (?, ?)", (key, value))
        conn.commit()


def get_active_war() -> int:
    value = get_setting("active_war")
    return int(value) if value else 1


def set_active_war(war_number: int):
    set_setting("active_war", str(war_number))
