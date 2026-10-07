"""Pygame game mode and automatic/manual CSV replay mode."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pygame

from car import Car, DriverInputs
from config import CarParams, GameParams
from csv_output import OUTPUT_FIELDS, rows_to_columns, save_simulation_csv
from input.csv_loader import load_driver_csv
from input.game_controls import GameControls
from simulation import SimulationResult, iter_simulation_inputs
from visual.birds_eye import BirdsEyeRenderer
from visual.hud import HUD


class PlaybackControls:
    """Common real-time/frame-step toggle state for game and CSV replay."""

    def __init__(self) -> None:
        self.step_mode = False
        self._step_requested = False

    def handle_event(self, event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_t:
            self.step_mode = not self.step_mode
            self._step_requested = False
        elif event.key == pygame.K_f and self.step_mode:
            self._step_requested = True

    def consume_step(self) -> bool:
        if not self.step_mode or not self._step_requested:
            return False
        self._step_requested = False
        return True


def _create_renderer(width: int, height: int, game_params: GameParams):
    birds_eye = BirdsEyeRenderer(
        width,
        height,
        pixels_per_meter=game_params.pixels_per_meter,
        max_path_points=game_params.path_max_points,
    )
    return birds_eye, HUD()


def _draw_frame(
    screen,
    birds_eye,
    hud,
    car,
    params,
    *,
    controls=None,
    mode="GAME",
    step_mode=False,
) -> None:
    birds_eye.draw(screen, car)
    hud.draw(
        screen,
        car,
        params,
        controls_help=(controls is not None and mode == "GAME"),
        mode=mode,
        step_mode=step_mode,
        manual_controls=controls,
    )
    pygame.display.flip()


def _game_driver_inputs(controls: GameControls) -> DriverInputs:
    state = controls.state
    return DriverInputs(
        throttle=state.throttle,
        brake_pressure_front=state.brake_pressure_front,
        brake_pressure_rear=state.brake_pressure_rear,
        brake_pedal_travel=state.brake_pedal_travel,
        steering_angle_deg=state.steering_angle_deg,
    )


def _manual_override_inputs(csv_inputs: DriverInputs, controls: GameControls) -> DriverInputs:
    """Override only CSV throttle/brake fields while manual mode is enabled."""
    manual = controls.manual_driver_values()
    if manual is None:
        return csv_inputs
    throttle, brake = manual
    return replace(
        csv_inputs,
        throttle=throttle,
        brake_pressure_front=brake,
        brake_pressure_rear=brake,
        brake_pedal_travel=brake,
    )


def _new_output_rows() -> list[dict[str, float]]:
    """Create row-oriented output storage shared by game and replay modes."""
    return []


def _record_car_state(rows: list[dict[str, float]], car: Car) -> None:
    """Append an immutable-in-practice snapshot as one dictionary row.

    A fresh dict is required here because ``car.state`` is replaced on every
    physics step. Keeping snapshots row-oriented also matches ``rows_to_columns``.
    """
    snapshot = car.state.as_dict()
    rows.append({field: float(snapshot[field]) for field in OUTPUT_FIELDS})


def _result_from_rows(rows: list[dict[str, float]]) -> SimulationResult:
    """Convert row-oriented game/replay snapshots to the column-oriented result."""
    return SimulationResult(rows_to_columns(rows))


def run_game(
    width: int = 1200,
    height: int = 800,
    output_path: str | Path = "game_simulation_output.csv",
) -> SimulationResult:
    """Run interactive keyboard-controlled game mode and record every physics step."""
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
    playback = PlaybackControls()
    birds_eye, hud = _create_renderer(width, height, game_params)
    rows = _new_output_rows()

    # Record t=0 so game output has the same schema and initial state convention
    # as CSV simulation output.
    _record_car_state(rows, car)

    running = True
    accumulator = 0.0
    try:
        while running:
            frame_dt = min(
                clock.tick(120) / 1000.0,
                game_params.physics_accumulator_limit,
            )

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                else:
                    playback.handle_event(event)
                    controls.handle_event(event)

            keys = pygame.key.get_pressed()

            if playback.step_mode:
                # Paused: only F advances exactly one physics frame.
                if playback.consume_step():
                    controls.update(params.sim_dt, keys)
                    car.step(params.sim_dt, _game_driver_inputs(controls))
                    birds_eye.add_point(car.state.x, car.state.y)
                    _record_car_state(rows, car)
                accumulator = 0.0
            else:
                controls.update(frame_dt, keys)
                accumulator += frame_dt
                while accumulator >= params.sim_dt:
                    car.step(params.sim_dt, _game_driver_inputs(controls))
                    accumulator -= params.sim_dt
                    birds_eye.add_point(car.state.x, car.state.y)
                    _record_car_state(rows, car)

            _draw_frame(
                screen,
                birds_eye,
                hud,
                car,
                params,
                controls=controls,
                mode="GAME",
                step_mode=playback.step_mode,
            )
    finally:
        pygame.quit()

    result = _result_from_rows(rows)
    save_simulation_csv(result, output_path)

    print(f"Game session recorded: {len(result.time)} samples")
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


def run_csv_replay(
    csv_path: str | Path,
    output_path: str | Path = "simulation_output.csv",
    width: int = 1200,
    height: int = 800,
) -> SimulationResult:
    """Replay a CSV simulation inside pygame with optional frame-step/manual pedals.

    CSV values are interpolated onto the fixed simulation timeline and are used
    directly. No game smoothing is applied to CSV inputs. W/S/A/D/Space do not
    control the car in replay mode; T/F control playback and M enables the
    manual throttle/brake override.
    """
    csv_series = load_driver_csv(csv_path)
    params = CarParams()
    game_params = GameParams()
    timeline = list(iter_simulation_inputs(csv_series, params=params))
    if not timeline:
        raise ValueError("CSV input contains no simulation timesteps")

    pygame.init()
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Unified Car Physics Simulator — CSV Replay")
    clock = pygame.time.Clock()

    birds_eye, hud = _create_renderer(width, height, game_params)
    playback = PlaybackControls()
    controls = GameControls(
        throttle_rate=game_params.throttle_rate,
        brake_rate=game_params.brake_rate,
        steering_rate_deg=game_params.steering_rate_deg,
        max_steering_angle_deg=params.max_steering_angle_deg,
    )
    car = Car(params)
    rows = _new_output_rows()

    running = True
    interrupted = False
    frame_index = 0

    def advance_one_frame() -> bool:
        nonlocal frame_index
        if frame_index >= len(timeline) - 1:
            return False
        next_time, csv_driver = timeline[frame_index + 1]
        effective_driver = _manual_override_inputs(csv_driver, controls)
        car.step(next_time - car.state.time, effective_driver)
        frame_index += 1
        birds_eye.add_point(car.state.x, car.state.y)
        _record_car_state(rows, car)
        return True

    try:
        birds_eye.add_point(car.state.x, car.state.y)
        _record_car_state(rows, car)

        while running and frame_index < len(timeline):
            clock.tick(120 if playback.step_mode else round(1.0 / params.sim_dt))

            current_csv_driver = timeline[frame_index][1]
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                else:
                    playback.handle_event(event)
                    # M/manual input is allowed in replay. All driving keys are ignored.
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_m:
                        controls.handle_event(
                            event,
                            current_throttle=current_csv_driver.throttle,
                            current_brake=current_csv_driver.brake_pedal_travel,
                        )
                    else:
                        controls.handle_event(event)

            if not running:
                interrupted = True
                break

            if playback.step_mode:
                if playback.consume_step():
                    advance_one_frame()
            else:
                advance_one_frame()

            _draw_frame(
                screen,
                birds_eye,
                hud,
                car,
                params,
                controls=controls,
                mode="CSV REPLAY",
                step_mode=playback.step_mode,
            )

            if frame_index >= len(timeline) - 1:
                # Keep the final frame visible until the user closes the window.
                while running:
                    clock.tick(30)
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            running = False
                        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                            running = False
                    _draw_frame(
                        screen,
                        birds_eye,
                        hud,
                        car,
                        params,
                        controls=controls,
                        mode="CSV COMPLETE",
                        step_mode=playback.step_mode,
                    )
                break
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
