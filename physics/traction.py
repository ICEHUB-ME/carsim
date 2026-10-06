"""Lateral tire model with a simple friction/grip limit."""

import math


def slip_angle(
    steering_angle_deg: float,
    lateral_velocity_mps: float,
    forward_speed_mps: float,
    epsilon: float = 1e-3,
) -> float:
    forward_speed = max(abs(forward_speed_mps), epsilon)
    return math.radians(steering_angle_deg) - lateral_velocity_mps / forward_speed


def lateral_force(
    slip_angle_rad: float,
    cornering_stiffness_n_per_rad: float,
    max_grip_n: float,
) -> float:
    raw = cornering_stiffness_n_per_rad * slip_angle_rad
    return max(-max_grip_n, min(max_grip_n, raw))


def lateral_acceleration(force_n: float, mass_kg: float) -> float:
    if mass_kg <= 0:
        raise ValueError("mass_kg must be positive")
    return force_n / mass_kg
