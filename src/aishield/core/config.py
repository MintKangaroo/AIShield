"""Validated application configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """AIShield runtime settings loaded from ``AISHIELD_*`` variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AISHIELD_",
        extra="ignore",
        frozen=True,
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    compute_device: Literal["cpu", "cuda"] = "cpu"
    database_url: str = "postgresql://aishield:aishield@localhost:5432/aishield"
    redis_url: str = "redis://localhost:6379/0"
    artifact_root: Path = Path("artifacts")
    model_root: Path = Path("artifacts/models")
    dataset_root: Path = Path("data")
    allow_public_downloads: bool = False
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"]
    )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings object."""

    return Settings()
