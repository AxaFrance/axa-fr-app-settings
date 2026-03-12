from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, TypeAdapter

TBound = TypeVar("TBound")


class ConfigurationSection:
    """Read-only navigable view over configuration data."""

    def __init__(self, root: Mapping[str, Any], path: tuple[str, ...] = ()) -> None:
        self._root = root
        self._path = path

    @property
    def path(self) -> str:
        return ":".join(self._path)

    def exists(self) -> bool:
        try:
            self._resolve(strict=True)
        except KeyError:
            return False
        return True

    @property
    def value(self) -> Any:
        return deepcopy(self._resolve(strict=True))

    def get_value(self, path: str, default: Any = None) -> Any:
        try:
            resolved = _resolve_path(self._resolve(strict=True), _split_path(path), strict=True)
            return deepcopy(resolved)
        except KeyError:
            return default

    def __getitem__(self, path: str) -> Any:
        return deepcopy(_resolve_path(self._resolve(strict=True), _split_path(path), strict=True))

    def get_section(self, path: str) -> ConfigurationSection:
        return ConfigurationSection(self._root, self._path + tuple(_split_path(path)))

    def get(self, model_type: type[TBound]) -> TBound:
        data = self._resolve(strict=True)
        if isinstance(model_type, type) and issubclass(model_type, BaseModel):
            return model_type.model_validate(deepcopy(data))
        return TypeAdapter(model_type).validate_python(deepcopy(data))

    def as_dict(self) -> dict[str, Any]:
        data = self._resolve(strict=True)
        if not isinstance(data, Mapping):
            raise TypeError(f"Configuration section '{self.path or '<root>'}' is not a mapping")
        return deepcopy(dict(data))

    def _resolve(self, *, strict: bool) -> Any:
        return _resolve_path(self._root, list(self._path), strict=strict)


class ConfigurationRoot(ConfigurationSection, Generic[TBound]):
    def __init__(self, root: Mapping[str, Any], settings_type: type[Any] | None = None) -> None:
        super().__init__(root, ())
        self._settings_type = settings_type

    def bind(self) -> TBound:
        if self._settings_type is None:
            raise TypeError("No settings type was provided to this configuration root")
        return self.get(self._settings_type)


def _split_path(path: str) -> list[str]:
    return [part for part in path.split(":") if part]


def _resolve_path(data: Any, parts: list[str], *, strict: bool) -> Any:
    current = data
    for part in parts:
        if isinstance(current, Mapping):
            if part not in current:
                raise KeyError(":".join(parts))
            current = current[part]
            continue

        if isinstance(current, list):
            if not part.isdigit():
                raise KeyError(":".join(parts))
            index = int(part)
            if index < 0 or index >= len(current):
                raise KeyError(":".join(parts))
            current = current[index]
            continue

        if strict:
            raise KeyError(":".join(parts))
        return None

    return current
