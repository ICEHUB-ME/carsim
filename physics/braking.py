"""Normalized single-input braking model."""


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def driver_braking_force(brake_input: float, max_braking_capacity: float) -> float:
    """Return braking force from normalized pedal input and capacity."""
    return _clamp01(brake_input) * max(0.0, max_braking_capacity)


def braking_force(
    brake_pressure_front: float,
    brake_pressure_rear: float,
    brake_pedal_travel: float,
    max_braking_capacity: float,
    max_grip: float | None = None,
) -> float:
    """Compatibility wrapper for the former multi-input braking API.

    The assignment defines one normalized driver input. The front/rear pressure
    fields and grip argument remain accepted for callers using the old API, but
    do not alter the force calculation.
    """
    del brake_pressure_front, brake_pressure_rear, max_grip
    return driver_braking_force(brake_pedal_travel, max_braking_capacity)
