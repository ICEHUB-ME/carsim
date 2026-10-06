"""Fixed-step CSV simulation and replay-friendly state iterator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np

from car import Car, CarState, DriverInputs
from config import CarParams
from input.csv_loader import DriverInputSeries, load_driver_csv
from input.interpolation import interpolate_columns, make_time_grid

OUTPUT_FIELDS = (
    "time",
    "x",
    "y",
    "heading",
    "speed",
    "acceleration",
    "lateral_velocity",
    "lateral_acceleration",
    "slip_angle",
    "steering_angle",
    "throttle",
    "brake_pedal",
    "brake_pressure_front",
    "brake_pressure_rear",
    "propulsion_force",
    "drag_force",
    "rolling_resistance",
    "braking_force",
    "lateral_force",
)


@dataclass
class SimulationResult:
    data: dict[str, np.ndarray]

    def __getitem__(self, field: str) -> np.ndarray:
        return self.data[field]

    @property
    def time(self) -> np.ndarray:
        return self.data["time"]

    @property
    def x(self) -> np.ndarray:
        return self.data["x"]

    @property
    def y(self) -> np.ndarray:
        return self.data["y"]

    def to_matplotlib_arrays(self) -> tuple[np.ndarray, ...]:
        """Return arrays in the exact order of OUTPUT_FIELDS."""
        return tuple(self.data[name] for name in OUTPUT_FIELDS)

    def as_dict(self) -> dict[str, np.ndarray]:
        return dict(self.data)


def _resample_inputs(inputs: DriverInputSeries, sim_dt: float) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    # The simulator always starts from the standard t=0 initial condition.
    target_time = make_time_grid(0.0, float(inputs.time[-1]), sim_dt)
    columns = interpolate_columns(
        inputs.time,
        {
            "throttle": inputs.throttle,
            "brake_pressure_front": inputs.brake_pressure_front,
            "brake_pressure_rear": inputs.brake_pressure_rear,
            "brake_pedal_travel": inputs.brake_pedal_travel,
            "steer_angle_deg": inputs.steer_angle_deg,
        },
        target_time,
    )
    return target_time, columns


def _driver_at(u: dict[str, np.ndarray], index: int) -> DriverInputs:
    """Create direct CSV driver inputs; no game-mode smoothing is applied."""
    return DriverInputs(
        throttle=float(u["throttle"][index]),
        brake_pressure_front=float(u["brake_pressure_front"][index]),
        brake_pressure_rear=float(u["brake_pressure_rear"][index]),
        brake_pedal_travel=float(u["brake_pedal_travel"][index]),
        steering_angle_deg=float(u["steer_angle_deg"][index]),
    )


def iter_simulation_states(
    inputs: DriverInputSeries,
    params: CarParams | None = None,
) -> Iterator[tuple[float, Car]]:
    """Yield the live Car object at every interpolated simulation timestep.

    This is the common fixed-step path used by CSV headless simulation and the
    pygame replay mode. CSV values are applied directly and never passed
    through GameControls smoothing.
    """
    p = params or CarParams()
    times, u = _resample_inputs(inputs, p.sim_dt)
    car = Car(p)

    yield float(times[0]), car
    for i in range(len(times) - 1):
        car.step(float(times[i + 1] - times[i]), _driver_at(u, i))
        yield float(times[i + 1]), car


def simulate_driver_inputs(
    inputs: DriverInputSeries,
    params: CarParams | None = None,
) -> SimulationResult:
    p = params or CarParams()
    rows: dict[str, list[float]] = {field: [] for field in OUTPUT_FIELDS}

    for _, car in iter_simulation_states(inputs, params=p):
        snapshot = car.state.as_dict()
        for field in OUTPUT_FIELDS:
            rows[field].append(float(snapshot[field]))

    return SimulationResult({field: np.asarray(values, dtype=float) for field, values in rows.items()})


def simulate_csv(
    csv_path: str | Path,
    output_path: str | Path = "simulation_output.csv",
    params: CarParams | None = None,
) -> SimulationResult:
    inputs = load_driver_csv(csv_path)
    result = simulate_driver_inputs(inputs, params=params)
    save_simulation_csv(result, output_path)
    return result


def save_simulation_csv(result: SimulationResult, output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    matrix = np.column_stack([result.data[field] for field in OUTPUT_FIELDS])
    np.savetxt(
        output_path,
        matrix,
        delimiter=",",
        header=",".join(OUTPUT_FIELDS),
        comments="",
        fmt="%.10g",
    )