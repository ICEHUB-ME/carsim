"""Keyboard controls and manual pedal/steering overrides for pygame modes."""

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
    """Keyboard driver inputs with smoothing and independent manual overrides.

    Normal game controls:
      W      -> throttle target = 100%
      S      -> brake target = 100%
      Space  -> brake target = 100%
      A      -> steering target = +max angle (RIGHT)
      D      -> steering target = -max angle (LEFT)

    Manual pedal mode:
      M      -> toggle manual throttle/brake override

    Manual steering mode:
      K      -> toggle manual steering-angle override

    Text entry:
      TAB    -> cycle through active manual fields
      0-9    -> enter digits
      -      -> enter a negative steering angle
      Enter  -> apply the typed value
      Backspace -> delete a character

    Manual overrides are direct values and do not use game-mode smoothing.
    When both manual modes are enabled, TAB cycles through throttle, brake,
    and steering. The same state is used by CSV replay, where enabled manual
    fields replace only their corresponding CSV inputs.
    """

    _PEDAL_FIELDS = ("throttle", "brake")
    _STEER_FIELD = "steering"

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
        self.manual_steer_mode = False
        self.manual_field = "throttle"
        self.manual_throttle = 0.0
        self.manual_brake = 0.0
        self.manual_steering_angle_deg = 0.0
        self._manual_buffer = ""

    @property
    def manual_buffer(self) -> str:
        return self._manual_buffer

    @property
    def manual_steering(self) -> float:
        """Return the configured manual steering angle in degrees."""
        return self.manual_steering_angle_deg

    def _active_manual_fields(self) -> tuple[str, ...]:
        fields: list[str] = []
        if self.manual_mode:
            fields.extend(self._PEDAL_FIELDS)
        if self.manual_steer_mode:
            fields.append(self._STEER_FIELD)
        return tuple(fields)

    def _ensure_valid_manual_field(self) -> None:
        active = self._active_manual_fields()
        if not active:
            self.manual_field = "throttle"
        elif self.manual_field not in active:
            self.manual_field = active[0]

    def _manual_percent(self) -> float:
        if not self._manual_buffer:
            return 0.0
        return max(0.0, min(100.0, float(self._manual_buffer))) / 100.0

    def _manual_steering_degrees(self) -> float:
        if not self._manual_buffer or self._manual_buffer == "-":
            return 0.0
        value = float(self._manual_buffer)
        return max(
            -self.max_steering_angle_deg,
            min(self.max_steering_angle_deg, value),
        )

    def _apply_manual_buffer(self) -> None:
        if not self._manual_buffer:
            return

        if self.manual_field == "steering":
            self.manual_steering_angle_deg = self._manual_steering_degrees()
        elif self.manual_field == "throttle":
            self.manual_throttle = self._manual_percent()
        elif self.manual_field == "brake":
            self.manual_brake = self._manual_percent()

        self._manual_buffer = ""

    def set_manual_values(self, throttle: float, brake: float) -> None:
        """Set manual pedal values directly, clamped to [0, 1]."""
        self.manual_throttle = max(0.0, min(1.0, float(throttle)))
        self.manual_brake = max(0.0, min(1.0, float(brake)))

    def set_manual_steering(self, angle_deg: float) -> None:
        """Set the manual steering angle directly, clamped to max steering."""
        self.manual_steering_angle_deg = max(
            -self.max_steering_angle_deg,
            min(self.max_steering_angle_deg, float(angle_deg)),
        )

    def toggle_manual_mode(
        self,
        current_throttle: float | None = None,
        current_brake: float | None = None,
    ) -> bool:
        """Toggle manual throttle/brake override and return its new state."""
        self.manual_mode = not self.manual_mode
        self._manual_buffer = ""
        if self.manual_mode:
            throttle = self.state.throttle if current_throttle is None else current_throttle
            brake = self.state.brake_pedal_travel if current_brake is None else current_brake
            self.set_manual_values(throttle, brake)
            if self.manual_field not in self._active_manual_fields():
                self.manual_field = "throttle"
        self._ensure_valid_manual_field()
        return self.manual_mode

    def toggle_manual_steer(
        self,
        current_steering: float | None = None,
    ) -> bool:
        """Toggle direct manual steering override and return its new state."""
        self.manual_steer_mode = not self.manual_steer_mode
        self._manual_buffer = ""
        if self.manual_steer_mode:
            steering = (
                self.state.steering_angle_deg
                if current_steering is None
                else current_steering
            )
            self.set_manual_steering(steering)
            self.manual_field = "steering"
        else:
            self._ensure_valid_manual_field()
        return self.manual_steer_mode

    def handle_event(
        self,
        event,
        current_throttle: float | None = None,
        current_brake: float | None = None,
        current_steering: float | None = None,
    ) -> bool:
        """Handle manual-mode toggles and text-entry keys.

        Returns True when either manual mode is toggled.
        """
        import pygame

        if event.type != pygame.KEYDOWN:
            return False

        if event.key == pygame.K_m:
            self.toggle_manual_mode(current_throttle, current_brake)
            return True

        if event.key == pygame.K_k:
            self.toggle_manual_steer(current_steering)
            return True

        if not self._active_manual_fields():
            return False

        if event.key == pygame.K_TAB:
            active = self._active_manual_fields()
            if active:
                current_index = active.index(self.manual_field) if self.manual_field in active else -1
                self.manual_field = active[(current_index + 1) % len(active)]
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
        if digit is not None:
            max_length = 4 if self.manual_field == "steering" else 3
            if len(self._manual_buffer) < max_length:
                self._manual_buffer += digit
            return False

        minus_keys = tuple(
            key for key in (
                getattr(pygame, "K_MINUS", None),
                getattr(pygame, "K_KP_MINUS", None),
            )
            if key is not None
        )
        if self.manual_field == "steering" and event.key in minus_keys:
            if not self._manual_buffer:
                self._manual_buffer = "-"
            return False

        return False

    def manual_driver_values(self) -> tuple[float, float] | None:
        """Return (throttle, brake) overrides, or None when pedal mode is off."""
        if not self.manual_mode:
            return None
        return self.manual_throttle, self.manual_brake

    def manual_steering_value(self) -> float | None:
        """Return manual steering override in degrees, or None when off."""
        if not self.manual_steer_mode:
            return None
        return self.manual_steering_angle_deg

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

        # Manual steering is direct. Otherwise A=RIGHT/positive and D=LEFT/negative.
        if self.manual_steer_mode:
            self.state.steering_angle_deg = self.manual_steering_angle_deg
        else:
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
