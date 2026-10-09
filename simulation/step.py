"""One fixed-step update of the car's longitudinal and lateral physics."""

from __future__ import annotations

import math

from config import CarParameters
from physics.braking import braking_force
from physics.drag import drag_force
from physics.motor import propulsion_force
from physics.rolling_resistance import rolling_resistance_force
from physics.traction import lateral_acceleration, lateral_force, slip_angle
from simulation.state import CarState, DriverInputs


class Car:
    """Forward-only car model advanced through :meth:`step`."""

    def __init__(
        self,
        params: CarParameters | None = None,
        initial_heading_rad: float = 0.0,
    ) -> None:
        self.params = params or CarParameters()
        self.initial_heading_rad = initial_heading_rad
        self.state = CarState(heading=initial_heading_rad)

    def reset(self) -> None:
        """Restore the initial state while retaining the configured heading."""
        self.state = CarState(heading=self.initial_heading_rad)

    def step(self, dt: float, inputs: DriverInputs) -> CarState:
        """Advance the vehicle by one time step and return the new state."""
        if dt <= 0:
            raise ValueError(
                "dt must be positive; provide a time step greater than zero"
            )

        params = self.params
        controls = inputs.sanitized(params.max_steering_angle_deg)
        state = self.state

        propulsion = propulsion_force(
            controls.throttle,
            state.speed,
            params.max_propulsion_force,
            params.vmax,
        )
        aerodynamic_drag = drag_force(
            state.speed,
            params.frontal_area,
            params.drag_coefficient,
            params.air_density,
        )
        rolling_resistance = rolling_resistance_force(
            params.rolling_resistance_coefficient,
            params.normal_force,
            state.speed,
        )
        braking = braking_force(
            controls.brake_pressure_front,
            controls.brake_pressure_rear,
            controls.brake_pedal_travel,
            params.max_braking_capacity,
            params.max_grip,
        )
        acceleration = (
            propulsion - aerodynamic_drag - rolling_resistance - braking
        ) / params.mass
        speed = max(0.0, state.speed + acceleration * dt)

        slip = slip_angle(
            controls.steering_angle_deg,
            state.lateral_velocity,
            state.speed,
            params.slip_speed_epsilon,
        )
        lateral = lateral_force(
            slip,
            params.cornering_stiffness,
            params.max_grip,
        )
        lateral_accel = lateral_acceleration(lateral, params.mass)
        lateral_velocity = state.lateral_velocity + lateral_accel * dt

        # Position uses the current state so the integrator remains explicit.
        yaw_rate = state.lateral_velocity / max(
            state.speed,
            params.slip_speed_epsilon,
        )
        heading = state.heading + yaw_rate * dt
        x = state.x + state.speed * math.cos(state.heading) * dt
        y = state.y + state.speed * math.sin(state.heading) * dt

        self.state = CarState(
            time=state.time + dt,
            x=x,
            y=y,
            heading=heading,
            speed=speed,
            acceleration=acceleration,
            lateral_velocity=lateral_velocity,
            lateral_acceleration=lateral_accel,
            slip_angle=slip,
            steering_angle=controls.steering_angle_deg,
            throttle=controls.throttle,
            brake_pedal=controls.brake_pedal_travel,
            brake_pressure_front=controls.brake_pressure_front,
            brake_pressure_rear=controls.brake_pressure_rear,
            propulsion_force=propulsion,
            drag_force=aerodynamic_drag,
            rolling_resistance=rolling_resistance,
            braking_force=braking,
            lateral_force=lateral,
        )
        return self.state