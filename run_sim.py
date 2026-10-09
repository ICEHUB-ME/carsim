"""Command-line CSV simulation entry point."""

from __future__ import annotations

import argparse
import math

from config import CarParameters
from simulation import simulate_csv


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the unified car simulator from CSV driver inputs."
    )
    parser.add_argument("csv", help="Input CSV with driver commands")
    parser.add_argument(
        "-o",
        "--output",
        default="simulation_output.csv",
        help="Output CSV path (default: simulation_output.csv)",
    )
    parser.add_argument("--initial-heading-deg", type=float, default=0.0)
    args = parser.parse_args()

    result = simulate_csv(
        args.csv,
        args.output,
        CarParameters(),
        initial_heading_rad=math.radians(args.initial_heading_deg),
    )
    print(f"Simulation complete: {len(result.time)} samples")
    print(f"Duration: {result.time[-1]:.3f} s")
    final_speed = result["speed"][-1]
    print(
        f"Final speed: {final_speed:.3f} m/s "
        f"({final_speed * 3.6:.3f} km/h)"
    )
    print(
        f"Final position: x={result['x'][-1]:.3f} m, "
        f"y={result['y'][-1]:.3f} m"
    )
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
