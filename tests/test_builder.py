from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import Field

from axa_fr_app_settings import ConfigurationBuilder, SettingsModel


class DatabaseSettings(SettingsModel):
    endpoint_url: str


class CacheRedisSettings(SettingsModel):
    expiry_time: int = 60


class CacheSettings(SettingsModel):
    type: str = "redis"
    redis: CacheRedisSettings = Field(default_factory=CacheRedisSettings)


class AppSettings(SettingsModel):
    debug: bool = False
    http_timeout: int = 45
    database: dict[str, DatabaseSettings] = Field(default_factory=dict)
    cache: CacheSettings = Field(default_factory=CacheSettings)


def test_yaml_then_environment_variables_override_nested_values(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        """
        debug: false
        http_timeout: 45
        database:
          main:
            endpoint_url: postgresql://base
        cache:
          redis:
            expiry_time: 60
        """,
        encoding="utf-8",
    )

    settings = (
        ConfigurationBuilder(AppSettings)
        .add_yaml_file(settings_file.as_posix())
        .add_environment_variables(
            environ={
                "DEBUG": "true",
                "CACHE__REDIS__EXPIRY_TIME": "120",
                "DATABASE__main__ENDPOINT_URL": "postgresql://override",
            }
        )
        .build()
    )

    assert settings.debug is True
    assert settings.cache.redis.expiry_time == 120
    assert settings.database["main"].endpoint_url == "postgresql://override"


def test_json_and_in_memory_collection_merge(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "debug": False,
                "database": {
                    "main": {
                        "endpoint_url": "postgresql://json",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    settings = (
        ConfigurationBuilder(AppSettings)
        .add_json_file(settings_file.as_posix())
        .add_in_memory_collection({"http_timeout": 90})
        .build()
    )

    assert settings.http_timeout == 90
    assert settings.database["main"].endpoint_url == "postgresql://json"


def test_env_file_is_supported(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "DEBUG=true",
                "HTTP_TIMEOUT=30",
                "CACHE__REDIS__EXPIRY_TIME=180",
            ]
        ),
        encoding="utf-8",
    )

    settings = (
        ConfigurationBuilder(AppSettings)
        .add_env_file(env_file.as_posix())
        .build()
    )

    assert settings.debug is True
    assert settings.http_timeout == 30
    assert settings.cache.redis.expiry_time == 180


def test_missing_optional_file_is_ignored(tmp_path: Path) -> None:
    settings = (
        ConfigurationBuilder(AppSettings)
        .add_yaml_file((tmp_path / "missing.yaml").as_posix(), optional=True)
        .build()
    )

    assert settings.debug is False


def test_missing_required_file_raises(tmp_path: Path) -> None:
    builder = ConfigurationBuilder(AppSettings).add_yaml_file(
        (tmp_path / "missing.yaml").as_posix(),
        optional=False,
    )

    with pytest.raises(FileNotFoundError):
        builder.build()
