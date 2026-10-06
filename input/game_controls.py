"""Smooth keyboard controls for pygame game mode."""

from __future__ import annotations

from dataclasses import dataclass


def approach(current: float, target: float, max_delta: float) -> float:
    """Move current toward target by at most max_delta."""
    if current < target:
        return min(current + max_delta, target)
    return max(current - max_delta, target)


@dataclass
class GameControlState:
    throttle: float = 0.0
    brake_pedal_travel: float = 0.0
    brake_pressure_front: float = 0.0
    brake_pressure_rear: float = 0.0
    steering_angle_deg: float = 0.0


class GameControls:
    """Keyboard driver inputs with first-order/slew-style smoothing.

    Controls:
      W      -> throttle target = 100%
      S      -> brake target = 100%
      Space  -> brake target = 100%
      A      -> steering target = -max angle (left)
      D      -> steering target = +max angle (right)

    Releasing W/S/Space smoothly returns the corresponding pedal input to zero.
    """

    def __init__(
        self,
        throttle_rate: float,
        brake_rate: float,
        steering_rate_deg: float,
        max_steering_angle_deg: float,
    ) -> None:
        self.throttle_rate = throttle_rate
        self.brake_rate = brake_rate
        self.steering_rate_deg = steering_rate_deg
        self.max_steering_angle_deg = max_steering_angle_deg
        self.state = GameControlState()

    def update(self, dt: float, keys) -> GameControlState:
        import pygame

        if dt < 0:
            raise ValueError("dt must be non-negative")

        # W controls throttle. Releasing W smoothly returns throttle to zero.
        throttle_target = 1.0 if keys[pygame.K_w] else 0.0

        # S and Space both command the brake. This keeps the requested S pedal
        # behavior while retaining Space as the primary brake shortcut.
        brake_target = 1.0 if (keys[pygame.K_s] or keys[pygame.K_SPACE]) else 0.0

        # A = left (negative), D = right (positive).
        steer_target = 0.0
        if keys[pygame.K_a] and not keys[pygame.K_d]:
            steer_target = -self.max_steering_angle_deg
        elif keys[pygame.K_d] and not keys[pygame.K_a]:
            steer_target = self.max_steering_angle_deg

        self.state.throttle = approach(
            self.state.throttle, throttle_target, self.throttle_rate * dt
        )

        self.state.brake_pedal_travel = approach(
            self.state.brake_pedal_travel, brake_target, self.brake_rate * dt
        )

        # Keyboard braking applies both hydraulic circuits equally.
        self.state.brake_pressure_front = approach(
            self.state.brake_pressure_front, brake_target, self.brake_rate * dt
        )
        self.state.brake_pressure_rear = approach(
            self.state.brake_pressure_rear, brake_target, self.brake_rate * dt
        )

        self.state.steering_angle_deg = approach(
            self.state.steering_angle_deg,
            steer_target,
            self.steering_rate_deg * dt,
        )
        return self.state
