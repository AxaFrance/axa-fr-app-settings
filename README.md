# axa-fr-app-settings

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
```

### 4. YAML example

```yaml
debug: false
http_timeout: 45

database:
  main:
    endpoint_url: "postgresql://localhost:5432/app"

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
  "database": {
    "main": {
      "endpoint_url": "postgresql://localhost:5432/app"
    }
  },
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

- `add_yaml_file(path, optional=False, encoding="utf-8")`
- `add_json_file(path, optional=False, encoding="utf-8")`
- `add_env_file(path=".env", optional=False, prefix="", nested_delimiter="__", case_sensitive=False)`
- `add_environment_variables(prefix="", nested_delimiter="__", case_sensitive=False)`
- `add_in_memory_collection(data)`
- `add_source(source)`
- `build()`
- `build_data()`

## Full example

A complete example is provided in [`examples/api_settings.py`](examples/api_settings.py).

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
