from __future__ import annotations

from pathlib import Path
from typing import List


class _Page:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text

    def extract_table(self):
        lines = [line for line in self._text.splitlines() if "\t" in line]
        if not lines:
            return None
        table = [lines[0].split("\t")]
        for line in lines[1:]:
            table.append(line.split("\t"))
        return table


class _PDF:
    def __init__(self, path: Path) -> None:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        self.pages = [_Page(_extract_text(raw))]

    def __enter__(self) -> "_PDF":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _extract_text(raw: str) -> str:
    if "(" not in raw:
        return raw
    parts = []
    capture = False
    buffer = []
    for char in raw:
        if char == "(":
            capture = True
            buffer = []
            continue
        if char == ")" and capture:
            parts.append("".join(buffer))
            capture = False
            continue
        if capture:
            buffer.append(char)
    return "\n".join(part.replace("\\n", "\n") for part in parts)


def open(path: str):
    return _PDF(Path(path))


__all__ = ["open"]
