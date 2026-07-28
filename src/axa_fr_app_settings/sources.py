from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import UnionType
from typing import Annotated, Any, Literal, Protocol, Union, get_args, get_origin

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel

FlatKeyNormalization = Literal["legacy", "preserve", "model"]
DynamicKeyCase = Literal["preserve", "lower"]
_FLAT_KEY_NORMALIZATIONS = frozenset({"legacy", "preserve", "model"})
_DYNAMIC_KEY_CASES = frozenset({"preserve", "lower"})


class SettingsSource(Protocol):
    def load(self) -> Mapping[str, Any]:
        ...


def _normalize_legacy_key(key: str, *, case_sensitive: bool) -> str:
    normalized = key.replace("-", "_")
    return normalized if case_sensitive else normalized.lower()


def _normalize_dynamic_key(key: str, *, dynamic_key_case: DynamicKeyCase) -> str:
    return key.lower() if dynamic_key_case == "lower" else key


def _unwrap_annotation(annotation: Any) -> Any:
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]

    if get_origin(annotation) in (Union, UnionType):
        union_types = [item for item in get_args(annotation) if item is not type(None)]
        if len(union_types) == 1:
            return _unwrap_annotation(union_types[0])

    return annotation


def _is_type(annotation: Any, expected_type: type[Any]) -> bool:
    try:
        return isinstance(annotation, type) and issubclass(annotation, expected_type)
    except TypeError:
        return False


def _mapping_value_type(annotation: Any) -> Any | None:
    annotation = _unwrap_annotation(annotation)
    origin = get_origin(annotation)

    if annotation in (dict, Mapping):
        return Any
    if origin is None or not _is_type(origin, Mapping):
        return None

    arguments = get_args(annotation)
    return arguments[1] if len(arguments) >= 2 else Any


def _sequence_item_type(annotation: Any) -> Any | None:
    annotation = _unwrap_annotation(annotation)
    origin = get_origin(annotation)

    if annotation is list:
        return Any
    if origin is not list:
        return None

    arguments = get_args(annotation)
    return arguments[0] if arguments else Any


def _field_input_names(field_name: str, field: Any) -> list[str]:
    names = [field_name]
    if isinstance(field.validation_alias, str):
        names.append(field.validation_alias)
    if isinstance(field.alias, str):
        names.append(field.alias)
    return list(dict.fromkeys(names))


def _match_model_field(
    model_type: type[BaseModel],
    key: str,
) -> tuple[str, Any] | None:
    exact_matches: list[tuple[str, str, Any]] = []
    casefold_matches: list[tuple[str, str, Any]] = []

    for field_name, field in model_type.model_fields.items():
        input_names = _field_input_names(field_name, field)
        exact_name = next((input_name for input_name in input_names if input_name == key), None)
        if exact_name is not None:
            exact_matches.append((field_name, exact_name, field.annotation))
            continue

        casefold_name = next(
            (input_name for input_name in input_names if input_name.casefold() == key.casefold()),
            None,
        )
        if casefold_name is not None:
            casefold_matches.append((field_name, casefold_name, field.annotation))

    matches = exact_matches or casefold_matches
    if not matches:
        return None

    if len(matches) > 1:
        raise ValueError(
            f"Configuration key '{key}' is ambiguous for model {model_type.__name__}"
        )
    _, input_name, annotation = matches[0]
    return input_name, annotation


def _normalize_model_path(
    parts: list[str],
    *,
    settings_type: type[BaseModel],
    ignore_unknown_root: bool,
    dynamic_key_case: DynamicKeyCase,
) -> list[str] | None:
    normalized_parts: list[str] = []
    annotation: Any = settings_type

    for index, part in enumerate(parts):
        annotation = _unwrap_annotation(annotation)

        if _is_type(annotation, BaseModel):
            field_match = _match_model_field(annotation, part)
            if field_match is None:
                if index == 0 and ignore_unknown_root:
                    return None
                normalized_parts.extend(
                    _normalize_legacy_key(remaining_part, case_sensitive=False)
                    for remaining_part in parts[index:]
                )
                break

            field_name, annotation = field_match
            normalized_parts.append(field_name)
            continue

        mapping_value_type = _mapping_value_type(annotation)
        if mapping_value_type is not None:
            normalized_parts.append(
                _normalize_dynamic_key(part, dynamic_key_case=dynamic_key_case)
            )
            annotation = mapping_value_type
            continue

        sequence_item_type = _sequence_item_type(annotation)
        if sequence_item_type is not None:
            normalized_parts.append(part)
            annotation = sequence_item_type
            continue

        normalized_parts.extend(parts[index:])
        break

    return normalized_parts


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


