from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from .errors import ConfigurationError


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    serper_api_key: str
    firecrawl_api_key: str
    deepseek_api_key: str
    deepseek_model: str
    http_timeout_seconds: int
    max_urls_for_extraction: int
    firecrawl_poll_interval_seconds: int
    firecrawl_max_poll_seconds: int

    @staticmethod
    def load() -> "Settings":
        root = _project_root()
        dotenv_path = root / ".env"
        if dotenv_path.exists():
            try:
                from dotenv import load_dotenv  # type: ignore
            except ImportError as e:
                raise ConfigurationError(
                    "Missing dependency: python-dotenv. Install with: pip install -r requirements.txt"
                ) from e
            load_dotenv(dotenv_path=dotenv_path, override=False)

        def req(name: str) -> str:
            v = os.getenv(name, "").strip()
            if not v:
                raise ConfigurationError(
                    f"Missing required environment variable: {name}"
                )
            return v

        def opt_int(name: str, default: int) -> int:
            raw = os.getenv(name, "").strip()
            if not raw:
                return default
            try:
                return int(raw)
            except ValueError as e:
                raise ConfigurationError(f"Invalid integer for {name}: {raw}") from e

        deepseek_model = os.getenv("DEEPSEEK_MODEL", "").strip() or "deepseek-chat"

        return Settings(
            serper_api_key=req("SERPER_API_KEY"),
            firecrawl_api_key=req("FIRECRAWL_API_KEY"),
            deepseek_api_key=req("DEEPSEEK_API_KEY"),
            deepseek_model=deepseek_model,
            http_timeout_seconds=opt_int("HTTP_TIMEOUT_SECONDS", 30),
            max_urls_for_extraction=opt_int("MAX_URLS_FOR_EXTRACTION", 5),
            firecrawl_poll_interval_seconds=opt_int(
                "FIRECRAWL_POLL_INTERVAL_SECONDS", 2
            ),
            firecrawl_max_poll_seconds=opt_int("FIRECRAWL_MAX_POLL_SECONDS", 180),
        )
