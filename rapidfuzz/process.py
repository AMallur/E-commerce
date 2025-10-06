from __future__ import annotations

from typing import Iterable, Optional, Tuple


def extractOne(query: str, choices: Iterable[str]) -> Optional[Tuple[str, int, int]]:
    """Very small stand-in for rapidfuzz.process.extractOne."""
    best_choice: Optional[str] = None
    best_score = -1
    best_index = -1
    for idx, choice in enumerate(choices):
        score = _simple_ratio(query.lower(), choice.lower())
        if score > best_score:
            best_score = score
            best_choice = choice
            best_index = idx
    if best_choice is None:
        return None
    return best_choice, best_score, best_index


def _simple_ratio(a: str, b: str) -> int:
    """Return a naive similarity score between two strings."""
    if not a or not b:
        return 0
    matches = sum(1 for ch1, ch2 in zip(a, b) if ch1 == ch2)
    return int(100 * matches / max(len(a), len(b)))
