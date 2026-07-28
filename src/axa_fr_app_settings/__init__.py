import contextlib

from .base import SettingsModel, StrictSettingsModel
from .builder import ConfigurationBuilder, SettingsBuilder
from .configuration import ConfigurationRoot, ConfigurationSection
from .sources import (
    CallableSource,
    DictSource,
    DotEnvFileSource,
    EnvironmentVariablesSource,
    JsonFileSource,
    SettingsSource,
    YamlFileSource,
    mapping_from_flat_items,
)

with contextlib.suppress(ImportError):
    from .watcher import SettingsWatcher

__all__ = [
    "CallableSource",
    "ConfigurationBuilder",
    "ConfigurationRoot",
    "ConfigurationSection",
    "DictSource",
    "DotEnvFileSource",
    "EnvironmentVariablesSource",
    "JsonFileSource",
    "SettingsBuilder",
    "SettingsModel",
    "SettingsSource",
    "SettingsWatcher",
    "StrictSettingsModel",
    "YamlFileSource",
    "mapping_from_flat_items",
]
