"""Simple constant rolling resistance on a flat road."""


def rolling_resistance_force(
    rolling_resistance_coefficient: float,
    normal_force_n: float,
    speed_mps: float,
) -> float:
    # Do not create a backward force while the car is already stationary.
    if speed_mps <= 0.0:
        return 0.0
    return max(0.0, rolling_resistance_coefficient) * normal_force_n
