"""Minimal example showing how simulation arrays plug into matplotlib.animation."""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from simulation import simulate_csv


result = simulate_csv(
    Path("examples/braking_turn.csv"),
    output_path="simulation_output.csv",
)

fig, ax = plt.subplots(figsize=(8, 6))
ax.set_aspect("equal", adjustable="box")
ax.set_xlabel("x [m]")
ax.set_ylabel("y [m]")
ax.set_title("Car Path")

line, = ax.plot([], [], lw=2)
point, = ax.plot([], [], marker="o")

margin = 5.0
ax.set_xlim(result.x.min() - margin, result.x.max() + margin)
ax.set_ylim(result.y.min() - margin, result.y.max() + margin)


def init():
    line.set_data([], [])
    point.set_data([], [])
    return line, point


def update(frame):
    line.set_data(result.x[: frame + 1], result.y[: frame + 1])
    point.set_data([result.x[frame]], [result.y[frame]])
    return line, point


animation = FuncAnimation(
    fig,
    update,
    frames=len(result.time),
    init_func=init,
    interval=result.time[1] * 1000.0 if len(result.time) > 1 else 10.0,
    blit=True,
)

plt.show()
