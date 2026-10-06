"""Utilities for resampling time-series driver inputs onto a fixed time grid."""

from __future__ import annotations

import numpy as np


def make_time_grid(start: float, end: float, dt: float) -> np.ndarray:
    if dt <= 0:
        raise ValueError("dt must be positive")
    if end < start:
        raise ValueError("end must be >= start")
    count = int(np.floor((end - start) / dt + 1e-9)) + 1
    grid = start + np.arange(count, dtype=float) * dt
    if grid[-1] < end - 1e-10:
        grid = np.append(grid, end)
    else:
        grid[-1] = end if abs(grid[-1] - end) < 1e-9 else grid[-1]
    return grid


def interpolate_columns(
    source_time: np.ndarray,
    source_columns: dict[str, np.ndarray],
    target_time: np.ndarray,
) -> dict[str, np.ndarray]:
    if source_time.ndim != 1 or target_time.ndim != 1:
        raise ValueError("time arrays must be one-dimensional")
    if len(source_time) == 0:
        raise ValueError("source_time is empty")
    return {
        name: np.interp(target_time, source_time, values)
        for name, values in source_columns.items()
    }
