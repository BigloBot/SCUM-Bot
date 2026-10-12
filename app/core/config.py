import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator
import yaml

load_dotenv()


# --- Domain Models ---

class PlaneType(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    description: str
    name: Optional[str] = None
    role: Optional[str] = None

    @property
    def display_label(self) -> str:
        """Returns the label with the role in brackets, e.g. 'Harbinger (Fighter)'."""
        if self.role:
            return f"{self.label} ({self.role})"
        return self.label

    def get(self, item: str, default=None):
        val = getattr(self, item, None)
        return val if val is not None else default

    def __getitem__(self, item: str):
        if item == "display_label":
            return self.display_label
        if item == "name":
            return self.name or self.label.split(" (")[0]
        if item == "role":
            if self.role:
                return self.role
            if "(" in self.label and self.label.endswith(")"):
                return self.label.split(" (")[-1][:-1]
            return ""
        return getattr(self, item)


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

    # Dynamic Lookup Caches
    _colonial_planes_by_key: dict[str, PlaneType] = PrivateAttr(default_factory=dict)
    _warden_planes_by_key: dict[str, PlaneType] = PrivateAttr(default_factory=dict)

    def model_post_init(self, __context):
        """Build fast lookup dictionaries after loading."""
        self._colonial_planes_by_key = {p.key: p for p in self.features.airfield.colonial_planes}
        self._warden_planes_by_key = {p.key: p for p in self.features.airfield.warden_planes}

    @property
    def colonial_planes_by_key(self) -> dict[str, PlaneType]:
        return self._colonial_planes_by_key

    @property
    def warden_planes_by_key(self) -> dict[str, PlaneType]:
        return self._warden_planes_by_key


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
    """Reloads config from disk and updates the global instance."""
    global config
    new_config = load_config(file_path)
    config.bot = new_config.bot
    config.database = new_config.database
    config.features = new_config.features
    config.model_post_init(None)
    return config


# Instantiate globally
config: AppConfig = load_config()


# --- Backwards Compatibility Shim ---

class _ConfigCompat:
    """Provides backwards-compatible access to the legacy Config class attributes."""
    @property
    def DISCORD_TOKEN(self) -> str:
        return config.bot.token

    @property
    def COMMAND_PREFIX(self) -> str:
        return config.bot.command_prefix

    @property
    def DATABASE_PATH(self) -> str:
        return config.database.path


Config = _ConfigCompat()