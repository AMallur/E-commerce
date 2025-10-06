"""Utilities for redacting PHI from logs and documents."""
from __future__ import annotations

import re
from typing import Iterable

_PHI_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN format
    re.compile(r"\b\d{2}/\d{2}/\d{4}\b"),  # dates
    re.compile(r"\bMRN\s*[:#]?\s*\w+", re.IGNORECASE),
    re.compile(r"\bAccount\s*#\s*\w+", re.IGNORECASE),
]


def redact_text(text: str, extra_patterns: Iterable[str] | None = None) -> str:
    """Redact PHI-like patterns from the given text."""
    patterns = list(_PHI_PATTERNS)
    if extra_patterns:
        patterns.extend(re.compile(p) for p in extra_patterns)
    redacted = text
    for pattern in patterns:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


__all__ = ["redact_text"]
