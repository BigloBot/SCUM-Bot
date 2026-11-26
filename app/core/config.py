import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
import yaml

from app.libs.models import Strict
from app.libs.world.hexes import Hexes
from app.libs.world.units import Forces

load_dotenv()

class WorldConfig(Forces):
    """config.yaml's `world` section, shared by every feature as `config.world`"""
    hexes: Hexes = Field(default_factory=lambda: Hexes([]))


class BotConfig(Strict):
    token: str = ""
    owner_ids: list[int] = Field(default_factory=list)


class DatabaseConfig(Strict):
    path: str = "data/bot.db"


class AppConfig(Strict):
    bot: BotConfig = Field(default_factory=BotConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    world: WorldConfig = Field(default_factory=WorldConfig)


# --- Config Loader ---

def _find_config_file(file_path: str | Path | None = None) -> Path:
    if file_path is None:
        file_path = os.getenv("CONFIG_PATH", "config.yaml")

    path = Path(file_path)
    if not path.is_absolute() and not path.exists():
        # Fall back to project root directory relative to this file
        project_root = Path(__file__).resolve().parent.parent.parent
        alt_path = project_root / file_path
        if alt_path.exists():
            return alt_path

    return path


def load_config(file_path: str | Path | None = None) -> AppConfig:
    path = _find_config_file(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found at {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # Override token from environment variable (secrets should always prefer env)
    env_token = os.getenv("DISCORD_TOKEN")
    if env_token:
        data.setdefault("bot", {})["token"] = env_token

    env_db_path = os.getenv("DATABASE_PATH")
    if env_db_path and "path" not in data.get("database", {}):
        data.setdefault("database", {})["path"] = env_db_path

    return AppConfig(**data)


def reload_config(file_path: str | Path | None = None) -> AppConfig:
    """Reloads config from disk and updates the global instance in place. Raises (leaving it untouched) if invalid."""
    new_config = load_config(file_path)
    config.bot = new_config.bot
    config.world = new_config.world
    return config


# Instantiate globally
config: AppConfig = load_config()
