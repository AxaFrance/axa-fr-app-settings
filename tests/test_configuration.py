from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import Field

from axa_fr_app_settings import ConfigurationBuilder, SettingsModel


class EndpointSettings(SettingsModel):
    name: str
    url: str


class RegionSettings(SettingsModel):
    name: str
    endpoints: list[EndpointSettings] = Field(default_factory=list)


class AppSettingsSection(SettingsModel):
    application_name: str
    max_users: int
    feature_toggle: bool = False
    allowed_hosts: list[str] = Field(default_factory=list)
    regions: list[RegionSettings] = Field(default_factory=list)


class RootSettings(SettingsModel):
    appsettings: AppSettingsSection


def test_environment_variables_support_lists_and_nested_lists() -> None:
    settings = (
        ConfigurationBuilder(RootSettings)
        .add_environment_variables(
            environ={
                "APPSETTINGS__APPLICATION_NAME": "Portal",
                "APPSETTINGS__MAX_USERS": "42",
                "APPSETTINGS__ALLOWED_HOSTS__0": "api.local",
                "APPSETTINGS__ALLOWED_HOSTS__1": "admin.local",
                "APPSETTINGS__REGIONS__0__NAME": "eu-west",
                "APPSETTINGS__REGIONS__0__ENDPOINTS__0__NAME": "catalog",
                "APPSETTINGS__REGIONS__0__ENDPOINTS__0__URL": "https://eu/catalog",
                "APPSETTINGS__REGIONS__0__ENDPOINTS__1__NAME": "orders",
                "APPSETTINGS__REGIONS__0__ENDPOINTS__1__URL": "https://eu/orders",
                "APPSETTINGS__REGIONS__1__NAME": "us-east",
                "APPSETTINGS__REGIONS__1__ENDPOINTS__0__NAME": "catalog",
                "APPSETTINGS__REGIONS__1__ENDPOINTS__0__URL": "https://us/catalog",
            }
        )
        .build()
    )

    assert settings.appsettings.allowed_hosts == ["api.local", "admin.local"]
    assert len(settings.appsettings.regions) == 2
    assert settings.appsettings.regions[0].endpoints[1].name == "orders"
    assert settings.appsettings.regions[1].endpoints[0].url == "https://us/catalog"


def test_configuration_root_supports_colon_path_lookup_and_typed_section() -> None:
    config = (
        ConfigurationBuilder(RootSettings)
        .add_in_memory_collection(
            {
                "appsettings": {
                    "application_name": "Portal",
                    "max_users": 150,
                    "feature_toggle": True,
                    "allowed_hosts": ["api.local", "admin.local"],
                    "regions": [
                        {
                            "name": "eu-west",
                            "endpoints": [
                                {"name": "catalog", "url": "https://eu/catalog"}
                            ],
                        }
                    ],
                }
            }
        )
        .build_configuration()
    )

    assert config["appsettings:application_name"] == "Portal"
    assert config["appsettings:regions:0:endpoints:0:url"] == "https://eu/catalog"

    appsettings = config.get_section("appsettings").get(AppSettingsSection)
    assert appsettings.feature_toggle is True
    assert appsettings.max_users == 150
    assert appsettings.allowed_hosts[1] == "admin.local"

    bound = config.bind()
    assert bound.appsettings.application_name == "Portal"


def test_configuration_missing_key_raises_key_error() -> None:
    config = ConfigurationBuilder(RootSettings).add_in_memory_collection({}).build_configuration()

    with pytest.raises(KeyError):
        _ = config["appsettings:application_name"]


def test_env_file_supports_list_indexes(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "APPSETTINGS__APPLICATION_NAME=Portal",
                "APPSETTINGS__MAX_USERS=21",
                "APPSETTINGS__ALLOWED_HOSTS__0=public.local",
                "APPSETTINGS__ALLOWED_HOSTS__1=internal.local",
            ]
        ),
        encoding="utf-8",
    )

    settings = ConfigurationBuilder(RootSettings).add_env_file(env_file.as_posix()).build()

    assert settings.appsettings.allowed_hosts == ["public.local", "internal.local"]
