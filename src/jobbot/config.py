"""Settings: non-secret knobs from config.yaml, secrets from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


@dataclass(slots=True)
class Secrets:
    telegram_bot_token: str = ""
    admin_chat_id: int | None = None
    database_url: str = ""
    jooble_api_key: str = ""
    gemini_api_key: str = ""

    @classmethod
    def from_env(cls) -> Secrets:
        admin = os.getenv("ADMIN_CHAT_ID", "").strip()
        return cls(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            admin_chat_id=int(admin) if admin.lstrip("-").isdigit() else None,
            database_url=os.getenv("DATABASE_URL", "").strip(),
            jooble_api_key=os.getenv("JOOBLE_API_KEY", "").strip(),
            gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        )


@dataclass(slots=True)
class Settings:
    raw: dict[str, Any]
    secrets: Secrets = field(default_factory=Secrets)

    # --- convenience accessors -------------------------------------------------
    @property
    def digest(self) -> dict[str, Any]:
        return self.raw.get("digest", {})

    @property
    def scoring(self) -> dict[str, Any]:
        return self.raw.get("scoring", {})

    @property
    def sources(self) -> dict[str, Any]:
        return self.raw.get("sources", {})

    @property
    def http(self) -> dict[str, Any]:
        return self.raw.get("http", {})

    @property
    def llm(self) -> dict[str, Any]:
        return self.raw.get("llm", {})

    @property
    def retention(self) -> dict[str, Any]:
        return self.raw.get("retention", {})

    def source_options(self, name: str) -> dict[str, Any]:
        return self.sources.get(name) or {}

    def source_enabled(self, name: str) -> bool:
        return bool(self.source_options(name).get("enabled", False))


def load_settings(path: str | Path | None = None, *, load_env_file: bool = True) -> Settings:
    if load_env_file:
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:  # pragma: no cover
            pass
    config_path = Path(path or os.getenv("JOBBOT_CONFIG") or DEFAULT_CONFIG_PATH)
    raw = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
    settings = Settings(raw=raw or {}, secrets=Secrets.from_env())
    _validate(settings)
    return settings


def _validate(settings: Settings) -> None:
    weights = settings.scoring.get("weights")
    if weights:
        total = sum(float(v) for v in weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"scoring.weights must sum to 1.0 (got {total:.3f})")
