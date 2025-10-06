from __future__ import annotations

from pathlib import Path


class _Page:
    def __init__(self) -> None:
        self._data = {"/Rotate": 0}

    def get(self, key, default=None):
        return self._data.get(key, default)


class PdfReader:
    def __init__(self, path: str) -> None:
        self.pages = [_Page()]


__all__ = ["PdfReader"]
