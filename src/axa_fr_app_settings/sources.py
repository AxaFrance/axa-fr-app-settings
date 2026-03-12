from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import yaml
from dotenv import dotenv_values


class SettingsSource(Protocol):
    def load(self) -> Mapping[str, Any]:
        ...


def _normalize_key(key: str, *, case_sensitive: bool) -> str:
    normalized = key.replace("-", "_")
    return normalized if case_sensitive else normalized.lower()


def _parse_scalar(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    stripped = value.strip()
    if stripped == "":
        return ""

    try:
        return yaml.safe_load(stripped)
    except yaml.YAMLError:
        return value


def _ensure_list_size(items: list[Any], index: int) -> None:
    while len(items) <= index:
        items.append(None)


def _create_container_for_next_key(next_key: str) -> dict[str, Any] | list[Any]:
    return [] if next_key.isdigit() else {}


def _set_nested(mapping: dict[str, Any], keys: list[str], value: Any) -> None:
    current: Any = mapping
    parent: dict[str, Any] | list[Any] | None = None
    parent_key: str | int | None = None

    for index, key in enumerate(keys):
        is_last = index == len(keys) - 1
        next_key = keys[index + 1] if not is_last else None

        if isinstance(current, dict):
            if is_last:
                current[key] = value
                return

            next_value = current.get(key)
            expected_is_list = bool(next_key and next_key.isdigit())
            if expected_is_list and not isinstance(next_value, list):
                next_value = []
                current[key] = next_value
            elif not expected_is_list and not isinstance(next_value, dict):
                next_value = {}
                current[key] = next_value

            parent = current
            parent_key = key
            current = next_value
            continue

        if isinstance(current, list):
            if not key.isdigit():
                raise ValueError(f"List segment expects a numeric index, got '{key}'")

            numeric_key = int(key)
            _ensure_list_size(current, numeric_key)

            if is_last:
                current[numeric_key] = value
                return

            next_value = current[numeric_key]
            expected_container = _create_container_for_next_key(next_key or "")
            if not isinstance(next_value, type(expected_container)):
                next_value = expected_container
                current[numeric_key] = next_value

            parent = current
            parent_key = numeric_key
            current = next_value
            continue

        replacement = _create_container_for_next_key(key)
        if (
            isinstance(parent, dict)
            and isinstance(parent_key, str)
            or isinstance(parent, list)
            and isinstance(parent_key, int)
        ):
            parent[parent_key] = replacement
        current = replacement

    raise ValueError("Nested key path cannot be empty")


def _mapping_from_flat_items(
    items: Mapping[str, Any],
    *,
    prefix: str = "",
    nested_delimiter: str = "__",
    case_sensitive: bool = False,
    parse_values: bool = True,
) -> dict[str, Any]:
    output: dict[str, Any] = {}

    for raw_key, raw_value in items.items():
        if raw_value is None:
            continue

        if prefix and not raw_key.startswith(prefix):
            continue

        key = raw_key[len(prefix):] if prefix else raw_key
        if not key:
            continue

        parts = key.split(nested_delimiter) if nested_delimiter else [key]

        normalized_parts = [
            _normalize_key(part, case_sensitive=case_sensitive)
            for part in parts
            if part
        ]

        if not normalized_parts:
            continue

        value = _parse_scalar(raw_value) if parse_values else raw_value
        _set_nested(output, normalized_parts, value)

    return output


@dataclass(slots=True)
class DictSource:
    data: Mapping[str, Any]

    def load(self) -> Mapping[str, Any]:
        return dict(self.data)


@dataclass(slots=True)
class CallableSource:
    factory: Callable[[], Mapping[str, Any]]

    def load(self) -> Mapping[str, Any]:
        return dict(self.factory())


@dataclass(slots=True)
class YamlFileSource:
    path: str | Path
    optional: bool = False
    encoding: str = "utf-8"
    reload_on_change: bool = False

    def load(self) -> Mapping[str, Any]:
        source_path = Path(self.path)
        if not source_path.exists():
            if self.optional:
                return {}
            raise FileNotFoundError(f"YAML settings file not found: {source_path}")

        with source_path.open("r", encoding=self.encoding) as file:
            data = yaml.safe_load(file) or {}

        if not isinstance(data, dict):
            raise TypeError(f"YAML settings root must be a mapping: {source_path}")

        return data


@dataclass(slots=True)
class JsonFileSource:
    path: str | Path
    optional: bool = False
    encoding: str = "utf-8"
    reload_on_change: bool = False

    def load(self) -> Mapping[str, Any]:
        source_path = Path(self.path)
        if not source_path.exists():
            if self.optional:
                return {}
            raise FileNotFoundError(f"JSON settings file not found: {source_path}")

        with source_path.open("r", encoding=self.encoding) as file:
            data = json.load(file) or {}

        if not isinstance(data, dict):
            raise TypeError(f"JSON settings root must be a mapping: {source_path}")

        return data


@dataclass(slots=True)
class EnvironmentVariablesSource:
    prefix: str = ""
    nested_delimiter: str = "__"
    case_sensitive: bool = False
    parse_values: bool = True
    environ: Mapping[str, str] | None = None

    def load(self) -> Mapping[str, Any]:
        env = self.environ or os.environ
        return _mapping_from_flat_items(
            env,
            prefix=self.prefix,
            nested_delimiter=self.nested_delimiter,
            case_sensitive=self.case_sensitive,
            parse_values=self.parse_values,
        )


@dataclass(slots=True)
class DotEnvFileSource:
    path: str | Path = ".env"
    optional: bool = False
    prefix: str = ""
    nested_delimiter: str = "__"
    case_sensitive: bool = False
    parse_values: bool = True
    reload_on_change: bool = False

    def load(self) -> Mapping[str, Any]:
        source_path = Path(self.path)
        if not source_path.exists():
            if self.optional:
                return {}
            raise FileNotFoundError(f".env file not found: {source_path}")

        values = dotenv_values(source_path)
        return _mapping_from_flat_items(
            values,
            prefix=self.prefix,
            nested_delimiter=self.nested_delimiter,
            case_sensitive=self.case_sensitive,
            parse_values=self.parse_values,
        )
