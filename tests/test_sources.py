from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from axa_fr_app_settings import (
    ConfigurationBuilder,
    EnvironmentVariablesSource,
    SettingsModel,
    StrictSettingsModel,
    mapping_from_flat_items,
)


class LiteralValueSettings(SettingsModel):
    youhou: str


class LiteralKeySettings(SettingsModel):
    youhou: dict[str, LiteralValueSettings]


class OIDCSettings(SettingsModel):
    client_id: str


class SmartGuideSettings(SettingsModel):
    llm_oidc: dict[str, OIDCSettings]


class RegionSettings(SettingsModel):
    client_id: str


class RegionalSettings(SettingsModel):
    regions: list[RegionSettings]


class StrictOIDCSettings(StrictSettingsModel):
    client_id: str


class StrictSmartGuideSettings(StrictSettingsModel):
    llm_oidc: dict[str, StrictOIDCSettings]


def test_environment_variables_can_preserve_all_key_segments() -> None:
    settings = (
        ConfigurationBuilder(LiteralKeySettings)
        .add_environment_variables(
            environ={"youhou__uuu-Toto__youhou": "ok"},
            key_normalization="preserve",
        )
        .build()
    )

    assert settings.youhou["uuu-Toto"].youhou == "ok"


def test_env_file_can_preserve_all_key_segments(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("youhou__uuu-Toto__youhou=ok\n", encoding="utf-8")

    settings = (
        ConfigurationBuilder(LiteralKeySettings)
        .add_env_file(env_file.as_posix(), key_normalization="preserve")
        .build()
    )

    assert settings.youhou["uuu-Toto"].youhou == "ok"


def test_flat_keys_keep_existing_normalization_by_default() -> None:
    data = ConfigurationBuilder(LiteralKeySettings).add_environment_variables(
        environ={"youhou__uuu-Toto__youhou": "ok"},
    ).build_data()

    assert data == {"youhou": {"uuu_toto": {"youhou": "ok"}}}


def test_environment_source_keeps_0_4_1_positional_arguments() -> None:
    source = EnvironmentVariablesSource("", "__", False, False, {"Some-Key": "VALUE"})

    assert source.load() == {"some_key": "VALUE"}


def test_mapping_from_flat_items_is_public_and_can_preserve_keys() -> None:
    data = mapping_from_flat_items(
        {"APP__Some-Key": "42"},
        case_sensitive=False,
        key_normalization="preserve",
    )

    assert data == {"APP": {"Some-Key": 42}}


def test_model_normalization_preserves_dynamic_keys_and_normalizes_fields() -> None:
    settings = (
        ConfigurationBuilder(SmartGuideSettings)
        .add_environment_variables(
            environ={"LLM_OIDC__gpt-4o__CLIENT_ID": "smartguide-client"},
            key_normalization="model",
        )
        .build()
    )

    assert list(settings.llm_oidc) == ["gpt-4o"]
    assert settings.llm_oidc["gpt-4o"].client_id == "smartguide-client"


def test_model_normalization_is_available_for_env_files(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LLM_OIDC__gpt-4o__CLIENT_ID=smartguide-client\n",
        encoding="utf-8",
    )

    settings = (
        ConfigurationBuilder(SmartGuideSettings)
        .add_env_file(env_file.as_posix(), key_normalization="model")
        .build()
    )

    assert settings.llm_oidc["gpt-4o"].client_id == "smartguide-client"


def test_model_normalization_traverses_list_items() -> None:
    settings = (
        ConfigurationBuilder(RegionalSettings)
        .add_environment_variables(
            environ={"REGIONS__0__CLIENT_ID": "regional-client"},
            key_normalization="model",
        )
        .build()
    )

    assert settings.regions[0].client_id == "regional-client"


def test_unknown_environment_variables_can_be_filtered() -> None:
    settings = (
        ConfigurationBuilder(StrictSmartGuideSettings)
        .add_environment_variables(
            environ={
                "LLM_OIDC__gpt-4o__CLIENT_ID": "smartguide-client",
                "PATH": "/usr/bin",
                "UNRELATED__VALUE": "ignored",
            },
            key_normalization="model",
            ignore_unknown_environment_variables=True,
        )
        .build()
    )

    assert settings.llm_oidc["gpt-4o"].client_id == "smartguide-client"


def test_unknown_nested_environment_variable_is_not_silently_filtered() -> None:
    builder = ConfigurationBuilder(StrictSmartGuideSettings).add_environment_variables(
        environ={
            "LLM_OIDC__gpt-4o__CLIENT_ID": "smartguide-client",
            "LLM_OIDC__gpt-4o__UNKNOWN": "invalid",
        },
        key_normalization="model",
        ignore_unknown_environment_variables=True,
    )

    with pytest.raises(ValidationError, match="extra_forbidden"):
        builder.build()


def test_empty_environment_mapping_does_not_fall_back_to_os_environ(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_OIDC__gpt-4o__CLIENT_ID", "system-client")

    data = (
        ConfigurationBuilder(SmartGuideSettings)
        .add_environment_variables(
            environ={},
            key_normalization="model",
        )
        .build_data()
    )

    assert data == {}


def test_model_normalization_requires_a_settings_type() -> None:
    with pytest.raises(ValueError, match="settings_type is required"):
        mapping_from_flat_items(
            {"LLM_OIDC__gpt-4o__CLIENT_ID": "smartguide-client"},
            key_normalization="model",
        )


def test_unknown_filter_requires_model_normalization() -> None:
    builder = ConfigurationBuilder(SmartGuideSettings).add_environment_variables(
        environ={"PATH": "/usr/bin"},
        ignore_unknown_environment_variables=True,
    )

    with pytest.raises(ValueError, match="ignore_unknown requires model"):
        builder.build_data()
