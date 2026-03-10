"""Tests for the reloadOnChange / SettingsWatcher feature."""

from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from pydantic import Field

from axa_fr_app_settings import ConfigurationBuilder, SettingsModel

# We need watchdog for these tests
watchdog = pytest.importorskip("watchdog")


# ── Test models ──────────────────────────────────────────────────────

class SimpleSettings(SettingsModel):
    debug: bool = False
    http_timeout: int = 45


class NestedInner(SettingsModel):
    value: int = 0


class NestedSettings(SettingsModel):
    debug: bool = False
    inner: NestedInner = Field(default_factory=NestedInner)


# ── Tests ────────────────────────────────────────────────────────────

def test_build_watched_returns_initial_settings(tmp_path: Path) -> None:
    yaml_file = tmp_path / "settings.yaml"
    yaml_file.write_text("debug: true\nhttp_timeout: 10\n")

    watcher = (
        ConfigurationBuilder(SimpleSettings)
        .add_yaml_file(yaml_file.as_posix(), reload_on_change=True)
        .build_watched()
    )

    assert watcher.settings.debug is True
    assert watcher.settings.http_timeout == 10


def test_build_watched_reloads_on_file_change(tmp_path: Path) -> None:
    yaml_file = tmp_path / "settings.yaml"
    yaml_file.write_text("debug: false\nhttp_timeout: 45\n")

    watcher = (
        ConfigurationBuilder(SimpleSettings)
        .add_yaml_file(yaml_file.as_posix(), reload_on_change=True)
        .build_watched(debounce_seconds=0.1)
    )

    reloaded = threading.Event()
    watcher.on_change(lambda _s: reloaded.set())

    with watcher:
        assert watcher.settings.debug is False

        # Modify the file
        yaml_file.write_text("debug: true\nhttp_timeout: 99\n")

        # Wait for reload (with generous timeout for CI)
        assert reloaded.wait(timeout=5.0), "Settings were not reloaded within timeout"

        assert watcher.settings.debug is True
        assert watcher.settings.http_timeout == 99


def test_build_watched_json_reload(tmp_path: Path) -> None:
    json_file = tmp_path / "settings.json"
    json_file.write_text('{"debug": false, "http_timeout": 45}')

    watcher = (
        ConfigurationBuilder(SimpleSettings)
        .add_json_file(json_file.as_posix(), reload_on_change=True)
        .build_watched(debounce_seconds=0.1)
    )

    reloaded = threading.Event()
    watcher.on_change(lambda _s: reloaded.set())

    with watcher:
        json_file.write_text('{"debug": true, "http_timeout": 12}')
        assert reloaded.wait(timeout=5.0)

        assert watcher.settings.debug is True
        assert watcher.settings.http_timeout == 12


def test_build_watched_callback_receives_new_settings(tmp_path: Path) -> None:
    yaml_file = tmp_path / "settings.yaml"
    yaml_file.write_text("debug: false\n")

    watcher = (
        ConfigurationBuilder(SimpleSettings)
        .add_yaml_file(yaml_file.as_posix(), reload_on_change=True)
        .build_watched(debounce_seconds=0.1)
    )

    received: list[SimpleSettings] = []
    done = threading.Event()

    def cb(s: SimpleSettings) -> None:
        received.append(s)
        done.set()

    watcher.on_change(cb)

    with watcher:
        yaml_file.write_text("debug: true\n")
        assert done.wait(timeout=5.0)

    assert len(received) >= 1
    assert received[-1].debug is True


def test_build_watched_without_reload_on_change(tmp_path: Path) -> None:
    """build_watched with no reload_on_change sources still works (no watching)."""
    yaml_file = tmp_path / "settings.yaml"
    yaml_file.write_text("debug: true\n")

    watcher = (
        ConfigurationBuilder(SimpleSettings)
        .add_yaml_file(yaml_file.as_posix())  # reload_on_change defaults to False
        .build_watched()
    )

    assert watcher.settings.debug is True
    # stop should be a no-op
    watcher.stop()


def test_build_watched_context_manager(tmp_path: Path) -> None:
    yaml_file = tmp_path / "settings.yaml"
    yaml_file.write_text("debug: false\n")

    watcher = (
        ConfigurationBuilder(SimpleSettings)
        .add_yaml_file(yaml_file.as_posix(), reload_on_change=True)
        .build_watched()
    )

    with watcher as w:
        assert w.settings.debug is False

    # After exiting, the observer should be stopped
    assert watcher._observer is None


def test_custom_source_integration() -> None:
    """A custom source (protocol-based) can be plugged in via add_source."""

    @dataclass
    class FakeVaultSource:
        secrets: dict[str, Any] = field(default_factory=dict)

        def load(self) -> Mapping[str, Any]:
            return self.secrets

    source = FakeVaultSource(secrets={"debug": True, "http_timeout": 99})

    settings = (
        ConfigurationBuilder(SimpleSettings)
        .add_in_memory_collection({"debug": False})
        .add_source(source)
        .build()
    )

    assert settings.debug is True
    assert settings.http_timeout == 99


def test_build_watched_with_polling_reloads_custom_source(tmp_path: Path) -> None:
    """polling_interval_seconds triggers periodic rebuilds for custom sources."""
    call_count = 0

    @dataclass
    class RotatingSource:
        def load(self) -> Mapping[str, Any]:
            nonlocal call_count
            call_count += 1
            return {"http_timeout": call_count * 10}

    yaml_file = tmp_path / "settings.yaml"
    yaml_file.write_text("debug: false\n")

    watcher = (
        ConfigurationBuilder(SimpleSettings)
        .add_yaml_file(yaml_file.as_posix())
        .add_source(RotatingSource())
        .build_watched(polling_interval_seconds=0.2)
    )

    reloaded = threading.Event()
    watcher.on_change(lambda _s: reloaded.set())

    # Initial build already called load once
    initial_timeout = watcher.settings.http_timeout
    assert initial_timeout == 10

    with watcher:
        # Wait for at least one polling cycle
        assert reloaded.wait(timeout=5.0), "Polling did not trigger a reload"
        # After polling, the value should have been updated
        assert watcher.settings.http_timeout > initial_timeout


