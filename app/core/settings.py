"""Bot-wide key/value settings and the active war. Shared by every feature."""
from sqlalchemy import text

from app.libs.world.faction import Faction
from app.core .database import db

DEFAULT_FACTION = Faction.Warden

def get_setting(key: str) -> str | None:
    with db.connect() as conn:
        row = conn.execute(
            text("SELECT value FROM bot_config WHERE key = :key"), {"key": key}
        ).mappings().first()
        return row["value"] if row else None


def set_setting(key: str, value: str):
    with db.begin() as conn:
        conn.execute(
            text("INSERT OR REPLACE INTO bot_config (key, value) VALUES (:key, :value)"), {"key": key, "value": value})


def get_active_war() -> int:
    value = get_setting("active_war")
    return int(value) if value else 1


def set_active_war(war_number: int):
    set_setting("active_war", str(war_number))


def get_faction(war: int | None = None) -> Faction:
    """The faction being played in war"""
    value = get_setting(f"war.{war if war is not None else get_active_war()}.faction")
    return Faction(value) if value in Faction else DEFAULT_FACTION


def set_faction(faction: Faction, war: int | None = None):
    set_setting(f"war.{war if war is not None else get_active_war()}.faction", Faction(faction).value)
