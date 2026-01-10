"""Data models for Pool Math integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from homeassistant.const import UnitOfTemperature


@dataclass(frozen=True, slots=True)
class PoolMathConfig:
    """Configuration data for Pool Math integration."""

    user_id: str
    pool_id: str
    name: str = 'Pool'
    timeout: float = 15.0
    target: str = 'tfp'
    update_interval: timedelta = field(default_factory=lambda: timedelta(minutes=8))
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
        if self.target != 'tfp':
            raise ValueError(f"target must be 'tfp', got '{self.target}'")
        if self.unit_of_measurement not in (
            UnitOfTemperature.FAHRENHEIT,
            UnitOfTemperature.CELSIUS,
        ):
            raise ValueError('unit_of_measurement must be F or C')


@dataclass(slots=True)
class PoolMathState:
    """State data for Pool Math service."""

    json: dict[str, Any] | None = None
    last_updated: str | None = None
