"""Aerodynamic drag."""


def drag_force(
    speed_mps: float,
    frontal_area_m2: float,
    drag_coefficient: float,
    air_density_kg_m3: float,
) -> float:
    speed_mps = max(0.0, speed_mps)
    return 0.5 * frontal_area_m2 * drag_coefficient * air_density_kg_m3 * speed_mps**2