def mapping_from_flat_items(
    items: Mapping[str, Any],
    *,
    prefix: str = "",
    nested_delimiter: str = "__",
    case_sensitive: bool = False,
    key_normalization: FlatKeyNormalization = "legacy",
    dynamic_key_case: DynamicKeyCase = "preserve",
    settings_type: type[BaseModel] | None = None,
    ignore_unknown: bool = False,
    parse_values: bool = True,
) -> dict[str, Any]:
    """
    Convert flat key/value pairs into a nested configuration mapping.

    ``legacy`` keeps the historical lowercase/hyphen normalization,
    ``preserve`` keeps all segments unchanged, and ``model`` normalizes
    Pydantic fields while applying ``dynamic_key_case`` to mapping keys.
    """
    if key_normalization not in _FLAT_KEY_NORMALIZATIONS:
        raise ValueError(f"Unsupported key normalization: {key_normalization}")
    if dynamic_key_case not in _DYNAMIC_KEY_CASES:
        raise ValueError(f"Unsupported dynamic key case: {dynamic_key_case}")
    if key_normalization == "model" and settings_type is None:
        raise ValueError("settings_type is required for model key normalization")
    if dynamic_key_case != "preserve" and key_normalization != "model":
        raise ValueError("dynamic_key_case requires model key normalization")
    if ignore_unknown and key_normalization != "model":
        raise ValueError("ignore_unknown requires model key normalization")

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
        non_empty_parts = [part for part in parts if part]

        if key_normalization == "model":
            normalized_parts = _normalize_model_path(
                non_empty_parts,
                settings_type=settings_type,
                ignore_unknown_root=ignore_unknown,
                dynamic_key_case=dynamic_key_case,
            )
            if normalized_parts is None:
                continue
        elif key_normalization == "preserve":
            normalized_parts = non_empty_parts
        else:
            normalized_parts = [
                _normalize_legacy_key(part, case_sensitive=case_sensitive)
                for part in non_empty_parts
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
    key_normalization: FlatKeyNormalization = "legacy"
    settings_type: type[BaseModel] | None = None
    ignore_unknown_environment_variables: bool = False
    dynamic_key_case: DynamicKeyCase = "preserve"

    def load(self) -> Mapping[str, Any]:
        env = self.environ if self.environ is not None else os.environ
        return mapping_from_flat_items(
            env,
            prefix=self.prefix,
            nested_delimiter=self.nested_delimiter,
            case_sensitive=self.case_sensitive,
            key_normalization=self.key_normalization,
            dynamic_key_case=self.dynamic_key_case,
            settings_type=self.settings_type,
            ignore_unknown=self.ignore_unknown_environment_variables,
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
    key_normalization: FlatKeyNormalization = "legacy"
    settings_type: type[BaseModel] | None = None
    dynamic_key_case: DynamicKeyCase = "preserve"

    def load(self) -> Mapping[str, Any]:
        source_path = Path(self.path)
        if not source_path.exists():
            if self.optional:
                return {}
            raise FileNotFoundError(f".env file not found: {source_path}")

        values = dotenv_values(source_path)
        return mapping_from_flat_items(
            values,
            prefix=self.prefix,
            nested_delimiter=self.nested_delimiter,
            case_sensitive=self.case_sensitive,
            key_normalization=self.key_normalization,
            dynamic_key_case=self.dynamic_key_case,
            settings_type=self.settings_type,
            parse_values=self.parse_values,
        )
