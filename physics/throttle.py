"""Part 1: torque-based throttle model kept as a diagnostic/reference."""


def command_torque(throttle: float, max_motor_torque: float) -> float:
    return max(0.0, min(1.0, throttle)) * max_motor_torque


def wheel_force_from_torque(
    command_torque_nm: float,
    gear_ratio: float,
    wheel_radius_m: float,
) -> float:
    if wheel_radius_m <= 0:
        raise ValueError("wheel_radius_m must be positive")
    return command_torque_nm * gear_ratio / wheel_radius_m


def diagnostic_acceleration(
    throttle: float,
    max_motor_torque: float,
    gear_ratio: float,
    wheel_radius_m: float,
    mass_kg: float,
) -> float:
    if mass_kg <= 0:
        raise ValueError("mass_kg must be positive")
    torque = command_torque(throttle, max_motor_torque)
    force = wheel_force_from_torque(torque, gear_ratio, wheel_radius_m)
    return force / mass_kg
