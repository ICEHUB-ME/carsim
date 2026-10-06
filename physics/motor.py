"""Main propulsion model: simple back-EMF-limited force."""


def propulsion_force(
    throttle: float,
    speed_mps: float,
    max_propulsion_force: float,
    vmax_mps: float,
) -> float:
    if vmax_mps <= 0:
        raise ValueError("vmax_mps must be positive")
    throttle = max(0.0, min(1.0, throttle))
    speed_mps = max(0.0, speed_mps)
    speed_factor = max(0.0, 1.0 - speed_mps / vmax_mps)
    return max_propulsion_force * throttle * speed_factor


def motor_acceleration(force_n: float, mass_kg: float) -> float:
    if mass_kg <= 0:
        raise ValueError("mass_kg must be positive")
    return force_n / mass_kg
