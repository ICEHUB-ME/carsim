"""Pygame game mode and automatic CSV replay mode."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pygame

from car import Car, DriverInputs
from config import CarParams, GameParams
from input.csv_loader import load_driver_csv
from input.game_controls import GameControls
from simulation import OUTPUT_FIELDS, SimulationResult, iter_simulation_states, save_simulation_csv
from visual.birds_eye import BirdsEyeRenderer
from visual.hud import HUD


def _create_renderer(width: int, height: int, params: CarParams, game_params: GameParams):
    birds_eye = BirdsEyeRenderer(
        width,
        height,
        pixels_per_meter=game_params.pixels_per_meter,
        max_path_points=game_params.path_max_points,
    )
    hud = HUD()
    return birds_eye, hud


def run_game(width: int = 1200, height: int = 800) -> None:
    """Run interactive keyboard-controlled game mode."""
    pygame.init()
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Unified Car Physics Simulator — Game")
    clock = pygame.time.Clock()

    params = CarParams()
    game_params = GameParams()
    car = Car(params)
    controls = GameControls(
        throttle_rate=game_params.throttle_rate,
        brake_rate=game_params.brake_rate,
        steering_rate_deg=game_params.steering_rate_deg,
        max_steering_angle_deg=params.max_steering_angle_deg,
    )
    birds_eye, hud = _create_renderer(width, height, params, game_params)

    running = True
    accumulator = 0.0
    while running:
        frame_dt = min(clock.tick(120) / 1000.0, game_params.physics_accumulator_limit)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        keys = pygame.key.get_pressed()
        controls.update(frame_dt, keys)
        accumulator += frame_dt

        # Fixed 100 Hz physics. Keyboard smoothing lives only in GameControls.
        while accumulator >= params.sim_dt:
            c = controls.state
            inputs = DriverInputs(
                throttle=c.throttle,
                brake_pressure_front=c.brake_pressure_front,
                brake_pressure_rear=c.brake_pressure_rear,
                brake_pedal_travel=c.brake_pedal_travel,
                steering_angle_deg=c.steering_angle_deg,
            )
            car.step(params.sim_dt, inputs)
            accumulator -= params.sim_dt
            birds_eye.add_point(car.state.x, car.state.y)

        birds_eye.draw(screen, car)
        hud.draw(screen, car, params, controls_help=True, mode="GAME")
        pygame.display.flip()

    pygame.quit()


def _result_from_rows(rows: dict[str, list[float]]) -> SimulationResult:
    return SimulationResult(
        {field: np.asarray(rows[field], dtype=float) for field in OUTPUT_FIELDS}
    )


def run_csv_replay(
    csv_path: str | Path,
    output_path: str | Path = "simulation_output.csv",
    width: int = 1200,
    height: int = 800,
) -> SimulationResult:
    """Run CSV simulation inside pygame as an automatic, non-interactive replay.

    CSV inputs are interpolated to the fixed 100 Hz simulation grid and applied
    directly to the shared Car physics. No keyboard controls or GameControls
    smoothing is used. One rendered frame corresponds to one physics timestep.
    """
    inputs = load_driver_csv(csv_path)
    params = CarParams()
    game_params = GameParams()

    pygame.init()
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Unified Car Physics Simulator — CSV Replay")
    clock = pygame.time.Clock()

    birds_eye, hud = _create_renderer(width, height, params, game_params)

    rows: dict[str, list[float]] = {field: [] for field in OUTPUT_FIELDS}
    running = True
    interrupted = False

    def record(time_value: float, car: Car) -> None:
        snapshot = car.state.as_dict()
        # Keep the recorded timeline synchronized with the actual yielded state.
        snapshot["time"] = time_value
        for field in OUTPUT_FIELDS:
            rows[field].append(float(snapshot[field]))

    try:
        for time_value, car in iter_simulation_states(inputs, params=params):
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                # All player driving keys are deliberately ignored in replay mode.

            if not running:
                interrupted = True
                break

            birds_eye.add_point(car.state.x, car.state.y)
            record(time_value, car)

            birds_eye.draw(screen, car)
            hud.draw(screen, car, params, controls_help=False, mode="CSV REPLAY")
            pygame.display.flip()

            # SIM_DT is 0.01 s, so 100 FPS displays the replay at real-time speed.
            clock.tick(round(1.0 / params.sim_dt))
    finally:
        pygame.quit()

    result = _result_from_rows(rows)
    save_simulation_csv(result, output_path)

    status = "stopped early" if interrupted else "complete"
    print(f"CSV replay {status}: {len(result.time)} samples")
    if len(result.time):
        print(f"Duration: {result.time[-1]:.3f} s")
        print(
            f"Final speed: {result['speed'][-1]:.3f} m/s "
            f"({result['speed'][-1] * 3.6:.3f} km/h)"
        )
        print(
            f"Final position: x={result['x'][-1]:.3f} m, "
            f"y={result['y'][-1]:.3f} m"
        )
    print(f"Saved: {output_path}")
    return result