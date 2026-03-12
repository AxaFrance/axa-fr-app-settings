# axa-fr-app-settings

[![PyPI version](https://img.shields.io/pypi/v/axa-fr-app-settings)](https://pypi.org/project/axa-fr-app-settings/)
[![Python versions](https://img.shields.io/pypi/pyversions/axa-fr-app-settings)](https://pypi.org/project/axa-fr-app-settings/)
[![License](https://img.shields.io/pypi/l/axa-fr-app-settings)](https://pypi.org/project/axa-fr-app-settings/)
[![Typing](https://img.shields.io/pypi/types/axa-fr-app-settings)](https://pypi.org/project/axa-fr-app-settings/)

A Python 3.10+ package designed for `uv` that provides a **typed**, **chainable**, **.NET-like** configuration builder.

The idea is to be able to write:

```python
import os

from axa_fr_app_settings import ConfigurationBuilder, SettingsModel

class ApiSettings(SettingsModel):
    debug: bool = False
    http_timeout: int = 45

environment = os.getenv("PYTHON_ENVIRONMENT", "development")

settings = (
    ConfigurationBuilder(ApiSettings)
    .add_yaml_file("settings.yaml", optional=True)
    .add_yaml_file(f"settings.{environment}.yaml", optional=True)
    .add_json_file("settings.json", optional=True)
    .add_json_file(f"settings.{environment}.json", optional=True)
    .add_environment_variables(prefix="", nested_delimiter="__")
    .build()
)
```

## What the package provides

- Fluent API à la `.NET ConfigurationBuilder`
- YAML as the default source
- Override by order of source addition
- Environment variable support with `__` for nested keys
- `.env` file support
- Typed validation with Pydantic v2
- Compatible with `dict[str, SubModel]`, lists, booleans, integers, etc.
- Direct path access with `config["section:key"]`
- Typed subsections with `.get_section("...").get(MyModel)`

## Installation

With `uv`:

```bash
uv add axa-fr-app-settings
```

Locally for contributing:

```bash
uv sync --dev
```

## Usage

### 1. Define typed models

```python
from pydantic import Field

from axa_fr_app_settings import SettingsModel


class EndpointSettings(SettingsModel):
    name: str
    url: str


class RegionSettings(SettingsModel):
    name: str
    endpoints: list[EndpointSettings] = Field(default_factory=list)


class OIDCSettings(SettingsModel):
    endpoint_url: str
    issuer: str
    client_id: str
    client_secret: str | None = None
    private_key: str | None = None
    scopes: str


class DatabaseSettings(SettingsModel):
    endpoint_url: str


class CacheRedisSettings(SettingsModel):
    master: str = "mymaster"
    sentinels: str = "redis-ha:26379"
    expiry_time: int = 60


class CacheSettings(SettingsModel):
    type: str = "redis"
    redis: CacheRedisSettings = Field(default_factory=CacheRedisSettings)


class AppSettings(SettingsModel):
    database: dict[str, DatabaseSettings] = Field(default_factory=dict)
    llm_oidc: dict[str, OIDCSettings] = Field(default_factory=dict)
    debug: bool = False
    http_timeout: int = 45
    http_verify: bool = False
    cache: CacheSettings = Field(default_factory=CacheSettings)
    allowed_hosts: list[str] = Field(default_factory=list)
    regions: list[RegionSettings] = Field(default_factory=list)
```

### 2. Build the configuration

```python
import os

from axa_fr_app_settings import ConfigurationBuilder

environment = os.getenv("PYTHON_ENVIRONMENT", "development")

settings = (
    ConfigurationBuilder(AppSettings)
    .add_yaml_file("settings.yaml", optional=True)
    .add_yaml_file(f"settings.{environment}.yaml", optional=True)
    .add_json_file("settings.json", optional=True)
    .add_json_file(f"settings.{environment}.json", optional=True)
    .add_env_file(".env", optional=True)
    .add_environment_variables(prefix="", nested_delimiter="__")
    .build()
)
```

### 3. Environment variable examples

```bash
export DEBUG=true
export HTTP_TIMEOUT=30
export CACHE__REDIS__EXPIRY_TIME=120
export DATABASE__main__ENDPOINT_URL="postgresql://localhost:5432/app"
export ALLOWED_HOSTS__0="api.local"
export ALLOWED_HOSTS__1="admin.local"
export REGIONS__0__NAME="eu-west"
export REGIONS__0__ENDPOINTS__0__NAME="catalog"
export REGIONS__0__ENDPOINTS__0__URL="https://eu-west/catalog"
export REGIONS__0__ENDPOINTS__1__NAME="orders"
export REGIONS__0__ENDPOINTS__1__URL="https://eu-west/orders"
export REGIONS__1__NAME="us-east"
export REGIONS__1__ENDPOINTS__0__NAME="catalog"
export REGIONS__1__ENDPOINTS__0__URL="https://us-east/catalog"
```

### 4. YAML example

```yaml
debug: false
http_timeout: 45
allowed_hosts:
  - api.local
  - admin.local

database:
  main:
    endpoint_url: "postgresql://localhost:5432/app"

regions:
  - name: eu-west
    endpoints:
      - name: catalog
        url: "https://eu-west/catalog"
      - name: orders
        url: "https://eu-west/orders"
  - name: us-east
    endpoints:
      - name: catalog
        url: "https://us-east/catalog"

cache:
  type: redis
  redis:
    master: mymaster
    sentinels: redis-ha:26379
    expiry_time: 60
```

### 5. JSON example

```json
{
  "debug": false,
  "http_timeout": 45,
  "allowed_hosts": ["api.local", "admin.local"],
  "database": {
    "main": {
      "endpoint_url": "postgresql://localhost:5432/app"
    }
  },
  "regions": [
    {
      "name": "eu-west",
      "endpoints": [
        {
          "name": "catalog",
          "url": "https://eu-west/catalog"
        },
        {
          "name": "orders",
          "url": "https://eu-west/orders"
        }
      ]
    },
    {
      "name": "us-east",
      "endpoints": [
        {
          "name": "catalog",
          "url": "https://us-east/catalog"
        }
      ]
    }
  ],
  "cache": {
    "type": "redis",
    "redis": {
      "master": "mymaster",
      "sentinels": "redis-ha:26379",
      "expiry_time": 60
    }
  }
}
```

YAML and JSON sources can be mixed freely. The last source added always wins.

## Arrays and nested arrays

Arrays are supported in file sources (`yaml`, `json`) and also in flat sources
like environment variables and `.env` files.

### Simple array

```yaml
allowed_hosts:
  - api.local
  - admin.local
```

### Nested array with `regions`

```yaml
regions:
  - name: eu-west
    endpoints:
      - name: catalog
        url: https://eu-west/catalog
      - name: orders
        url: https://eu-west/orders
  - name: us-east
    endpoints:
      - name: catalog
        url: https://us-east/catalog
```

Equivalent environment variables:

```bash
export REGIONS__0__NAME="eu-west"
export REGIONS__0__ENDPOINTS__0__NAME="catalog"
export REGIONS__0__ENDPOINTS__0__URL="https://eu-west/catalog"
export REGIONS__0__ENDPOINTS__1__NAME="orders"
export REGIONS__0__ENDPOINTS__1__URL="https://eu-west/orders"
export REGIONS__1__NAME="us-east"
export REGIONS__1__ENDPOINTS__0__NAME="catalog"
export REGIONS__1__ENDPOINTS__0__URL="https://us-east/catalog"
```

## Priority order

As in .NET, **the last source added wins**.

Example:

```python
settings = (
    ConfigurationBuilder(AppSettings)
    .add_yaml_file("settings.yaml", optional=True)
    .add_yaml_file("settings.production.yaml", optional=True)
    .add_environment_variables()
    .build()
)
```

Here:
1. `settings.yaml` loads the base values
2. `settings.production.yaml` overrides them
3. environment variables override everything

## Available API

| Method | Description |
|---|---|
| `add_yaml_file(path, *, optional=False, encoding="utf-8", reload_on_change=False)` | Add a YAML file source |
| `add_json_file(path, *, optional=False, encoding="utf-8", reload_on_change=False)` | Add a JSON file source |
| `add_env_file(path=".env", *, optional=False, prefix="", nested_delimiter="__", case_sensitive=False, parse_values=True, reload_on_change=False)` | Add a `.env` file source |
| `add_environment_variables(*, prefix="", nested_delimiter="__", case_sensitive=False, parse_values=True)` | Add environment variables |
| `add_in_memory_collection(data)` | Add an in-memory dict |
| `add_source(source)` | Add a custom source (any object with a `load()` method) |
| `build()` | Build and return the validated settings model |
| `build_data()` | Build and return the raw merged dict |
| `build_configuration()` | Build and return a navigable configuration root |
| `build_watched(*, debounce_seconds=0.3, polling_interval_seconds=None)` | Build and return a `SettingsWatcher` with auto-reload |

**Key parameters:**

| Parameter | Default | Description |
|---|---|---|
| `optional` | `False` | When `True`, the source is silently skipped if the file does not exist. When `False` (default), a `FileNotFoundError` is raised. |
| `reload_on_change` | `False` | When `True`, the file is watched for changes and the configuration is automatically rebuilt when modified (requires `watchdog`, see below). When `False` (default), the file is read once at build time. |
| `polling_interval_seconds` | `None` | When set to a number of seconds, `build_watched()` will **periodically rebuild** the whole configuration at that interval. Useful for non-file sources (Key Vault, databases…) that cannot be watched with `watchdog`. `None` (default) disables polling. |

## reloadOnChange – Auto-reload on file change

Like .NET's `reloadOnChange: true`, you can watch configuration files for changes and automatically rebuild the settings.

### Installation

The file-watching feature requires the `watchdog` package (optional dependency):

```bash
uv add axa-fr-app-settings[watch]
```

### Usage

```python
import os

from axa_fr_app_settings import ConfigurationBuilder

environment = os.getenv("PYTHON_ENVIRONMENT", "development")

watcher = (
    ConfigurationBuilder(AppSettings)
    .add_yaml_file("settings.yaml", optional=True, reload_on_change=True)
    .add_yaml_file(f"settings.{environment}.yaml", optional=True, reload_on_change=True)
    .add_json_file("settings.json", optional=True, reload_on_change=True)
    .add_environment_variables(prefix="", nested_delimiter="__")
    .build_watched()              # ← returns a SettingsWatcher instead of a model
)

# Register a callback (like IOptionsMonitor.OnChange in .NET)
watcher.on_change(lambda s: print(f"Settings reloaded! debug={s.debug}"))

# Access the latest settings at any time (thread-safe)
print(watcher.settings.debug)

# Use as a context manager (starts/stops the file watcher)
with watcher:
    ...  # watcher.settings is always up-to-date

# Or start/stop manually
watcher.start()
# ...
watcher.stop()
```

A complete example is available in [`examples/reload_on_change_example.py`](examples/reload_on_change_example.py).

## Custom Source / Provider (e.g. Azure Key Vault)

Like .NET's `IConfigurationSource` / `IConfigurationProvider`, you can create your own configuration source and plug it into the builder via `add_source()`.

Any object that implements a `load() -> Mapping[str, Any]` method satisfies the `SettingsSource` protocol:

```python
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient


@dataclass
class KeyVaultSource:
    """Fetches secrets from Azure Key Vault and maps them to config keys."""

    vault_url: str
    secret_mapping: dict[str, str] = field(default_factory=dict)

    def load(self) -> Mapping[str, Any]:
        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=self.vault_url, credential=credential)

        result: dict[str, Any] = {}
        for secret_name, config_key in self.secret_mapping.items():
            secret = client.get_secret(secret_name)
            if secret.value is None:
                continue
            # Convert "database__main__password" → nested dict
            parts = config_key.split("__")
            current = result
            for part in parts[:-1]:
                current = current.setdefault(part, {})
            current[parts[-1]] = secret.value

        return result
```

### Static build (one-shot)

```python
settings = (
    ConfigurationBuilder(AppSettings)
    .add_yaml_file("settings.yaml", optional=True)
    .add_source(
        KeyVaultSource(
            vault_url="https://my-vault.vault.azure.net/",
            secret_mapping={
                "db-password": "database__main__password",
                "api-key": "secret_api_key",
            },
        )
    )
    .add_environment_variables(prefix="", nested_delimiter="__")
    .build()
)
```

### With watcher – periodic secret refresh (polling)

Since a Key Vault is not a file, `reload_on_change` cannot watch it.
Instead, use `polling_interval_seconds` to rebuild the configuration at a
regular interval.  File sources with `reload_on_change=True` are still
watched instantly; the two mechanisms work together:

```python
keyvault = KeyVaultSource(
    vault_url="https://my-vault.vault.azure.net/",
    secret_mapping={
        "db-password": "database__main__password",
        "api-key": "secret_api_key",
    },
)

watcher = (
    ConfigurationBuilder(AppSettings)
    .add_yaml_file("settings.yaml", optional=True, reload_on_change=True)
    .add_source(keyvault)
    .add_environment_variables(prefix="", nested_delimiter="__")
    .build_watched(
        polling_interval_seconds=300,  # re-fetch secrets every 5 min
    )
)

watcher.on_change(lambda s: print("Secrets refreshed!", s.secret_api_key))

with watcher:
    ...  # watcher.settings always holds the latest values
```

The Key Vault source (or any custom source) follows the same priority rule: **the last source added wins**.

A complete example is available in [`examples/custom_keyvault_source.py`](examples/custom_keyvault_source.py).

## Direct key access and typed sections

Like in .NET, you can also work with the raw merged configuration tree.
This is useful when you want direct path access or when you only want to bind
one subsection.

```python
from pydantic import Field

from axa_fr_app_settings import ConfigurationBuilder, SettingsModel


class EndpointSettings(SettingsModel):
    name: str
    url: str


class RegionSettings(SettingsModel):
    name: str
    endpoints: list[EndpointSettings] = Field(default_factory=list)


class AppSettings(SettingsModel):
    application_name: str
    max_users: int
    feature_toggle: bool = False
    allowed_hosts: list[str] = Field(default_factory=list)
    regions: list[RegionSettings] = Field(default_factory=list)


class RootSettings(SettingsModel):
    appsettings: AppSettings


config = (
    ConfigurationBuilder(RootSettings)
    .add_json_file("appsettings.json")
    .build_configuration()
)

app_name = config["appsettings:application_name"]
max_users = config["appsettings:max_users"]
first_region = config["appsettings:regions:0:name"]
first_endpoint_url = config["appsettings:regions:0:endpoints:0:url"]

app_settings = config.get_section("appsettings").get(AppSettings)
print(f"FeatureToggle: {app_settings.feature_toggle}")
print(f"Application Name: {app_settings.application_name}")
print(f"Max Users: {app_settings.max_users}")
print(f"First Region: {first_region}")
print(f"First Endpoint URL: {first_endpoint_url}")
```

You can also bind the full root model directly:

```python
root_settings = config.bind()
```

For environment variables or `.env` files, use numeric indexes with `__`:

```bash
export APPSETTINGS__ALLOWED_HOSTS__0=api.local
export APPSETTINGS__ALLOWED_HOSTS__1=admin.local
export APPSETTINGS__REGIONS__0__NAME="eu-west"
export APPSETTINGS__REGIONS__0__ENDPOINTS__0__NAME="catalog"
export APPSETTINGS__REGIONS__0__ENDPOINTS__0__URL="https://eu/catalog"
```

A complete runnable example is available in [`examples/configuration_sections.py`](examples/configuration_sections.py).

## Full example

Complete examples are provided in:

- [`examples/api_settings.py`](examples/api_settings.py)
- [`examples/configuration_sections.py`](examples/configuration_sections.py)

## Publishing to PyPI with GitHub Actions

The repository includes two workflows:

| Workflow | File | Trigger |
|---|---|---|
| CI | `.github/workflows/ci.yml` | push / PR on `main` |
| Publish | `.github/workflows/publish.yml` | every merge (push) on `main` |

The publish workflow automatically:
1. Runs lint + tests
2. Builds the wheel and sdist with `uv build`
3. Publishes to PyPI with `uv publish`

### Setup

Add a **`PYPI_API_TOKEN`** secret in your GitHub repository settings:
> **Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value |
|---|---|
| `PYPI_API_TOKEN` | Your PyPI API token (starts with `pypi-`) |

That's it — every merge to `main` will publish a new version automatically.

## Development

```bash
uv sync --dev
uv run ruff check .
uv run pytest
uv build
```

## License

MIT
