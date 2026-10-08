"""Mode selector for the unified simulator."""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Unified forward-only car physics simulator"
    )

    subparsers = parser.add_subparsers(
        dest="mode",
        required=True,
    )

    game = subparsers.add_parser(
        "game",
        help="Run interactive pygame driving",
    )

    game.add_argument(
        "--width",
        type=int,
        default=1200,
    )

    game.add_argument(
        "--height",
        type=int,
        default=800,
    )

    game.add_argument(
        "-o",
        "--output",
        default="game_simulation_output.csv",
        help="Recorded game CSV output",
    )

    sim = subparsers.add_parser(
        "sim",
        help="Run CSV simulation as an automatic pygame replay",
    )

    sim.add_argument(
        "csv",
        help="CSV containing driver inputs",
    )

    sim.add_argument(
        "-o",
        "--output",
        default="simulation_output.csv",
    )

    sim.add_argument(
        "--width",
        type=int,
        default=1200,
    )

    sim.add_argument(
        "--height",
        type=int,
        default=800,
    )

    args = parser.parse_args()

    if args.mode == "game":
        from visual.pygame_renderer import run_game

        run_game(
            width=args.width,
            height=args.height,
            output_path=args.output,
        )

    elif args.mode == "sim":
        from visual.pygame_renderer import run_csv_replay

        run_csv_replay(
            args.csv,
            args.output,
            width=args.width,
            height=args.height,
        )


if __name__ == "__main__":
    main()