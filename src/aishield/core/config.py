"""Validated application configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
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
    # "journal" keeps the default stack a single dependency-free process; "postgresql"
    # shares metadata across processes, which a multi-worker deployment requires.
    metadata_backend: Literal["journal", "postgresql"] = "journal"
    database_pool_size: int = Field(default=5, ge=1, le=64)
    redis_url: str = "redis://localhost:6379/0"
    artifact_root: Path = Path("artifacts")
    model_root: Path = Path("artifacts/models")
    dataset_root: Path = Path("data")
    allow_public_downloads: bool = False
    # Unset means the API is open, which keeps the local demo and CI free of
    # secret management. Setting it protects every registry route at once.
    # The minimum length refuses a key weak enough to be guessed.
    api_key: SecretStr | None = Field(default=None, min_length=16)
    # One heavy evaluation at a time by default: a single box cannot honestly run
    # several full torch evaluations concurrently without distorting latency evidence.
    max_concurrent_runs: int = Field(default=1, ge=1, le=64)
    # "inprocess" runs jobs on the API's own threads; "redis" hands them to a
    # separate `aishield-worker` process that owns its own CPU and memory budget.
    job_backend: Literal["inprocess", "redis"] = "inprocess"
    job_max_workers: int = Field(default=2, ge=1, le=32)
    job_max_pending: int = Field(default=16, ge=1, le=1024)
    job_retained_records: int = Field(default=256, ge=1, le=100_000)
    # Upper bound on how long a queued worker waits for a run slot before failing.
    job_slot_timeout_seconds: float = Field(default=900.0, gt=0.0, le=86_400.0)
    # Rebuild the in-memory index from the metadata journal when the process starts.
    replay_journal_on_start: bool = True
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"]
    )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings object."""

    return Settings()
