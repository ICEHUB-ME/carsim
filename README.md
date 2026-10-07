# Unified Car Physics Simulator

A modular, forward-only Python car simulator with two modes:

1. **Game mode (`pygame`)** — fixed-step physics at 100 Hz, smooth keyboard controls, bird's-eye view, travelled path, and HUD.
2. **Simulation mode (CSV)** — interpolates driver inputs onto the same 0.01 s grid and writes a complete physics time series to `simulation_output.csv`.

## Finalized model

### Main propulsion
The **back-EMF propulsion model** is the production model:

`propulsionForce = maxPropulsionForce * throttle * max(0, 1 - speed / vmax)`

with `maxPropulsionForce = 2000 N` and `vmax = 27 m/s`.

### Part 1 diagnostic model
The torque model is retained only for reference:

`commandTorque = throttle * maxMotorTorque`

`wheelForce = commandTorque * gearRatio / wheelRadius`

`acceleration = wheelForce / mass`

Defaults: `180 Nm`, `3:1`, `0.216 m`, `300 kg`.

### Lateral dynamics

`slipAngle = steerAngle(rad) - lateralVelocity / max(abs(speed), epsilon)`

`lateralForce = clamp(corneringStiffness * slipAngle, -maxGrip, +maxGrip)`

`lateralAcceleration = lateralForce / mass`

`lateralVelocity += lateralAcceleration * dt`

`maxGrip = frictionCoefficient * normalForce`

with `normalForce = mass * 9.81` and `frictionCoefficient = 1.0`.

### Longitudinal resistance

`drag = 0.5 * area * dragCoefficient * airDensity * speed^2`

`rollingResistance = rollingResistanceCoefficient * normalForce` while moving.

Net longitudinal force is:

`propulsion - drag - rollingResistance - braking`

### Braking

`frontBrake = brakePressureFront * brakePedalTravel`

`rearBrake = brakePressureRear * brakePedalTravel`

`rawBrakingForce = maxBrakingCapacity * (0.7 * frontBrake + 0.3 * rearBrake)`

`brakingForce = min(rawBrakingForce, frictionCoefficient * normalForce)`

All three brake inputs are normalized to `[0, 1]`.

### Heading / position

The selected simple yaw model is used:

`x += forwardVelocity * cos(heading) * dt`

`y += forwardVelocity * sin(heading) * dt`

`yawRate = lateralVelocity / max(forwardVelocity, small_value)`

`heading += yawRate * dt`

No bicycle model, load transfer, aero downforce, reverse, or combined friction circle is implemented yet.

## Architecture

```text
car_physics_simulator/
├── main.py
├── run_sim.py
├── car.py
├── config.py
├── simulation.py
├── matplotlib_animation_example.py
├── physics/
│   ├── throttle.py
│   ├── motor.py
│   ├── drag.py
│   ├── traction.py
│   ├── braking.py
│   └── rolling_resistance.py
├── input/
│   ├── csv_loader.py
│   ├── interpolation.py
│   └── game_controls.py
├── visual/
│   ├── birds_eye.py
│   ├── hud.py
│   └── pygame_renderer.py
├── examples/
│   ├── straight_acceleration.csv
│   ├── braking_turn.csv
│   └── low_rate_input.csv
└── tests/
    └── test_physics.py
```

The important architectural rule is that **both modes use the same `Car.step()` implementation**. That prevents the interactive game and CSV simulation from developing two subtly different physics models.

## Install

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## Run game mode

From the project directory:

```bash
python main.py game
```

Controls:

- `W` — smoothly increase throttle toward 100%
- `S` — smoothly increase brake pedal travel and both brake pressures toward 100%
- `SPACE` — same brake action as `S`
- `A` — smoothly steer **right** toward `+30°`
- `D` — smoothly steer **left** toward `-30°`
- releasing `W` smoothly returns throttle toward 0
- releasing `S`/`SPACE` smoothly returns brake pedal travel and brake pressures toward 0
- releasing `A`/`D` smoothly returns steering toward 0°
- `T` — toggle real-time animation / frame-step mode
- `F` — when frame-step mode is active, advance **exactly one physics frame** (`0.01 s`)
- `M` — toggle manual throttle/brake override
- `TAB` — select manual throttle or brake field
- `0-9` — type a manual percentage; `ENTER` applies it (0-100%)
- `BACKSPACE` — erase the current manual percentage entry
- `ESC` — quit

Manual pedal entry is direct and does not use smoothing. In game mode, W/S are ignored while manual mode is active. In CSV replay, M enables a manual override for only throttle/brake; steering remains controlled by the CSV.

Input smoothing rates are:

- throttle: `2.0 / s`
- brake pedal and brake pressures: `2.0 / s`
- steering: `90° / s`

Physics remains fixed at `0.01 s` per update even though rendering runs independently.

## Run CSV simulation / replay

```bash
python main.py sim examples/straight_acceleration.csv
```

CSV mode opens the pygame window and automatically replays the interpolated 100 Hz timeline. Player driving keys (`W/S/A/D/SPACE`) are ignored. `T` pauses/resumes frame-step mode, `F` advances one physics frame at a time, and `M` enables a manual throttle/brake override.

