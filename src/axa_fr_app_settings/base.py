from pydantic import BaseModel, ConfigDict


class SettingsModel(BaseModel):
    """
    Base pratique pour les modèles de configuration.

    - ignore les clés inconnues par défaut
    - retire les espaces parasites dans les chaînes
    """

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        validate_assignment=True,
    )
