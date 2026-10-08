from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from car import Car, DriverInputs
from config import CarParams
from physics.braking import braking_force
from physics.motor import propulsion_force
from physics.throttle import diagnostic_acceleration
from simulation import simulate_csv


class PhysicsTests(unittest.TestCase):
    def test_reference_torque_model(self):
        p = CarParams()
        a = diagnostic_acceleration(
            1.0, p.max_motor_torque, p.gear_ratio, p.wheel_radius, p.mass
        )
        expected = (180.0 * 3.0 / 0.216) / 300.0
        self.assertTrue(math.isclose(a, expected, rel_tol=1e-12))

    def test_back_emf_at_zero_speed(self):
        self.assertEqual(propulsion_force(1.0, 0.0, 2000.0, 27.0), 2000.0)

    def test_brake_mapping_full_input(self):
        p = CarParams()
        self.assertTrue(
            math.isclose(
                braking_force(1.0, 1.0, 1.0, p.max_braking_capacity, p.max_grip),
                1850.0,
            )
        )

    def test_traction_limit(self):
        p = CarParams()
        car = Car(p)
        car.step(0.01, DriverInputs(throttle=1.0, steering_angle_deg=30.0))
        self.assertLessEqual(abs(car.state.lateral_force), p.max_grip + 1e-9)

    def test_forward_only_braking(self):
        p = CarParams()
        car = Car(p)
        car.step(0.01, DriverInputs(throttle=1.0))
        for _ in range(1000):
            car.step(
                0.01,
                DriverInputs(
                    brake_pressure_front=1.0,
                    brake_pressure_rear=1.0,
                    brake_pedal_travel=1.0,
                ),
            )
        self.assertGreaterEqual(car.state.speed, 0.0)
        self.assertTrue(np.isfinite(car.state.speed))

    def test_csv_resampling_produces_100_hz_grid(self):
        output = ROOT / "tests" / "_output.csv"
        try:
            result = simulate_csv(ROOT / "examples" / "low_rate_input.csv", output)
            self.assertTrue(
                math.isclose(
                    result.time[1] - result.time[0],
                    0.01,
                    rel_tol=0,
                    abs_tol=1e-12,
                )
            )
            self.assertEqual(len(result.time), len(result.x))
            self.assertTrue(np.all(np.isfinite(result.x)))
            self.assertTrue(np.all(np.isfinite(result.y)))
        finally:
            output.unlink(missing_ok=True)

def test_game_output_csv_columns_are_accepted(self):
    output = ROOT / "tests" / "_game_output.csv"
    input_csv = ROOT / "tests" / "_game_input.csv"

    input_csv.write_text(
        "\n".join(
            [
                "time,x,y,speed,throttle,brake_pedal,"
                "brake_pressure_front,brake_pressure_rear,"
                "steering_angle,random_column",
                "0.0,0,0,0,0,0,0,0,0,hello",
                "0.01,1,2,3,0.5,0.25,0.8,0.7,5,world",
            ]
        ),
        encoding="utf-8",
    )

    try:
        result = simulate_csv(input_csv, output)

        self.assertEqual(len(result.time), 2)

        self.assertTrue(
            np.isclose(result["throttle"][1], 0.5)
        )

        self.assertTrue(
            np.isclose(result["brake_pedal"][1], 0.25)
        )

        self.assertTrue(
            np.isclose(result["brake_pressure_front"][1], 0.8)
        )

        self.assertTrue(
            np.isclose(result["brake_pressure_rear"][1], 0.7)
        )

        self.assertTrue(
            np.isclose(result["steering_angle"][1], 5.0)
        )

    finally:
        input_csv.unlink(missing_ok=True)
        output.unlink(missing_ok=True)

def test_missing_driver_input_column_raises(self):
    input_csv = ROOT / "tests" / "_invalid_input.csv"

    input_csv.write_text(
        "time,throttle,steering_angle\n"
        "0.0,0.0,0.0\n"
        "0.01,1.0,5.0\n",
        encoding="utf-8",
    )

    try:
        with self.assertRaisesRegex(
            ValueError,
            "missing required driver-input columns",
        ):
            from input.csv_loader import load_driver_csv

            load_driver_csv(input_csv)
    finally:
        input_csv.unlink(missing_ok=True)

if __name__ == "__main__":
    unittest.main()
