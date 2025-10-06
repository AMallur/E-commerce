from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable


@dataclass
class _Field:
    default: Any = None
    default_factory: Callable[[], Any] | None = None
    description: str | None = None

    def resolve(self) -> Any:
        if self.default_factory is not None:
            return self.default_factory()
        return self.default


def Field(*, default: Any = None, default_factory: Callable[[], Any] | None = None, description: str | None = None) -> _Field:
    return _Field(default=default, default_factory=default_factory, description=description)


class _Validator:
    def __init__(self, fields: Iterable[str], pre: bool = False) -> None:
        self.fields = tuple(fields)
        self.pre = pre
        self.func: Callable[..., Any] | None = None

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        func.__validator_config__ = self  # type: ignore[attr-defined]
        return func


def validator(*fields: str, pre: bool = False) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    return _Validator(fields, pre=pre)


__all__ = ["Field", "validator"]
