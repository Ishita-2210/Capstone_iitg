"""Deterministic version of the notebook's historical Pathway pricing rule.

No Pathway or pandas dependency is required to validate and price an observation.
"""

from dataclasses import dataclass
from datetime import datetime
from math import isfinite


def _finite(name: str, value: float) -> None:
    if not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{name} must be a finite number")


@dataclass(frozen=True)
class PricingConfig:
    """Fixed feature scales avoid using future observations for normalization."""

    queue_scale: float = 10.0
    traffic_scale: float = 5.0
    base_price: float = 10.0
    min_multiplier: float = 0.5
    max_multiplier: float = 2.0

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            _finite(name, value)
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.min_multiplier > self.max_multiplier:
            raise ValueError("min_multiplier must not exceed max_multiplier")
        for bound in (self.min_multiplier, self.max_multiplier):
            if not 0 < self.base_price * bound < float("inf"):
                raise ValueError("configured price bounds must be finite and positive")


def checked_lot_id(lot_id: str) -> str:
    if not isinstance(lot_id, str) or not lot_id.strip():
        raise ValueError("SystemCodeNumber must be a nonempty lot identifier")
    return lot_id.strip()


def observation_timestamp(date: str, time: str) -> str:
    """Parse the original day-first source fields; no timezone is inferred."""
    try:
        return datetime.strptime(f"{date} {time}", "%d-%m-%Y %H:%M:%S").isoformat()
    except ValueError as error:
        raise ValueError("Expected LastUpdatedDate DD-MM-YYYY and LastUpdatedTime HH:MM:SS") from error


def calculate_demand(
    occupancy: float,
    capacity: float,
    queue_length: float,
    traffic: float,
    special_day: float,
    vehicle_type: str,
    config: PricingConfig,
) -> float:
    """Apply the historical streaming coefficients to one validated observation.

    Queue and traffic saturate at their configured scales. The notebook's bike
    weight is 0.8 in this model (its separate pandas experiment uses 0.5).
    """
    for name, value in (
        ("Occupancy", occupancy),
        ("Capacity", capacity),
        ("QueueLength", queue_length),
        ("TrafficConditionNearby", traffic),
        ("IsSpecialDay", special_day),
    ):
        _finite(name, value)
    if capacity <= 0:
        raise ValueError("Capacity must be positive")
    if not 0 <= occupancy <= capacity:
        raise ValueError("Occupancy must be between zero and Capacity")
    if queue_length < 0 or traffic < 0:
        raise ValueError("QueueLength and TrafficConditionNearby must be nonnegative")
    if special_day not in (0, 1):
        raise ValueError("IsSpecialDay must be 0 or 1")
    if not isinstance(vehicle_type, str) or not vehicle_type.strip():
        raise ValueError("VehicleType must be a nonempty string")

    vehicle_weight = {"car": 1.0, "bike": 0.8, "truck": 1.5}.get(
        vehicle_type.strip().lower(), 1.0
    )
    return (
        occupancy / capacity
        + 0.7 * min(queue_length / config.queue_scale, 1.0)
        - 0.4 * min(traffic / config.traffic_scale, 1.0)
        + 0.6 * special_day
        + 0.3 * vehicle_weight
    )


def calculate_price(demand: float, config: PricingConfig) -> float:
    """Bound the notebook's base * (1 + 0.4 * demand) rule."""
    _finite("demand", demand)
    return min(
        config.base_price * config.max_multiplier,
        max(config.base_price * config.min_multiplier, config.base_price * (1 + 0.4 * demand)),
    )
