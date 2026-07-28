from __future__ import annotations

import pytest
from pydantic import ValidationError

from axa_fr_app_settings import (
    ConfigurationBuilder,
    SettingsModel,
    StrictSettingsModel,
)


class StrictNestedSettings(StrictSettingsModel):
    value: int


class StrictRootSettings(StrictSettingsModel):
    nested: StrictNestedSettings


class PermissiveSettings(SettingsModel):
    value: int


def test_strict_settings_model_rejects_unknown_root_key() -> None:
    builder = ConfigurationBuilder(StrictRootSettings).add_in_memory_collection(
        {
            "nested": {"value": 1},
            "unexpected": True,
        }
    )

    with pytest.raises(ValidationError, match="extra_forbidden"):
        builder.build()


def test_strict_settings_model_rejects_unknown_nested_key() -> None:
    builder = ConfigurationBuilder(StrictRootSettings).add_in_memory_collection(
        {
            "nested": {
                "value": 1,
                "unexpected": True,
            }
        }
    )

    with pytest.raises(ValidationError, match="extra_forbidden"):
        builder.build()


def test_settings_model_keeps_ignoring_unknown_keys() -> None:
    settings = (
        ConfigurationBuilder(PermissiveSettings)
        .add_in_memory_collection({"value": 1, "unexpected": True})
        .build()
    )

    assert settings.model_dump() == {"value": 1}
