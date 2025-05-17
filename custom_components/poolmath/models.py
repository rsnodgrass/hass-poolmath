from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from homeassistant.const import UnitOfTemperature
from .targets import get_known_sensor_target_slugs


@dataclass
class PoolMathConfig:
    """Configuration data for Pool Math integration."""

    user_id: str
    pool_id: str
    name: str = 'Pool'
    timeout: float = 15.0
    target: str = 'tfp'
    update_interval: timedelta = timedelta(minutes=8)
    unit_of_measurement: str = UnitOfTemperature.FAHRENHEIT

    def validate(self) -> None:
        """Validate configuration values.

        Raises:
            ValueError: If required fields are missing or invalid
        """
        if not self.user_id or not self.pool_id:
            raise ValueError('user_id and pool_id are required')
        if self.timeout <= 0:
            raise ValueError('timeout must be positive')
        if self.target not in get_known_sensor_target_slugs():
            raise ValueError(
                f'target must be one of: {", ".join(get_known_sensor_target_slugs())}'
            )
        if self.unit_of_measurement not in [
            UnitOfTemperature.FAHRENHEIT,
            UnitOfTemperature.CELSIUS,
        ]:
            raise ValueError("unit_of_measurement must be 'F' or 'C'")


@dataclass
class PoolMathState:
    """State data for Pool Math service."""

    json: dict[str, Any] = None
    last_updated: str | None = None
