"""
Example: reload_on_change – automatic configuration reload.

Like .NET's ``reloadOnChange: true``, the configuration is automatically
rebuilt whenever a watched file changes on disk.

Run this example, then edit ``examples/settings.yaml`` in another terminal
and watch the output update.

    uv run python examples/reload_on_change_example.py
"""

from __future__ import annotations

import os
import time

from pydantic import Field

from axa_fr_app_settings import ConfigurationBuilder, SettingsModel

# ── Models ────────────────────────────────────────────────────────────

class CacheRedisSettings(SettingsModel):
    master: str = "mymaster"
    sentinels: str = "redis-ha:26379"
    expiry_time: int = 60


class CacheSettings(SettingsModel):
    type: str = "redis"
    redis: CacheRedisSettings = Field(default_factory=CacheRedisSettings)


class DatabaseSettings(SettingsModel):
    endpoint_url: str


class AppSettings(SettingsModel):
    debug: bool = False
    http_timeout: int = 45
    database: dict[str, DatabaseSettings] = Field(default_factory=dict)
    cache: CacheSettings = Field(default_factory=CacheSettings)


# ── Build with reload_on_change ──────────────────────────────────────

def main() -> None:
    environment = os.getenv("PYTHON_ENVIRONMENT", "development")

    watcher = (
        ConfigurationBuilder(AppSettings)
        .add_yaml_file("examples/settings.yaml", optional=True, reload_on_change=True)
        .add_yaml_file(
            f"examples/settings.{environment}.yaml",
            optional=True,
            reload_on_change=True,
        )
        .add_json_file("examples/settings.json", optional=True, reload_on_change=True)
        .add_environment_variables(prefix="", nested_delimiter="__")
        .build_watched()
    )

    # Register a callback (just like IOptionsMonitor.OnChange in .NET)
    watcher.on_change(
        lambda s: print(
            f"\n\U0001f504 Settings reloaded!\n"
            f"   debug={s.debug}  http_timeout={s.http_timeout}"
        )
    )

    print("Initial settings:", watcher.settings.model_dump())
    print("\n\U0001f449 Edit examples/settings.yaml and save "
          "- the config will reload automatically.")
    print("   Press Ctrl+C to stop.\n")

    with watcher:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()

