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


class StrictSettingsModel(SettingsModel):
    """
    Base stricte pour les modèles de configuration.

    Les clés inconnues provoquent une erreur de validation.
    """

    model_config = ConfigDict(extra="forbid")
