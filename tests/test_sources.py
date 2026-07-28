from __future__ import annotations

from pathlib import Path

from axa_fr_app_settings import (
    ConfigurationBuilder,
    SettingsModel,
    mapping_from_flat_items,
)


class LiteralValueSettings(SettingsModel):
    youhou: str


class LiteralKeySettings(SettingsModel):
    youhou: dict[str, LiteralValueSettings]


def test_environment_variables_preserve_literal_key_segments() -> None:
    settings = (
        ConfigurationBuilder(LiteralKeySettings)
        .add_environment_variables(
            environ={"youhou__uuu-Toto__youhou": "ok"},
            preserve_keys=True,
        )
        .build()
    )

    assert settings.youhou["uuu-Toto"].youhou == "ok"


def test_env_file_preserves_literal_key_segments(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("youhou__uuu-Toto__youhou=ok\n", encoding="utf-8")

    settings = (
        ConfigurationBuilder(LiteralKeySettings)
        .add_env_file(env_file.as_posix(), preserve_keys=True)
        .build()
    )

    assert settings.youhou["uuu-Toto"].youhou == "ok"


def test_flat_keys_keep_existing_normalization_by_default() -> None:
    data = ConfigurationBuilder(LiteralKeySettings).add_environment_variables(
        environ={"youhou__uuu-Toto__youhou": "ok"},
    ).build_data()

    assert data == {"youhou": {"uuu_toto": {"youhou": "ok"}}}


def test_mapping_from_flat_items_is_public_and_can_preserve_keys() -> None:
    data = mapping_from_flat_items(
        {"APP__Some-Key": "42"},
        case_sensitive=False,
        preserve_keys=True,
    )

    assert data == {"APP": {"Some-Key": 42}}
