from __future__ import annotations

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
    .add_in_memory_collection(
        {
            "appsettings": {
                "application_name": "AXA Portal",
                "max_users": 150,
                "feature_toggle": True,
                "allowed_hosts": ["api.local", "admin.local"],
                "regions": [
                    {
                        "name": "eu-west",
                        "endpoints": [
                            {"name": "catalog", "url": "https://eu/catalog"},
                            {"name": "orders", "url": "https://eu/orders"},
                        ],
                    },
                    {
                        "name": "us-east",
                        "endpoints": [
                            {"name": "catalog", "url": "https://us/catalog"},
                        ],
                    },
                ],
            }
        }
    )
    .build_configuration()
)

app_name = config["appsettings:application_name"]
max_users = config["appsettings:max_users"]
first_region_name = config["appsettings:regions:0:name"]
first_endpoint_url = config["appsettings:regions:0:endpoints:0:url"]

app_settings = config.get_section("appsettings").get(AppSettings)
root_settings = config.bind()

print(f"Application Name: {app_name}")
print(f"Max Users: {max_users}")
print(f"First Region: {first_region_name}")
print(f"First Endpoint URL: {first_endpoint_url}")
print(f"Allowed Hosts: {app_settings.allowed_hosts}")
print(f"Region count: {len(app_settings.regions)}")
print(f"Root bound application name: {root_settings.appsettings.application_name}")
