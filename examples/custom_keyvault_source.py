"""
Example: Custom configuration source – Azure Key Vault **with watcher**.

This shows how to create a custom ``SettingsSource`` and plug it into
the ``ConfigurationBuilder`` together with ``build_watched()`` so that
secrets are **periodically refreshed** (polling), while YAML files are
refreshed instantly on change (file-watching).

The ``KeyVaultSource`` below is a *mock*.  Replace the body of
``load()`` with a real call to ``azure.keyvault.secrets`` for production.

Usage::

    uv run python examples/custom_keyvault_source.py
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import Field as PydanticField

from axa_fr_app_settings import ConfigurationBuilder, SettingsModel

# ─── Settings models ─────────────────────────────────────────────────

class DatabaseSettings(SettingsModel):
    endpoint_url: str
    password: str = ""


class AppSettings(SettingsModel):
    debug: bool = False
    http_timeout: int = 45
    database: dict[str, DatabaseSettings] = PydanticField(default_factory=dict)
    secret_api_key: str = ""


# ─── Custom Key Vault source ─────────────────────────────────────────
# Implement the ``SettingsSource`` protocol: any object with a
# ``load() -> Mapping[str, Any]`` method is accepted.

# Internal counter to simulate secret rotation in this demo.
_ROTATION_COUNTER = 0


@dataclass
class KeyVaultSource:
    """
    Fetches secrets from Azure Key Vault (or any secret manager) and
    maps them to configuration keys.

    Parameters
    ----------
    vault_url:
        The URL of the Key Vault, e.g. ``https://my-vault.vault.azure.net/``.
    secret_mapping:
        A dict mapping *secret names* in the vault to flat config keys
        using ``__`` as the nested delimiter.
        Example: ``{"db-password": "database__main__password"}``
    """

    vault_url: str
    secret_mapping: dict[str, str] = field(default_factory=dict)

    def load(self) -> Mapping[str, Any]:
        # ── In production, use the Azure SDK ──────────────────────────
        # from azure.identity import DefaultAzureCredential
        # from azure.keyvault.secrets import SecretClient
        # credential = DefaultAzureCredential()
        # client = SecretClient(vault_url=self.vault_url, credential=credential)

        # For this demo we simulate secret rotation:
        global _ROTATION_COUNTER  # noqa: PLW0603
        _ROTATION_COUNTER += 1
        fake_vault: dict[str, str] = {
            "db-password": f"sup3r-s3cret-v{_ROTATION_COUNTER}",
            "api-key": f"ak-12345-ABCDE-v{_ROTATION_COUNTER}",
        }

        result: dict[str, Any] = {}
        for secret_name, config_key in self.secret_mapping.items():
            value = fake_vault.get(secret_name)
            if value is None:
                continue

            # Convert flat key (e.g. "database__main__password") into a
            # nested dict structure.
            parts = config_key.split("__")
            current = result
            for part in parts[:-1]:
                current = current.setdefault(part, {})
            current[parts[-1]] = value

        return result


# ─── Wire everything together ────────────────────────────────────────

def main() -> None:
    keyvault = KeyVaultSource(
        vault_url="https://my-vault.vault.azure.net/",
        secret_mapping={
            "db-password": "database__main__password",
            "api-key": "secret_api_key",
        },
    )

    watcher = (
        ConfigurationBuilder(AppSettings)
        # 1. Base file – reload instantly on change
        .add_yaml_file("examples/settings.yaml", optional=True, reload_on_change=True)
        # 2. Secrets from Key Vault – refreshed every 5 s via polling
        .add_source(keyvault)
        # 3. Environment variables override everything
        .add_environment_variables(prefix="", nested_delimiter="__")
        .build_watched(
            polling_interval_seconds=5.0,   # ← poll every 5 s
        )
    )

    # Subscribe to changes
    watcher.on_change(
        lambda s: print(
            f"\n\U0001f504 Settings reloaded!"
            f"\n   secret_api_key = {s.secret_api_key}"
            f"\n   database.main.password = "
            f"{s.database['main'].password if 'main' in s.database else 'N/A'}"
        )
    )

    print("Initial settings:")
    print(f"  secret_api_key       = {watcher.settings.secret_api_key}")
    if "main" in watcher.settings.database:
        print(f"  database.main.password = {watcher.settings.database['main'].password}")
    print()
    print("\U0001f449 The Key Vault source is polled every 5 s (simulated rotation).")
    print("   You can also edit examples/settings.yaml for an instant reload.")
    print("   Press Ctrl+C to stop.\n")

    with watcher:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()

