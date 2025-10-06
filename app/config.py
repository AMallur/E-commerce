"""Application configuration using pydantic-settings."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Configuration values for the application."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    data_dir: Path = Field(default=Path("data"), description="Directory for reference data.")
    template_dir: Path = Field(
        default=Path("app/templates"), description="Directory containing HTML templates."
    )
    output_currency: str = Field(default="$", description="Currency symbol for display.")
    redact_phi: bool = Field(default=True, description="Whether to redact PHI in reports.")
    persist_uploads: bool = Field(
        default=False, description="Whether to keep uploaded files instead of deleting them."
    )
    tessdata_prefix: Optional[str] = Field(
        default=None, description="Optional override for Tesseract language data directory."
    )
    ocr_languages: str = Field(default="eng", description="Languages to use for OCR.")
    llm_provider: Optional[str] = Field(default=None, description="LLM provider identifier.")
    llm_api_key: Optional[str] = Field(default=None, description="LLM provider API key.")
    report_footer_disclaimer: str = Field(
        default="Educational summary, not medical or legal advice.",
        description="Disclaimer text for generated reports.",
    )
    timezone: str = Field(default="UTC", description="Timezone for parsing dates.")
    table_engines: List[str] = Field(
        default_factory=lambda: ["camelot_lattice", "camelot_stream", "tabula"],
        description="Preferred table extraction engines in order.",
    )
    min_column_score: float = Field(
        default=0.5,
        description="Minimum column consistency score required to accept table extraction.",
    )
    currency_regex: str = Field(
        default=r"[-+]?\$?\d{1,3}(?:,\d{3})*(?:\.\d{2})?",
        description="Regex for locating currency values.",
    )
    date_formats: List[str] = Field(
        default_factory=lambda: ["%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"],
        description="Accepted date formats in source documents.",
    )
    code_dictionary_path: Path = Field(
        default=Path("data/codes.json"),
        description="Path to editable code dictionary for friendly descriptions.",
    )
    glossary_path: Path = Field(
        default=Path("data/glossary.json"), description="Path to glossary terms for reports."
    )
    enable_llm: bool = Field(default=False, description="Enable LLM powered explanations.")

    @validator("data_dir", "template_dir", "code_dictionary_path", "glossary_path", pre=True)
    def expand_path(cls, value: Path | str) -> Path:
        """Expand user-relative paths to absolute ones."""
        path = Path(value)
        if not path.is_absolute():
            path = Path.cwd() / path
        return path


def get_settings() -> AppSettings:
    """Return a cached instance of the application settings."""
    return AppSettings()


__all__ = ["AppSettings", "get_settings"]
