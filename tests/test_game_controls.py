from __future__ import annotations

import sys
import types
import unittest

ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from input.game_controls import GameControls


class _FakeKeys:
    def __init__(self, pressed: set[int]):
        self.pressed = pressed

    def __getitem__(self, key: int) -> bool:
        return key in self.pressed


FAKE_PYGAME = types.SimpleNamespace(
    K_w=1,
    K_s=2,
    K_SPACE=3,
    K_a=4,
    K_d=5,
)


class GameControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._previous = sys.modules.get("pygame")
        sys.modules["pygame"] = FAKE_PYGAME

    @classmethod
    def tearDownClass(cls):
        if cls._previous is None:
            sys.modules.pop("pygame", None)
        else:
            sys.modules["pygame"] = cls._previous

    def test_w_smoothing_and_release(self):
        controls = GameControls(2.0, 2.0, 90.0, 30.0)
        state = controls.update(0.25, _FakeKeys({FAKE_PYGAME.K_w}))
        self.assertAlmostEqual(state.throttle, 0.5)
        self.assertAlmostEqual(state.brake_pedal_travel, 0.0)

        state = controls.update(0.25, _FakeKeys(set()))
        self.assertAlmostEqual(state.throttle, 0.0)

        state = controls.update(0.25, _FakeKeys({FAKE_PYGAME.K_s}))
        self.assertAlmostEqual(state.brake_pedal_travel, 0.5)
        self.assertAlmostEqual(state.brake_pressure_front, 0.5)
        self.assertAlmostEqual(state.brake_pressure_rear, 0.5)

    def test_space_is_brake_alias(self):
        controls = GameControls(2.0, 2.0, 90.0, 30.0)
        state = controls.update(0.5, _FakeKeys({FAKE_PYGAME.K_SPACE}))
        self.assertAlmostEqual(state.brake_pedal_travel, 1.0)
        self.assertAlmostEqual(state.brake_pressure_front, 1.0)
        self.assertAlmostEqual(state.brake_pressure_rear, 1.0)

    def test_steering_direction(self):
        controls = GameControls(2.0, 2.0, 90.0, 30.0)
        state = controls.update(1.0, _FakeKeys({FAKE_PYGAME.K_a}))
        self.assertAlmostEqual(state.steering_angle_deg, 30.0)

        state = controls.update(1.0, _FakeKeys({FAKE_PYGAME.K_d}))
        self.assertAlmostEqual(state.steering_angle_deg, -30.0)

        state = controls.update(1.0, _FakeKeys(set()))
        self.assertAlmostEqual(state.steering_angle_deg, 0.0)


if __name__ == "__main__":
    unittest.main()
