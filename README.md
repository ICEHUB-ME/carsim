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
- `A` — smoothly steer left toward -30°
- `D` — smoothly steer right toward +30°
- `A` — smoothly steer toward `-30°`
- `D` — smoothly steer toward `+30°`
- neutral steering — smoothly return toward `0°`
- releasing `W` smoothly returns throttle toward 0
- releasing `S`/`SPACE` smoothly returns brake pedal travel and brake pressures toward 0
- releasing `A`/`D` smoothly returns steering toward 0°
- `ESC` — quit

Input smoothing rates are:

- throttle: `2.0 / s`
- brake pedal and brake pressures: `2.0 / s`
- steering: `90° / s`

Physics remains fixed at `0.01 s` per update even though rendering runs independently.

## Run CSV simulation

```bash
python main.py sim examples/straight_acceleration.csv
```

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

The tests cover the reference torque model, back-EMF model, brake mapping, lateral grip limit, forward-only braking, and 100 Hz CSV interpolation.

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
