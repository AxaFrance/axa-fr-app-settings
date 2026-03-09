from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from .merge import deep_merge
from .sources import (
    CallableSource,
    DictSource,
    DotEnvFileSource,
    EnvironmentVariablesSource,
    JsonFileSource,
    SettingsSource,
    YamlFileSource,
)

TSettings = TypeVar("TSettings", bound=BaseModel)


class SettingsBuilder(Generic[TSettings]):
    """
    Builder de configuration typée proche du ConfigurationBuilder .NET.
    """

    def __init__(self, settings_type: type[TSettings]) -> None:
        self._settings_type = settings_type
        self._sources: list[SettingsSource] = []

    def add_yaml_file(
        self,
        path: str,
        *,
        optional: bool = False,
        encoding: str = "utf-8",
    ) -> SettingsBuilder[TSettings]:
        self._sources.append(
            YamlFileSource(path=path, optional=optional, encoding=encoding)
        )
        return self

    def add_json_file(
        self,
        path: str,
        *,
        optional: bool = False,
        encoding: str = "utf-8",
    ) -> SettingsBuilder[TSettings]:
        self._sources.append(
            JsonFileSource(path=path, optional=optional, encoding=encoding)
        )
        return self

    def add_env_file(
        self,
        path: str = ".env",
        *,
        optional: bool = False,
        prefix: str = "",
        nested_delimiter: str = "__",
        case_sensitive: bool = False,
        parse_values: bool = True,
    ) -> SettingsBuilder[TSettings]:
        self._sources.append(
            DotEnvFileSource(
                path=path,
                optional=optional,
                prefix=prefix,
                nested_delimiter=nested_delimiter,
                case_sensitive=case_sensitive,
                parse_values=parse_values,
            )
        )
        return self

    def add_environment_variables(
        self,
        *,
        prefix: str = "",
        nested_delimiter: str = "__",
        case_sensitive: bool = False,
        parse_values: bool = True,
        environ: Mapping[str, str] | None = None,
    ) -> SettingsBuilder[TSettings]:
        self._sources.append(
            EnvironmentVariablesSource(
                prefix=prefix,
                nested_delimiter=nested_delimiter,
                case_sensitive=case_sensitive,
                parse_values=parse_values,
                environ=environ,
            )
        )
        return self

    def add_in_memory_collection(
        self,
        data: Mapping[str, Any],
    ) -> SettingsBuilder[TSettings]:
        self._sources.append(DictSource(data=data))
        return self

    def add_source(
        self,
        source: SettingsSource | Callable[[], Mapping[str, Any]],
    ) -> SettingsBuilder[TSettings]:
        if callable(source):
            self._sources.append(CallableSource(factory=source))
        else:
            self._sources.append(source)
        return self

    def build_data(self) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for source in self._sources:
            merged = deep_merge(merged, source.load())
        return merged

    def build(self) -> TSettings:
        data = self.build_data()
        return self._settings_type.model_validate(data)


ConfigurationBuilder = SettingsBuilder
