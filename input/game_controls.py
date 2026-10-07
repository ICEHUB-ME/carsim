"""Keyboard controls and manual pedal override for pygame modes."""

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
    """Keyboard driver inputs with game-mode smoothing plus manual pedal entry.

    Normal game controls:
      W      -> throttle target = 100%
      S      -> brake target = 100%
      Space  -> brake target = 100%
      A      -> steering target = +max angle (RIGHT)
      D      -> steering target = -max angle (LEFT)

    Manual mode:
      M      -> toggle manual throttle/brake override
      TAB    -> select throttle/brake field
      0-9    -> enter percentage digits
      Enter  -> apply the typed percentage (0-100)
      Backspace -> delete a digit

    Manual throttle/brake values are direct (no smoothing). Steering continues
    to use the configured game-mode smoothing. The same manual state can be
    used by CSV replay to override CSV throttle/brake values without applying
    game smoothing.
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

        self.manual_mode = False
        self.manual_field = "throttle"
        self.manual_throttle = 0.0
        self.manual_brake = 0.0
        self._manual_buffer = ""

    @property
    def manual_buffer(self) -> str:
        return self._manual_buffer

    def _manual_percent(self) -> float:
        if not self._manual_buffer:
            return 0.0
        return max(0.0, min(100.0, float(self._manual_buffer))) / 100.0

    def _apply_manual_buffer(self) -> None:
        value = self._manual_percent()
        if self.manual_field == "throttle":
            self.manual_throttle = value
        else:
            self.manual_brake = value
        self._manual_buffer = ""

    def set_manual_values(self, throttle: float, brake: float) -> None:
        """Set manual pedal values directly, clamped to [0, 1]."""
        self.manual_throttle = max(0.0, min(1.0, float(throttle)))
        self.manual_brake = max(0.0, min(1.0, float(brake)))

    def toggle_manual_mode(
        self,
        current_throttle: float | None = None,
        current_brake: float | None = None,
    ) -> bool:
        """Toggle manual pedal override and return the new state.

        Optional current values let CSV replay enter manual mode without a
        sudden pedal jump from the CSV value to the controller's previous value.
        """
        self.manual_mode = not self.manual_mode
        self._manual_buffer = ""
        if self.manual_mode:
            throttle = self.state.throttle if current_throttle is None else current_throttle
            brake = self.state.brake_pedal_travel if current_brake is None else current_brake
            self.set_manual_values(throttle, brake)
        return self.manual_mode

    def handle_event(
        self,
        event,
        current_throttle: float | None = None,
        current_brake: float | None = None,
    ) -> bool:
        """Handle mode/entry keys. Return True when manual mode changed."""
        import pygame

        if event.type != pygame.KEYDOWN:
            return False

        if event.key == pygame.K_m:
            self.toggle_manual_mode(current_throttle, current_brake)
            return True

        if not self.manual_mode:
            return False

        if event.key == pygame.K_TAB:
            self.manual_field = "brake" if self.manual_field == "throttle" else "throttle"
            self._manual_buffer = ""
            return False

        if event.key == pygame.K_BACKSPACE:
            self._manual_buffer = self._manual_buffer[:-1]
            return False

        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._apply_manual_buffer()
            return False

        digit_map = {
            pygame.K_0: "0", pygame.K_1: "1", pygame.K_2: "2",
            pygame.K_3: "3", pygame.K_4: "4", pygame.K_5: "5",
            pygame.K_6: "6", pygame.K_7: "7", pygame.K_8: "8",
            pygame.K_9: "9",
        }
        digit = digit_map.get(event.key)
        if digit is not None and len(self._manual_buffer) < 3:
            self._manual_buffer += digit
            # Three digits can only exceed 100 for values such as 999. Keep the
            # display editable and clamp on Enter rather than silently changing it.
            return False

        return False

    def manual_driver_values(self) -> tuple[float, float] | None:
        """Return (throttle, brake) overrides, or None when manual mode is off."""
        if not self.manual_mode:
            return None
        return self.manual_throttle, self.manual_brake

    def update(self, dt: float, keys) -> GameControlState:
        import pygame

        if dt < 0:
            raise ValueError("dt must be non-negative")

        # Pedal inputs are direct while manual mode is active.
        if self.manual_mode:
            self.state.throttle = self.manual_throttle
            self.state.brake_pedal_travel = self.manual_brake
            self.state.brake_pressure_front = self.manual_brake
            self.state.brake_pressure_rear = self.manual_brake
        else:
            # W controls throttle. Releasing W smoothly returns throttle to zero.
            throttle_target = 1.0 if keys[pygame.K_w] else 0.0
            brake_target = 1.0 if (keys[pygame.K_s] or keys[pygame.K_SPACE]) else 0.0

            self.state.throttle = approach(
                self.state.throttle, throttle_target, self.throttle_rate * dt
            )
            self.state.brake_pedal_travel = approach(
                self.state.brake_pedal_travel, brake_target, self.brake_rate * dt
            )
            self.state.brake_pressure_front = approach(
                self.state.brake_pressure_front, brake_target, self.brake_rate * dt
            )
            self.state.brake_pressure_rear = approach(
                self.state.brake_pressure_rear, brake_target, self.brake_rate * dt
            )

        # Requested game-mode direction: A = right/positive, D = left/negative.
        steer_target = 0.0
        if keys[pygame.K_a] and not keys[pygame.K_d]:
            steer_target = self.max_steering_angle_deg
        elif keys[pygame.K_d] and not keys[pygame.K_a]:
            steer_target = -self.max_steering_angle_deg

        self.state.steering_angle_deg = approach(
            self.state.steering_angle_deg,
            steer_target,
            self.steering_rate_deg * dt,
        )
        return self.state
