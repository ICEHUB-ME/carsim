"""Fixed-step simulation and deterministic CSV replay helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np

from simulation.state import DriverInputs
from simulation.step import Car
from config import CarParameters
from csv_output import OUTPUT_FIELDS, rows_to_columns, save_simulation_csv
from input.csv_loader import DriverInputSeries, load_driver_csv
from input.interpolation import interpolate_columns, make_time_grid


@dataclass(frozen=True)
class SimulationResult:
    """Column-oriented simulation state with convenient named access."""

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
        """Return arrays in the established CSV field order."""
        return tuple(self.data[field] for field in OUTPUT_FIELDS)

    def as_dict(self) -> dict[str, np.ndarray]:
        """Return a shallow copy of the result columns."""
        return dict(self.data)


def _resample_inputs(
    inputs: DriverInputSeries,
    time_step: float,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Interpolate controls onto the physics model's fixed time grid."""
    target_time = make_time_grid(0.0, float(inputs.time[-1]), time_step)
    source_columns = {
        "throttle": inputs.throttle,
        "brake_pressure_front": inputs.brake_pressure_front,
        "brake_pressure_rear": inputs.brake_pressure_rear,
        "brake_pedal_travel": inputs.brake_pedal_travel,
        "steer_angle_deg": inputs.steer_angle_deg,
    }
    return target_time, interpolate_columns(inputs.time, source_columns, target_time)


def _driver_at(
    controls: dict[str, np.ndarray],
    index: int,
) -> DriverInputs:
    """Build one immutable control sample from interpolated columns."""
    return DriverInputs(
        throttle=float(controls["throttle"][index]),
        brake_pressure_front=float(controls["brake_pressure_front"][index]),
        brake_pressure_rear=float(controls["brake_pressure_rear"][index]),
        brake_pedal_travel=float(controls["brake_pedal_travel"][index]),
        steering_angle_deg=float(controls["steer_angle_deg"][index]),
    )


def iter_simulation_inputs(
    inputs: DriverInputSeries,
    params: CarParameters | None = None,
) -> Iterator[tuple[float, DriverInputs]]:
    """Yield the initial sample, then each fixed-step driver command."""
    vehicle = params or CarParameters()
    sample_times, controls = _resample_inputs(inputs, vehicle.sim_dt)

    # The initial state is recorded before the first control interval.
    yield float(sample_times[0]), DriverInputs()
    for index in range(len(sample_times) - 1):
        yield float(sample_times[index + 1]), _driver_at(controls, index)


def iter_simulation_states(
    inputs: DriverInputSeries,
    params: CarParameters | None = None,
    *,
    initial_heading_rad: float = 0.0,
) -> Iterator[tuple[float, Car]]:
    """Yield each state using the same fixed-step path as CSV simulation."""
    vehicle = params or CarParameters()
    car = Car(vehicle, initial_heading_rad=initial_heading_rad)
    timeline = iter_simulation_inputs(inputs, params=vehicle)

    first_time, _ = next(timeline)
    yield first_time, car

    for sample_time, driver_inputs in timeline:
        car.step(sample_time - car.state.time, driver_inputs)
        yield sample_time, car


def simulate_driver_inputs(
    inputs: DriverInputSeries,
    params: CarParameters | None = None,
    *,
    initial_heading_rad: float = 0.0,
) -> SimulationResult:
    """Run a driver-input series and collect the established state columns."""
    rows: list[dict[str, float]] = []
    states = iter_simulation_states(
        inputs,
        params=params,
        initial_heading_rad=initial_heading_rad,
    )
    for sample_time, car in states:
        snapshot = car.state.as_dict()
        snapshot["time"] = sample_time
        rows.append({field: float(snapshot[field]) for field in OUTPUT_FIELDS})
    return SimulationResult(rows_to_columns(rows))


def simulate_csv(
    csv_path: str | Path,
    output_path: str | Path = "simulation_output.csv",
    params: CarParameters | None = None,
    *,
    initial_heading_rad: float = 0.0,
) -> SimulationResult:
    """Load controls, simulate them, and write the established output schema."""
    driver_inputs = load_driver_csv(csv_path)
    result = simulate_driver_inputs(
        driver_inputs,
        params=params,
        initial_heading_rad=initial_heading_rad,
    )
    save_simulation_csv(result, output_path)
    return result