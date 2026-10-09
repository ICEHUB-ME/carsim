"""Example: animate a simulation result with matplotlib."""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from simulation import SimulationResult, simulate_csv

PLOT_MARGIN_M = 5.0
DEFAULT_FRAME_INTERVAL_MS = 10.0


def create_animation(result: SimulationResult):
    """Create a path animation without starting the GUI as an import side effect."""
    figure, axes = plt.subplots(figsize=(8, 6))
    axes.set_aspect("equal", adjustable="box")
    axes.set_xlabel("x [m]")
    axes.set_ylabel("y [m]")
    axes.set_title("Car Path")
    axes.set_xlim(result.x.min() - PLOT_MARGIN_M, result.x.max() + PLOT_MARGIN_M)
    axes.set_ylim(result.y.min() - PLOT_MARGIN_M, result.y.max() + PLOT_MARGIN_M)

    path_line, = axes.plot([], [], lw=2)
    car_marker, = axes.plot([], [], marker="o")

    def initialize():
        path_line.set_data([], [])
        car_marker.set_data([], [])
        return path_line, car_marker

    def update(frame_index: int):
        path_line.set_data(result.x[:frame_index + 1], result.y[:frame_index + 1])
        car_marker.set_data([result.x[frame_index]], [result.y[frame_index]])
        return path_line, car_marker

    interval_ms = (
        result.time[1] * 1000.0
        if len(result.time) > 1
        else DEFAULT_FRAME_INTERVAL_MS
    )
    animation = FuncAnimation(
        figure,
        update,
        frames=len(result.time),
        init_func=initialize,
        interval=interval_ms,
        blit=True,
    )
    return figure, animation


def main() -> None:
    """Run the example with the included braking-turn input profile."""
    result = simulate_csv(
        Path("examples/braking_turn.csv"),
        output_path="simulation_output.csv",
    )
    create_animation(result)
    plt.show()


if __name__ == "__main__":
    main()