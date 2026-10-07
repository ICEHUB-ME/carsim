from dataclasses import dataclass


@dataclass(frozen=True)
class CarParams:
    # Shared physical constants
    mass: float = 300.0
    gravity: float = 9.81

    # Part 1 diagnostic/reference torque model
    max_motor_torque: float = 180.0
    gear_ratio: float = 3.0
    wheel_radius: float = 0.216

    # Part 2 lateral dynamics
    cornering_stiffness: float = 36_000.0
    friction_coefficient: float = 1.0

    # Part 3 drag
    frontal_area: float = 1.2
    drag_coefficient: float = 0.7
    air_density: float = 1.2

    # Part 4 motor/back-EMF model
    max_propulsion_force: float = 2_000.0
    vmax: float = 27.0

    # Part 5/6 braking and rolling resistance
    max_braking_capacity: float = 1_850.0
    rolling_resistance_coefficient: float = 0.015

    # Steering / numerical settings
    max_steering_angle_deg: float = 30.0
    slip_speed_epsilon: float = 1e-3
    sim_dt: float = 0.01

    @property
    def normal_force(self) -> float:
        return self.mass * self.gravity

    @property
    def max_grip(self) -> float:
        return self.friction_coefficient * self.normal_force


@dataclass(frozen=True)
class GameParams:
    throttle_rate: float = 2.0          # normalized units / s
    brake_rate: float = 2.0             # normalized units / s
    steering_rate_deg: float = 90.0     # degrees / s
    path_max_points: int = 10_000
    physics_accumulator_limit: float = 0.25
    pixels_per_meter: float = 10.0
