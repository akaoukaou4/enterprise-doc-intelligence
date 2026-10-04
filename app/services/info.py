from app.core.config import Settings
from app.schemas.info import InfoResponse


class InfoService:
    """Example application service: holds the logic, knows nothing about HTTP."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_info(self) -> InfoResponse:
        return InfoResponse(
            name=self._settings.app_name,
            version=self._settings.app_version,
            environment=self._settings.app_env,
        )
