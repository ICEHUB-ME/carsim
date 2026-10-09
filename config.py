"""Immutable configuration objects for vehicle, controls, simulation, and rendering."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CarParameters:
    """Physical constants and limits used by the vehicle model."""

    mass: float = 300.0
    gravity: float = 9.81
    max_motor_torque: float = 180.0
    gear_ratio: float = 3.0
    wheel_radius: float = 0.216
    cornering_stiffness: float = 36_000.0
    friction_coefficient: float = 1.0
    frontal_area: float = 1.2
    drag_coefficient: float = 0.7
    air_density: float = 1.2
    max_propulsion_force: float = 2_000.0
    vmax: float = 27.0
    max_braking_capacity: float = 1_850.0
    rolling_resistance_coefficient: float = 0.015
    max_steering_angle_deg: float = 30.0
    slip_speed_epsilon: float = 1e-3
    sim_dt: float = 0.01

    @property
    def normal_force(self) -> float:
        """Return static normal force on a level surface, in newtons."""
        return self.mass * self.gravity

    @property
    def max_grip(self) -> float:
        """Return the friction-limited tire force, in newtons."""
        return self.friction_coefficient * self.normal_force


@dataclass(frozen=True)
class ControlConfig:
    """Rates that limit keyboard control changes per second."""

    throttle_rate: float = 2.0
    brake_rate: float = 2.0
    steering_rate_deg: float = 90.0


@dataclass(frozen=True)
class SimulationConfig:
    """Timing limits for fixed-step and real-time simulation."""

    time_step: float = 0.01
    accumulator_limit: float = 0.25


@dataclass(frozen=True)
class PlotConfig:
    """Scale and retained history for the bird's-eye view."""

    pixels_per_meter: float = 10.0
    grid_spacing_m: float = 10.0
    path_max_points: int = 10_000


@dataclass(frozen=True)
class GameConfig:
    """Backward-compatible bundle used by existing renderer integrations."""

    throttle_rate: float = 2.0
    brake_rate: float = 2.0
    steering_rate_deg: float = 90.0
    path_max_points: int = 10_000
    physics_accumulator_limit: float = 0.25
    pixels_per_meter: float = 1.0
    grid_spacing_m: float = 10.0

    @property
    def controls(self) -> ControlConfig:
        return ControlConfig(
            throttle_rate=self.throttle_rate,
            brake_rate=self.brake_rate,
            steering_rate_deg=self.steering_rate_deg,
        )

    @property
    def simulation(self) -> SimulationConfig:
        return SimulationConfig(accumulator_limit=self.physics_accumulator_limit)

    @property
    def plot(self) -> PlotConfig:
        return PlotConfig(
            pixels_per_meter=self.pixels_per_meter,
            grid_spacing_m=self.grid_spacing_m,
            path_max_points=self.path_max_points,
        )


# Preserve the original public import while new code uses the clearer name.
CarParams = CarParameters
GameParams = GameConfig
