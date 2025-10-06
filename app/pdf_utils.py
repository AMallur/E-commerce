"""Utility helpers for PDF ingestion and preprocessing."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

import pdfplumber
from pypdf import PdfReader

LOGGER = logging.getLogger(__name__)


def detect_rotation(pdf_path: Path) -> List[int]:
    """Return detected rotation for each page."""
    rotations: List[int] = []
    reader = PdfReader(str(pdf_path))
    for page in reader.pages:
        rotation = page.get("/Rotate", 0)
        rotations.append(int(rotation or 0))
    LOGGER.debug("Detected page rotations: %s", rotations)
    return rotations


def extract_text(pdf_path: Path) -> str:
    """Extract raw text from the PDF using pdfplumber."""
    text_parts: List[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            try:
                text_parts.append(page.extract_text() or "")
            except Exception as exc:  # pragma: no cover - logging path
                LOGGER.warning("Failed to extract text from page: %s", exc)
    return "\n".join(text_parts)


def iter_tables(pdf_path: Path, flavor: str = "lattice") -> List[List[List[str]]]:
    """Extract tables from the PDF using pdfplumber as a lightweight fallback."""
    tables: List[List[List[str]]] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
            try:
                table = page.extract_table()
                if table:
                    tables.append(table)
            except Exception as exc:  # pragma: no cover - logging path
                LOGGER.debug("Table extraction failed on page %s: %s", page_idx, exc)
    return tables


def is_scanned(pdf_path: Path) -> bool:
    """Heuristic to determine if the PDF is likely scanned (no embedded text)."""
    text = extract_text(pdf_path)
    return len(text.strip()) == 0


def ensure_directory(path: Path) -> None:
    """Ensure the parent directory exists."""
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)


__all__ = ["detect_rotation", "extract_text", "iter_tables", "is_scanned", "ensure_directory"]
