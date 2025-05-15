from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class PoolMathConfig:
    """Configuration data for Pool Math integration."""
    user_id: str
    pool_id: str
    name: str
    timeout: int
    target: str
    update_interval: timedelta = timedelta(minutes=8)

@dataclass
class PoolMathState:
    """State data for Pool Math service."""
    last_updated: Optional[str] = None
    attributes: Dict[str, Any] = None
