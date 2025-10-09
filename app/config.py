"""Application configuration using pydantic-settings."""
from __future__ import annotations

from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Configuration values for the accounting workspace."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = Field(default="Aurora Accounting Workspace")
    default_currency: str = Field(default="USD", min_length=3, max_length=3)
    fiscal_year_start_month: int = Field(default=1, ge=1, le=12)
    seed_demo_data: bool = Field(
        default=True,
        description="Seed the in-memory engine with illustrative demo data.",
    )
    max_entries_returned: int = Field(default=200)

    @validator("default_currency")
    def _uppercase_currency(cls, value: str) -> str:
        return value.upper()


_settings: AppSettings | None = None


def get_settings() -> AppSettings:
    """Return a cached instance of the application settings."""

    global _settings
    if _settings is None:
        _settings = AppSettings()
    return _settings


__all__ = ["AppSettings", "get_settings"]
