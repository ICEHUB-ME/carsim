"""Unified car state and integration pipeline."""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any

from config import CarParams
from physics.braking import braking_force
from physics.drag import drag_force
from physics.motor import propulsion_force
from physics.rolling_resistance import rolling_resistance_force
from physics.traction import lateral_acceleration, lateral_force, slip_angle


@dataclass(frozen=True)
class DriverInputs:
    throttle: float = 0.0
    brake_pressure_front: float = 0.0
    brake_pressure_rear: float = 0.0
    brake_pedal_travel: float = 0.0
    steering_angle_deg: float = 0.0

    def sanitized(self, max_steering_angle_deg: float) -> "DriverInputs":
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
        return asdict(self)


class Car:
    """Forward-only car model shared by CSV mode and pygame mode."""

    def __init__(self, params: CarParams | None = None) -> None:
        self.params = params or CarParams()
        self.state = CarState()

    def reset(self) -> None:
        self.state = CarState()

    def step(self, dt: float, inputs: DriverInputs) -> CarState:
        if dt <= 0:
            raise ValueError("dt must be positive")

        p = self.params
        u = inputs.sanitized(p.max_steering_angle_deg)
        s = self.state

        # ----- Longitudinal forces -----
        propulsion = propulsion_force(
            u.throttle, s.speed, p.max_propulsion_force, p.vmax
        )
        aero_drag = drag_force(s.speed, p.frontal_area, p.drag_coefficient, p.air_density)
        rolling = rolling_resistance_force(
            p.rolling_resistance_coefficient, p.normal_force, s.speed
        )
        braking = braking_force(
            u.brake_pressure_front,
            u.brake_pressure_rear,
            u.brake_pedal_travel,
            p.max_braking_capacity,
            p.max_grip,
        )

        net_longitudinal_force = propulsion - aero_drag - rolling - braking
        acceleration = net_longitudinal_force / p.mass
        new_speed = max(0.0, s.speed + acceleration * dt)

        # ----- Lateral forces -----
        current_slip = slip_angle(
            u.steering_angle_deg,
            s.lateral_velocity,
            s.speed,
            p.slip_speed_epsilon,
        )
        lateral = lateral_force(
            current_slip,
            p.cornering_stiffness,
            p.max_grip,
        )
        lateral_accel = lateral_acceleration(lateral, p.mass)
        new_lateral_velocity = s.lateral_velocity + lateral_accel * dt

        # ----- Simple yaw/position integration -----
        yaw_rate = s.lateral_velocity / max(s.speed, p.slip_speed_epsilon)
        new_heading = s.heading + yaw_rate * dt
        new_x = s.x + s.speed * math.cos(s.heading) * dt
        new_y = s.y + s.speed * math.sin(s.heading) * dt

        self.state = CarState(
            time=s.time + dt,
            x=new_x,
            y=new_y,
            heading=new_heading,
            speed=new_speed,
            acceleration=acceleration,
            lateral_velocity=new_lateral_velocity,
            lateral_acceleration=lateral_accel,
            slip_angle=current_slip,
            steering_angle=u.steering_angle_deg,
            throttle=u.throttle,
            brake_pedal=u.brake_pedal_travel,
            brake_pressure_front=u.brake_pressure_front,
            brake_pressure_rear=u.brake_pressure_rear,
            propulsion_force=propulsion,
            drag_force=aero_drag,
            rolling_resistance=rolling,
            braking_force=braking,
            lateral_force=lateral,
        )
        return self.state
