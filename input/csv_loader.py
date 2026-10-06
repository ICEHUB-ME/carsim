"""Load and validate driver-input CSV files."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

REQUIRED_COLUMNS = (
    "time",
    "throttle",
    "brakePressureFront",
    "brakePressureRear",
    "brakePedalTravel",
    "steerAngle",
)


@dataclass(frozen=True)
class DriverInputSeries:
    time: np.ndarray
    throttle: np.ndarray
    brake_pressure_front: np.ndarray
    brake_pressure_rear: np.ndarray
    brake_pedal_travel: np.ndarray
    steer_angle_deg: np.ndarray


def _as_float_column(rows: list[dict[str, str]], name: str) -> np.ndarray:
    try:
        return np.asarray([float(row[name]) for row in rows], dtype=float)
    except (KeyError, ValueError) as exc:
        raise ValueError(f"Column {name!r} contains missing/non-numeric data") from exc


def load_driver_csv(path: str | Path) -> DriverInputSeries:
    path = Path(path)
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header row")
        missing = [name for name in REQUIRED_COLUMNS if name not in reader.fieldnames]
        if missing:
            raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")
        rows = list(reader)

    if not rows:
        raise ValueError("CSV contains no data rows")

    arrays = {name: _as_float_column(rows, name) for name in REQUIRED_COLUMNS}
    time = arrays["time"]

    if np.any(~np.isfinite(time)):
        raise ValueError("time contains non-finite values")
    if np.any(np.diff(time) <= 0):
        raise ValueError("time must be strictly increasing")
    if time[0] < 0:
        raise ValueError("time cannot be negative")

    def finite(name: str) -> np.ndarray:
        values = arrays[name]
        if np.any(~np.isfinite(values)):
            raise ValueError(f"{name} contains non-finite values")
        return values

    throttle = np.clip(finite("throttle"), 0.0, 1.0)
    front = np.clip(finite("brakePressureFront"), 0.0, 1.0)
    rear = np.clip(finite("brakePressureRear"), 0.0, 1.0)
    pedal = np.clip(finite("brakePedalTravel"), 0.0, 1.0)
    steering = finite("steerAngle")

    return DriverInputSeries(
        time=time,
        throttle=throttle,
        brake_pressure_front=front,
        brake_pressure_rear=rear,
        brake_pedal_travel=pedal,
        steer_angle_deg=steering,
    )
