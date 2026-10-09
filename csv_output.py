"""Shared CSV output utilities for headless simulation, replay, and game recording."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping, Sequence

import numpy as np

# Keep this schema identical for CSV simulation mode and recorded game mode.
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


def write_csv_columns(
    columns: Mapping[str, Sequence[float] | np.ndarray],
    output_path: str | Path,
) -> None:
    """Write named simulation columns using the shared output schema."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    arrays = [np.asarray(columns[field], dtype=float) for field in OUTPUT_FIELDS]
    lengths = {len(array) for array in arrays}
    if len(lengths) != 1:
        raise ValueError("All CSV output columns must have the same length")

    matrix = (
        np.column_stack(arrays)
        if arrays[0].size
        else np.empty((0, len(OUTPUT_FIELDS)))
    )
    np.savetxt(
        output_path,
        matrix,
        delimiter=",",
        header=",".join(OUTPUT_FIELDS),
        comments="",
        fmt="%.10g",
    )


def save_simulation_csv(result, output_path: str | Path) -> None:
    """Save a SimulationResult-like object to the shared CSV format."""
    write_csv_columns(result.data, output_path)


def rows_to_columns(rows: Sequence[Mapping[str, float]]) -> dict[str, np.ndarray]:
    """Convert row-oriented state snapshots into column-oriented arrays.

    Every element must be a mapping with the string keys in ``OUTPUT_FIELDS``.
    This explicit validation prevents confusing errors such as ``string indices
    must be integers`` when a column dictionary or other non-row iterable is
    accidentally passed in.
    """
    if rows is None:
        raise TypeError("rows must be a sequence of dictionaries, not None")

    normalized = list(rows)
    for index, row in enumerate(normalized):
        if not isinstance(row, Mapping):
            raise TypeError(
                f"rows[{index}] must be a dictionary-like mapping with string keys; "
                f"got {type(row).__name__}"
            )
        missing = [field for field in OUTPUT_FIELDS if field not in row]
        if missing:
            raise ValueError(
                f"rows[{index}] is missing required fields: {', '.join(missing)}"
            )

    return {
        field: np.asarray([float(row[field]) for row in normalized], dtype=float)
        for field in OUTPUT_FIELDS
    }
