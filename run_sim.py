"""Command-line CSV simulation entry point."""

from __future__ import annotations

import argparse

from config import CarParams
from simulation import simulate_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the unified car simulator from CSV driver inputs.")
    parser.add_argument("csv", help="Input CSV with driver commands")
    parser.add_argument(
        "-o",
        "--output",
        default="simulation_output.csv",
        help="Output CSV path (default: simulation_output.csv)",
    )
    args = parser.parse_args()

    result = simulate_csv(args.csv, args.output, CarParams())
    print(f"Simulation complete: {len(result.time)} samples")
    print(f"Duration: {result.time[-1]:.3f} s")
    print(f"Final speed: {result['speed'][-1]:.3f} m/s ({result['speed'][-1] * 3.6:.3f} km/h)")
    print(f"Final position: x={result['x'][-1]:.3f} m, y={result['y'][-1]:.3f} m")
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
