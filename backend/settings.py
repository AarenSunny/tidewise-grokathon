"""App settings loaded from environment (review1-#15)."""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "TideWise"
    app_env: str = "development"
    debug: bool = False
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    # Comma-separated; empty ⇒ no CORS (safer). Dev default set in .env.example.
    cors_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")
    upstream_timeout_s: float = 8.0
    upstream_max_retries: int = 3
    cache_default_ttl_seconds: int = 300
    nws_user_agent: str = "TideWise/0.1 (https://github.com/AarenSunny/tidewise-grokathon)"
    orchestrator_deadline_s: float = 20.0
    orchestrator_max_concurrency: int = 8

    def cors_origin_list(self) -> List[str]:
        parts = [p.strip() for p in self.cors_origins.split(",") if p.strip()]
        if self.debug and not parts:
            return ["http://localhost:5173"]
        return parts


@lru_cache
def get_settings() -> Settings:
    # Ensure dotenv is loaded for non-pydantic consumers
    try:
        from dotenv import load_dotenv

        load_dotenv(override=False)
    except ImportError:
        pass
    return Settings()
