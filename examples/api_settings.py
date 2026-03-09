from __future__ import annotations

import os

from pydantic import Field

from axa_fr_app_settings import ConfigurationBuilder, SettingsModel


class OIDCSettings(SettingsModel):
    endpoint_url: str
    issuer: str
    client_id: str
    client_secret: str | None = None
    private_key: str | None = None
    scopes: str


class OpenTelemetrySettings(SettingsModel):
    enable_otel: bool = False
    otel_excluded_urls: str = "/health,/metrics,/openapi_json,/version"


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
    db_connection_url: str = ""
    db_password: str = ""
    cache: CacheSettings = Field(default_factory=CacheSettings)
    open_telemetry_settings: OpenTelemetrySettings = Field(default_factory=OpenTelemetrySettings)


class ApiSettings(AppSettings):
    allow_origin: str = ""
    server_host: str = ""
    server_port: int = 5000
    server_ssl: bool = False
    oidc_issuer: str = ""
    oidc_enable: bool = True
    oidc_client_ids_dpop_mandatory: str = ""
    https_proxy: bool = True
    log_level: str = "INFO"


def load_settings(settings_dir: str) -> ApiSettings:
    environment = os.getenv("PYTHON_ENVIRONMENT", "development")

    return (
        ConfigurationBuilder(ApiSettings)
        .add_yaml_file(f"{settings_dir}/settings.yaml", optional=True)
        .add_yaml_file(f"{settings_dir}/settings.{environment}.yaml", optional=True)
        .add_json_file(f"{settings_dir}/settings.json", optional=True)
        .add_json_file(f"{settings_dir}/settings.{environment}.json", optional=True)
        .add_env_file(f"{settings_dir}/.env", optional=True)
        .add_environment_variables(prefix="", nested_delimiter="__")
        .build()
    )


if __name__ == "__main__":
    settings = load_settings("./examples")
    print(settings.model_dump())



