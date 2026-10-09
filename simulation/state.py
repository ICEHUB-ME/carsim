"""Typed state objects shared by the vehicle model and simulation runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class DriverInputs:
    """A complete, immutable set of driver commands for one physics step."""

    throttle: float = 0.0
    brake_pressure_front: float = 0.0
    brake_pressure_rear: float = 0.0
    brake_pedal_travel: float = 0.0
    steering_angle_deg: float = 0.0

    def sanitized(self, max_steering_angle_deg: float) -> DriverInputs:
        """Clamp user controls to the ranges accepted by the physics model."""
        return DriverInputs(
            throttle=max(0.0, min(1.0, self.throttle)),
            brake_pressure_front=max(0.0, min(1.0, self.brake_pressure_front)),
            brake_pressure_rear=max(0.0, min(1.0, self.brake_pressure_rear)),
            brake_pedal_travel=max(0.0, min(1.0, self.brake_pedal_travel)),
            steering_angle_deg=max(
                -max_steering_angle_deg,
                min(max_steering_angle_deg, self.steering_angle_deg),
            ),
        )


@dataclass
class CarState:
    """Vehicle state and last-step telemetry, expressed in SI units."""

    time: float = 0.0
    x: float = 0.0
    y: float = 0.0
    heading: float = 0.0
    speed: float = 0.0
    acceleration: float = 0.0
    lateral_velocity: float = 0.0
    lateral_acceleration: float = 0.0
    slip_angle: float = 0.0
    steering_angle: float = 0.0
    throttle: float = 0.0
    brake_pedal: float = 0.0
    brake_pressure_front: float = 0.0
    brake_pressure_rear: float = 0.0
    propulsion_force: float = 0.0
    drag_force: float = 0.0
    rolling_resistance: float = 0.0
    braking_force: float = 0.0
    lateral_force: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        """Return the stable field mapping used by CSV serialization."""
        return asdict(self)