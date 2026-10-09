"""Three-input brake model with a longitudinal friction limit."""

FRONT_BRAKE_BIAS = 0.7
REAR_BRAKE_BIAS = 0.3



def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def brake_force_components(
    brake_pressure_front: float,
    brake_pressure_rear: float,
    brake_pedal_travel: float,
) -> tuple[float, float]:
    pedal = _clamp01(brake_pedal_travel)
    front = _clamp01(brake_pressure_front) * pedal
    rear = _clamp01(brake_pressure_rear) * pedal
    return front, rear


def braking_force(
    brake_pressure_front: float,
    brake_pressure_rear: float,
    brake_pedal_travel: float,
    max_braking_capacity: float,
    max_grip: float,
) -> float:
    front, rear = brake_force_components(
        brake_pressure_front, brake_pressure_rear, brake_pedal_travel
    )
    raw = max_braking_capacity * (FRONT_BRAKE_BIAS * front + REAR_BRAKE_BIAS * rear)
    # Longitudinal traction limit.
    return min(max(0.0, raw), max(0.0, max_grip))