or:

```bash
python run_sim.py examples/braking_turn.csv -o simulation_output.csv
```

The CSV input must contain:

```text
time,throttle,brakePressureFront,brakePressureRear,brakePedalTravel,steerAngle
```

`steerAngle` is in degrees. The input series is linearly interpolated to the 100 Hz simulation grid.

## Output arrays

`simulate_csv()` returns a `SimulationResult` whose fields are NumPy arrays:

```python
result.time
result.x
result.y
result["speed"]
result["acceleration"]
result["lateral_velocity"]
result["lateral_acceleration"]
result["slip_angle"]
result["steering_angle"]
result["throttle"]
result["brake_pedal"]
result["brake_pressure_front"]
result["brake_pressure_rear"]
result["propulsion_force"]
result["drag_force"]
result["rolling_resistance"]
result["braking_force"]
result["lateral_force"]
```

`result.to_matplotlib_arrays()` returns the arrays in exactly the CSV output order, which makes it easy to adapt to a `matplotlib.animation.FuncAnimation` template.

A ready-to-run example is included as `matplotlib_animation_example.py`.

## CSV output

`simulation_output.csv` contains:

```text
time, x, y, heading, speed, acceleration, lateral_velocity,
lateral_acceleration, slip_angle, steering_angle, throttle,
brake_pedal, brake_pressure_front, brake_pressure_rear,
propulsion_force, drag_force, rolling_resistance, braking_force,
lateral_force
```

Angles in output are radians for `slip_angle` and `heading`, while `steering_angle` remains degrees. This matches the input convention and keeps the physical equations explicit.

## Validation

Run:

```bash
python -m unittest discover -s tests
```

The tests cover the reference torque model, back-EMF model, brake mapping, lateral grip limit, forward-only braking, 100 Hz CSV interpolation, game-input smoothing, steering direction, manual pedal entry, and replay/headless consistency.

## Extension points

The current design makes later upgrades localized. Examples include:

- combined longitudinal/lateral friction circle
- front/rear tire loads and load transfer
- wheel-speed state and individual tire slip
- bicycle-model yaw dynamics
- drivetrain gears and motor torque curves
- ABS / brake bias control
- regenerative braking
- reverse
- richer track/world rendering

## CSV replay mode

The `sim` mode now opens pygame and replays the CSV automatically through the
same `Car` physics, bird's-eye renderer, HUD, and pedal widgets used by game mode.
CSV inputs are interpolated to the fixed 0.01 s simulation grid and applied
directly; `GameControls` is not constructed, so W/S/A/D/Space do nothing.

```bash
python main.py sim examples/braking_turn.csv
```

Optional replay window size and output path:

```bash
python main.py sim examples/braking_turn.csv --width 1400 --height 900 -o replay_output.csv
```

During replay, ESC or closing the window stops playback. The output CSV contains
the states rendered up to that point.

## Game-mode CSV recording

Game mode records the initial state and every physics timestep to a CSV file using the same 19-column schema as CSV simulation/replay mode.

```bash
python main.py game -o game_simulation_output.csv
```

The default output file is `game_simulation_output.csv`. The `-o/--output` option can be used to choose another path.

The recorded `throttle` and `brake_pedal` columns remain normalized to `[0, 1]`, matching the existing CSV simulation format; the HUD displays them as percentages.

## Project layout and `csv_output.py` location

`csv_output.py` belongs **at the project root**, alongside `main.py`, `simulation.py`, `car.py`, and `config.py`:

```text
car_physics_simulator/
├── main.py
├── run_sim.py
├── car.py
├── config.py
├── simulation.py
├── csv_output.py          # shared CSV output module
├── physics/
├── input/
├── visual/
├── examples/
└── tests/
```

### Import rule

This project is designed to be launched with script-style commands such as:

```bash
python main.py game
python main.py sim examples/braking_turn.csv
python run_sim.py examples/braking_turn.csv
```

For that reason, project modules use the root-level absolute import:

```python
from csv_output import OUTPUT_FIELDS, rows_to_columns, save_simulation_csv
```

Do **not** change this to `from .csv_output import ...` unless the entire project is converted to a package and launched with `python -m ...`. Using a leading-dot relative import while running `main.py` directly causes `ImportError: attempted relative import with no known parent package`.

Both game mode and CSV simulation/replay use the same `csv_output.py` functions, so there is only one CSV output implementation to maintain.

## Manual steering override

`K` toggles manual steering mode. While it is ON, A/D do not change steering and the angle is held directly at the manually entered value. Use `-` for negative angles and `ENTER` to apply, with the value clamped to ±30°.

Manual text entry uses `TAB` to cycle through active fields. With manual pedals and manual steering both enabled, the fields are `THROTTLE`, `BRAKE`, and `STEERING`.

Game mode controls: `A = right/positive`, `D = left/negative`; steering smoothing is 90°/s when manual steering is OFF. CSV replay keeps CSV steering unless manual steering mode is explicitly enabled.
