# Car Physics Simulator

A forward-only Python vehicle simulator with an interactive driving mode and a CSV-driven simulation mode. Both modes use the same `Car.step()` physics update.

## Features

- Fixed-step physics at 0.01 seconds (100 Hz) by default
- Pygame top-down view, distance grid, and HUD
- CSV control replay and simulation result recording
- `generate_csv.py` creates throttle, brake, and steering inputs for a waypoint track
- Vehicle, control, simulation, and rendering settings are defined with dataclasses in `config.py`

## Setup

Create a virtual environment and install the dependencies from the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Running the simulator

### Interactive game mode

```powershell
python main.py game
```

- `W`: increase throttle
- `S` / `SPACE`: apply the brakes
- `A` / `D`: steer left / right
- `T`: toggle real-time playback and frame-step mode
- `F` while frame-stepping: advance one physics frame
- `M`: toggle manual pedal input
- `K`: toggle manual steering input
- `ESC`: quit

Use `--width`, `--height`, and `-o` to set the window size and recording path.

### Replay control inputs from CSV

```powershell
python main.py sim examples/braking_turn.csv
```

Set the initial vehicle heading in degrees when the track does not begin along the positive X axis:

```powershell
python main.py sim examples/braking_turn.csv --initial-heading-deg 90
```

To run a simulation without the Pygame replay window:

```powershell
python run_sim.py examples/braking_turn.csv -o simulation_output.csv
```

The input CSV must contain these columns. Steering is in degrees; pedal values are normalized to the range 0–1. Input samples are linearly interpolated onto the fixed simulation time step.

```text
time,throttle,brakePressureFront,brakePressureRear,brakePedalTravel,steerAngle
```

## Generating track-following inputs

`generate_csv.py` turns an ordered list of track coordinates into driver control inputs:

```powershell
python generate_csv.py
python generate_csv.py my_track.csv
```

With no argument, the script uses the `TRACK` list in the file. A track CSV may provide `x,y` or `track_x,track_y` columns; otherwise its first two columns are treated as x and y. Coordinates are in meters, and row order defines the route order. The path is closed automatically by connecting the last point to the first. At least four distinct waypoints are required.

Set the output path with `OUTPUT_FILE` and the number of laps with `NUM_LAPS` near the top of the script. The generator writes a six-column control-input CSV. This is a different schema from the 19-column simulation-state output.

After generation, the script prints the initial heading that aligns the simulated car with the first track segment. If the track does not start along +X, pass that angle when replaying the generated CSV. For example, if the reported initial heading is 90 degrees:

```powershell
python main.py sim generate_natural_3laps.csv --initial-heading-deg 90
```

The input waypoints are smoothed by a periodic cubic spline. The resulting path passes smoothly near sharp corners rather than following each corner as a sharp polyline turn. `USE_RACING_LINE=False` by default, so the route is not offset from the supplied centerline.

## How `generate_csv.py` calculates the controls

The generator does not simply write the waypoint coordinates into a file. It builds a path and speed plan, drives the actual vehicle model in a feedback loop, and records the resulting controls.

### 1. Convert the track into an evenly spaced path

The ordered waypoints are connected, including the final-to-first segment. A periodic cubic spline is parameterized by distance between waypoints, sampled densely, and then resampled at roughly one-meter intervals along its arc length. The path distance `s` is therefore measured in meters.

### 2. Estimate path heading and curvature

The tangent direction `theta` is estimated from neighboring path points. The change in tangent direction divided by the distance gives an approximate curvature:

```text
kappa ≈ Δtheta / Δs        [1/m]
```

Positive curvature represents a left turn. Gaussian smoothing reduces noise from the discrete points. A forward window of about eight meters also considers the highest upcoming curvature, helping the speed plan account for a corner before the car reaches it.

### 3. Plan a speed for every path point

The local speed limit is constrained by both the steering range and lateral acceleration:

```text
v_steer = 0.80 × max_steering_angle_rad / |kappa|
v_grip  = sqrt(7.0 m/s² / |kappa|)
v_limit = min(v_steer, v_grip, 24.0 m/s)
```

Higher curvature therefore means a lower target speed. A small curvature floor avoids division by zero on straights.

The generator then makes repeated passes around the closed route. A backward pass limits speed so the car can brake before the next slower section:

```text
v_here <= sqrt(v_next² + 2 × a_brake × Δs)
```

The planned braking deceleration is 3.8 m/s². A forward pass limits speed to what the motor can reach after drag and rolling resistance:

