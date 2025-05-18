"""DataUpdateCoordinator for Pool Math"""
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .client import PoolMathClient
from .models import PoolMathState, PoolMathConfig

LOG = logging.getLogger(__name__)

class PoolMathUpdateCoordinator(DataUpdateCoordinator[PoolMathState]):
    """
    Coordinator that HA uses to periodically fetch Pool Math data and
    update associated sensors/entities from the JSON response.
    """
    def __init__(
        self,
        hass: HomeAssistant,
        client: PoolMathClient,
        config: PoolMathConfig,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOG,
            name=DOMAIN,
            update_interval=config.update_interval
        )
        self._client = client
        self._config = config

    async def _async_update_data(self) -> PoolMathState:
        """
        Called periodically by DataUpdateCoordinator to trigger
        an asynchronous update of data from Pool Math service.
        """
        try:
            json = await self._client.async_get_json()

            # returning state triggers HA to call _handle_coordinator_update() 
            # callbacks on all associated entities
            return PoolMathState(json=json,
                                 last_updated=json.get('last_updated'))
        except Exception as e:
            LOG.exception(e)
            raise UpdateFailed(e) from e
