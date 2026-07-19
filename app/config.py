"""Application configuration.

All secrets and tunables come from environment variables so nothing
sensitive is ever committed to the repository (see .env.example).
"""

import os
from dataclasses import dataclass, field


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings."""

    anthropic_api_key: str = field(
        default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", "")
    )
    anthropic_model: str = field(
        default_factory=lambda: os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    )
    llm_timeout_seconds: int = field(default_factory=lambda: _int_env("LLM_TIMEOUT_SECONDS", 20))
    rate_limit_per_minute: int = field(default_factory=lambda: _int_env("RATE_LIMIT_PER_MINUTE", 30))
    max_question_chars: int = field(default_factory=lambda: _int_env("MAX_QUESTION_CHARS", 500))

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


def get_settings() -> Settings:
    """Build settings fresh so tests can monkeypatch the environment."""
    return Settings()
