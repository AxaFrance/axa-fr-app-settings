from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pydantic import BaseModel

from .configuration import ConfigurationRoot
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

if TYPE_CHECKING:
    from .watcher import SettingsWatcher

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
        reload_on_change: bool = False,
    ) -> SettingsBuilder[TSettings]:
        self._sources.append(
            YamlFileSource(
                path=path,
                optional=optional,
                encoding=encoding,
                reload_on_change=reload_on_change,
            )
        )
        return self

    def add_json_file(
        self,
        path: str,
        *,
        optional: bool = False,
        encoding: str = "utf-8",
        reload_on_change: bool = False,
    ) -> SettingsBuilder[TSettings]:
        self._sources.append(
            JsonFileSource(
                path=path,
                optional=optional,
                encoding=encoding,
                reload_on_change=reload_on_change,
            )
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
        reload_on_change: bool = False,
    ) -> SettingsBuilder[TSettings]:
        self._sources.append(
            DotEnvFileSource(
                path=path,
                optional=optional,
                prefix=prefix,
                nested_delimiter=nested_delimiter,
                case_sensitive=case_sensitive,
                parse_values=parse_values,
                reload_on_change=reload_on_change,
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

    def build_configuration(self) -> ConfigurationRoot[TSettings]:
        return ConfigurationRoot(self.build_data(), self._settings_type)

    def build_watched(
        self,
        *,
        debounce_seconds: float = 0.3,
        polling_interval_seconds: float | None = None,
    ) -> SettingsWatcher[TSettings]:
        """
        Build the settings **and** start watching source files that have
        ``reload_on_change=True``.

        Returns a :class:`SettingsWatcher` whose ``.settings`` property
        always holds the latest snapshot.

        Parameters
        ----------
        debounce_seconds:
            Delay before rebuilding after a file change (avoids partial
            writes).  Default ``0.3``.
        polling_interval_seconds:
            If set, the watcher will also **poll** (rebuild) at this
            interval in seconds.  Useful for custom sources that are not
            file-based (e.g. Azure Key Vault, databases …).
            ``None`` (default) disables polling.

        Requires the ``watchdog`` package::

            uv add axa-fr-app-settings[watch]
        """
        from .watcher import SettingsWatcher as _Watcher

        watched: set[str] = set()
        for source in self._sources:
            if getattr(source, "reload_on_change", False) and hasattr(source, "path"):
                p = Path(source.path).resolve()  # type: ignore[union-attr]
                if p.exists():
                    watched.add(str(p))

        return _Watcher(
            build_fn=self.build,
            watched_paths=watched,
            debounce_seconds=debounce_seconds,
            polling_interval_seconds=polling_interval_seconds,
        )


ConfigurationBuilder = SettingsBuilder
