from __future__ import annotations

from typing import Any, Dict

from pydantic import _Field


class SettingsConfigDict(dict):
    pass


class BaseSettings:
    def __init__(self, **overrides: Any) -> None:
        annotations = getattr(self, "__annotations__", {})
        for name in annotations:
            value = overrides.get(name, getattr(self.__class__, name, None))
            if isinstance(value, _Field):
                value = value.resolve()
            setattr(self, name, value)
        for attr_name in dir(self.__class__):
            attr = getattr(self.__class__, attr_name)
            validator_config = getattr(attr, "__validator_config__", None)
            if validator_config:
                for field in validator_config.fields:
                    current = getattr(self, field)
                    new_value = attr(self.__class__, current)
                    setattr(self, field, new_value)


__all__ = ["BaseSettings", "SettingsConfigDict"]
