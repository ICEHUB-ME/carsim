"""Flexible CSV loader for driver-input time series."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np


# Internal canonical names.
REQUIRED_FIELDS = (
    "time",
    "throttle",
    "brake_pressure_front",
    "brake_pressure_rear",
    "brake_pedal_travel",
    "steer_angle_deg",
)


# Accepted CSV column names for each canonical field.
#
# The first names are the simulator's original input names.
# The additional names support the columns produced by game mode.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "time": (
        "time",
    ),
    "throttle": (
        "throttle",
    ),
    "brake_pressure_front": (
        "brakePressureFront",
        "brake_pressure_front",
    ),
    "brake_pressure_rear": (
        "brakePressureRear",
        "brake_pressure_rear",
    ),
    "brake_pedal_travel": (
        "brakePedalTravel",
        "brake_pedal_travel",
        "brake_pedal",
    ),
    "steer_angle_deg": (
        "steerAngle",
        "steer_angle",
        "steering_angle",
    ),
}


@dataclass(frozen=True)
class DriverInputSeries:
    """Normalized driver inputs consumed by the simulation engine."""

    time: np.ndarray
    throttle: np.ndarray
    brake_pressure_front: np.ndarray
    brake_pressure_rear: np.ndarray
    brake_pedal_travel: np.ndarray
    steer_angle_deg: np.ndarray


def _normalize_column_name(name: str) -> str:
    """
    Normalize a CSV header for comparison.

    This makes detection tolerant of:
        "throttle"
        "Throttle"
        " throttle "
        "THROTTLE"
    """

    return name.strip().lower()


def _find_column(
    fieldnames: list[str],
    canonical_name: str,
) -> str | None:
    """
    Find the actual CSV column corresponding to a canonical field.
    """

    aliases = COLUMN_ALIASES[canonical_name]

    normalized_headers = {
        _normalize_column_name(header): header
        for header in fieldnames
    }

    for alias in aliases:
        actual = normalized_headers.get(_normalize_column_name(alias))
        if actual is not None:
            return actual

    return None


def _as_float_column(
    rows: list[dict[str, str]],
    csv_column: str,
    canonical_name: str,
) -> np.ndarray:
    """Convert one CSV column into a numeric NumPy array."""

    values: list[float] = []

    for row_number, row in enumerate(rows, start=2):
        raw_value = row.get(csv_column, "")

        if raw_value is None or raw_value.strip() == "":
            raise ValueError(
                f"Column {csv_column!r} contains a missing value "
                f"at CSV row {row_number}"
            )

        try:
            values.append(float(raw_value))
        except ValueError as exc:
            raise ValueError(
                f"Column {csv_column!r} contains non-numeric data "
                f"at CSV row {row_number}: {raw_value!r}"
            ) from exc

    result = np.asarray(values, dtype=float)

    if np.any(~np.isfinite(result)):
        raise ValueError(
            f"Column {csv_column!r} contains non-finite values"
        )

    return result


def load_driver_csv(path: str | Path) -> DriverInputSeries:
    """
    Load any CSV containing the required driver inputs.

    Extra columns are intentionally ignored.

    Supported input-column variants include:

        throttle
        brakePressureFront / brake_pressure_front
        brakePressureRear / brake_pressure_rear
        brakePedalTravel / brake_pedal_travel / brake_pedal
        steerAngle / steer_angle / steering_angle

    The returned DriverInputSeries always uses the simulator's
    canonical internal representation.
    """

    path = Path(path)

    with path.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        reader = csv.DictReader(handle)

        if reader.fieldnames is None:
            raise ValueError(
                f"CSV {path} has no header row"
            )

        fieldnames = list(reader.fieldnames)

        # Resolve every required field to an actual CSV column.
        column_map: dict[str, str] = {}
        missing: list[str] = []

        for canonical_name in REQUIRED_FIELDS:
            actual_column = _find_column(
                fieldnames,
                canonical_name,
            )

            if actual_column is None:
                missing.append(canonical_name)
            else:
                column_map[canonical_name] = actual_column

        if missing:
            available = ", ".join(fieldnames)

            raise ValueError(
                f"CSV {path} is missing required driver-input "
                f"columns: {', '.join(missing)}.\n"
                f"Available columns: {available}"
            )

        rows = list(reader)

    if not rows:
        raise ValueError(
            f"CSV {path} contains no data rows"
        )

    # Extract ONLY the columns required by the physics engine.
    arrays = {
        canonical_name: _as_float_column(
            rows,
            csv_column,
            canonical_name,
        )
        for canonical_name, csv_column in column_map.items()
    }

    time = arrays["time"]

    if len(time) < 1:
        raise ValueError("CSV contains no time samples")

    if np.any(~np.isfinite(time)):
        raise ValueError("time contains non-finite values")

    if np.any(np.diff(time) <= 0):
        raise ValueError(
            "time must be strictly increasing; sort rows and remove "
            "duplicate timestamps"
        )

    if time[0] < 0:
        raise ValueError(
            "time cannot be negative; start the CSV timeline at zero or later"
        )

    # Driver inputs are normalized to the ranges expected by Car.step().
    throttle = np.clip(
        arrays["throttle"],
        0.0,
        1.0,
    )

    brake_pressure_front = np.clip(
        arrays["brake_pressure_front"],
        0.0,
        1.0,
    )

    brake_pressure_rear = np.clip(
        arrays["brake_pressure_rear"],
        0.0,
        1.0,
    )

    brake_pedal_travel = np.clip(
        arrays["brake_pedal_travel"],
        0.0,
        1.0,
    )

    steer_angle_deg = arrays["steer_angle_deg"]
    return DriverInputSeries(
        time=time,
        throttle=throttle,
        brake_pressure_front=brake_pressure_front,
        brake_pressure_rear=brake_pressure_rear,
        brake_pedal_travel=brake_pedal_travel,
        steer_angle_deg=steer_angle_deg,
    )