```text
a_available = 0.90 × (propulsion(1, v) - drag(v) - rolling_resistance(v)) / mass
v_next <= sqrt(v_here² + 2 × a_available × Δs)
```

Repeating these passes produces a speed profile that slows for corners and accelerates where the available distance and motor force permit.

### 4. Close the steering loop around the simulated car

The generator creates a `Car` and advances it with `Car.step()` at every physics time step. It finds the nearest path point near the previous progress index, and searches the whole route again if the car is too far away. From that point it calculates the lateral offset and heading error.

In this simulator's lateral model, steady-state yaw rate is approximately equal to the steering angle in radians. The feed-forward steering term is therefore:

```text
steer_ff = kappa_preview × speed       [rad]
```

Feedback from heading error `e_psi` and lateral error `e_y` corrects the feed-forward command:

```text
u_fb = -(2 ζ ω × e_psi + (ω² / max(speed, 5)) × e_y) × speed_gain
steer_command = degrees(steer_ff + u_fb)
```

The defaults are `ω=0.8` and `ζ=0.9`. The command is reduced at low speed and constrained by the maximum steering angle and steering rate. Preview time accounts for lateral response delay and adds extra lead for earlier turn-in.

### 5. Convert speed error into throttle or brake

The controller looks slightly ahead along the speed plan. It combines the planned speed gradient with the difference between target and actual speed to calculate desired acceleration:

```text
a_des = speed × dv/ds + 1.5 × (v_ref - speed)
```

Desired acceleration is limited to -6 through 4 m/s². The requested net drive force includes the force needed to overcome drag and rolling resistance:

```text
F_net = mass × a_des + drag + rolling_resistance
```

For nonnegative `F_net`, throttle is estimated as the required force divided by the available full-throttle propulsion force at the current speed. Curvature-dependent throttle caps and floors adjust the driving style. For negative `F_net`, the generator uses bisection to find the brake input that produces the requested braking force under the same braking model as the simulator.

Small brake requests are ignored so the car can coast. Separate brake engagement and release thresholds reduce rapid on/off changes. The controller also limits input rates and prevents throttle from remaining active while braking.

### 6. Apply and record the controls

Each calculated command is passed to `Car.step()`. The next control update uses the car's newly simulated position and speed, so steering and speed control respond to tracking errors instead of relying only on the precomputed plan. The generator records `time,throttle,brakePressureFront,brakePressureRear,brakePedalTravel,steerAngle` at the configured time step, defaulting to 0.01 seconds, until the requested lap distance is complete.

## Physics model overview

- Propulsion decreases as speed approaches the configured maximum speed (a back-EMF model).
- Aerodynamic drag grows with the square of speed; rolling resistance depends on the configured coefficient and normal force.
- Lateral tire force is computed from cornering stiffness and limited by maximum grip.
- Braking force is calculated from brake commands and capped by maximum grip.
- Position is advanced from heading and speed. Reverse, load transfer, and a combined friction circle are not currently modeled.

Vehicle parameters are defined by `CarParameters` in `config.py`. Rendering scale and grid distance are available through `PlotConfig` / `GameConfig`; `pixels_per_meter` controls screen scale, while `grid_spacing_m` controls the real-world distance between grid lines.

## Project layout

```text
car_physics_simulator/
├── main.py                     # Game and Pygame replay entry point
├── run_sim.py                  # Headless CSV simulation entry point
├── generate_csv.py             # Track-to-control-input generator
├── config.py                   # Dataclass configuration
├── car.py                      # Car and compatibility input API
├── simulation/
│   ├── state.py                # Vehicle state and simulation result
│   ├── step.py                 # One physics step
│   └── simulate.py             # CSV-driven simulation
├── physics/                    # Force, propulsion, and braking models
├── input/                      # CSV loading, interpolation, game controls
├── visual/                     # Top-down view, HUD, and Pygame rendering
├── csv_output.py               # Existing 19-column simulation output
├── examples/                   # Sample input CSV files
└── tests/                      # Physics and control tests
```

Game and CSV simulation share the same vehicle-step implementation. Physics, input handling, and rendering have separate modules; `generate_csv.py` reuses the physics functions and vehicle step instead of implementing another vehicle model.

## Tests

```powershell
python -m unittest discover -s tests -v
```

## CSV output formats

Game recording and simulation results use the existing 19-column schema containing position, velocity, and forces. `generate_csv.py` writes a separate six-column control-input schema for replay. It does not add or change the simulation-state output columns.
