import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, model_validator
import yaml

load_dotenv()


# --- Domain Models ---

class PlaneType(BaseModel):
    """One aircraft: a kill type (colonial_planes) or one of our own (warden_planes)."""
    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    description: str

class AirfieldConfig(BaseModel):
    colonial_planes: list[PlaneType] = Field(default_factory=list)
    warden_planes: list[PlaneType] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_keys(self):
        """Ensure no duplicate plane keys exist in colonial_planes or warden_planes."""
        colonial_keys = [p.key for p in self.colonial_planes]
        if len(colonial_keys) != len(set(colonial_keys)):
            raise ValueError("Duplicate 'key' found in colonial_planes config!")
        warden_keys = [p.key for p in self.warden_planes]
        if len(warden_keys) != len(set(warden_keys)):
            raise ValueError("Duplicate 'key' found in warden_planes config!")
        return self

    @property
    def colonial_planes_by_key(self) -> dict[str, PlaneType]:
        return {p.key: p for p in self.colonial_planes}

    @property
    def warden_planes_by_key(self) -> dict[str, PlaneType]:
        return {p.key: p for p in self.warden_planes}

    # --- Kill types: the colonial planes pilots can report shooting down ---

    @property
    def kill_types(self) -> list[PlaneType]:
        """The kill types in dropdown order."""
        return self.colonial_planes

    def kill_type_label(self, key: str) -> str:
        """Display name for a stored kill type key. A type later removed from the config shows under its key."""
        plane = self.colonial_planes_by_key.get(key)
        return plane.label if plane else key

    def kill_type_position(self, key: str) -> int:
        """Sort position of a stored kill type key; keys no longer in the config sort last."""
        keys = [p.key for p in self.colonial_planes]
        return keys.index(key) if key in keys else len(keys)


class FeatureConfig(BaseModel):
    airfield: AirfieldConfig = Field(default_factory=AirfieldConfig)


class BotConfig(BaseModel):
    token: str = ""
    command_prefix: str = "!"
    owner_ids: list[int] = Field(default_factory=list)


class DatabaseConfig(BaseModel):
    path: str = "data/bot.db"
    max_connections: int = 5


# --- Root Config ---

class AppConfig(BaseModel):
    bot: BotConfig = Field(default_factory=BotConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    features: FeatureConfig = Field(default_factory=FeatureConfig)

    @property
    def colonial_planes_by_key(self) -> dict[str, PlaneType]:
        return self.features.airfield.colonial_planes_by_key

    @property
    def warden_planes_by_key(self) -> dict[str, PlaneType]:
        return self.features.airfield.warden_planes_by_key


# --- Loader Function ---

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

    # Allow environment variables as fallback if not explicitly configured in yaml
    env_prefix = os.getenv("COMMAND_PREFIX")
    if env_prefix and "command_prefix" not in data.get("bot", {}):
        data.setdefault("bot", {})["command_prefix"] = env_prefix

    env_db_path = os.getenv("DATABASE_PATH")
    if env_db_path and "path" not in data.get("database", {}):
        data.setdefault("database", {})["path"] = env_db_path

    return AppConfig(**data)


def reload_config(file_path: str | Path | None = None) -> AppConfig:
    """Reloads config from disk and updates the global instance in place. Raises (leaving it untouched) if invalid."""
    new_config = load_config(file_path)
    config.bot = new_config.bot
    config.database = new_config.database
    config.features = new_config.features
    return config


# Instantiate globally
config: AppConfig = load_config()
