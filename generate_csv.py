#!/usr/bin/env python3
"""
generate_csv.py -- driver-input generator for the car physics simulator.

Produces a 3-lap CSV of CONTROL INPUTS ONLY:

    time,throttle,brakePressureFront,brakePressureRear,brakePedalTravel,steerAngle

The simulator ignores x/y from the CSV and integrates its own physics, so this
script turns a track polyline into steering / throttle / brake commands that
make that physics follow the track.

Pipeline
--------
 1. track polyline  -> periodic cubic spline -> dense, evenly spaced points
 2. racing line     -> minimum-curvature offset inside the track width
                       (early turn-in, clipping the apex, wide exit)
 3. curvature       -> from heading changes between consecutive points, smoothed
 4. speed profile   -> corner speed limits + braking / acceleration passes
 5. controls        -> steering (curvature feed-forward + preview + feedback),
                       throttle (95-100 % straights, 40-70 % medium corners,
                       20-40 % tight corners), front-biased brakes
 6. CSV             -> 100 Hz, three continuous laps, no resets, no jumps

How the steering is scaled
--------------------------
The simulator's lateral model is:
    slip      = steer - vy / v
    vy       += (Ca * slip / m) * dt        (force clamped to the grip limit)
    yaw rate  = vy / v
At steady state slip -> 0, so vy -> steer * v and yaw rate -> steer (rad/s),
independent of speed.  Following a path of curvature k at speed v therefore
needs   steer = k * v   (radians).  Small angles (0.1-2 deg) only give
0.002-0.035 rad/s of yaw rate, which is why steering must be strong, and why
the speed profile is limited so that  k * v  never exceeds the +-30 deg range.

Physics engine usage
--------------------
Nothing is re-implemented here.  The script imports the simulator itself:
    car.Car / car.DriverInputs        -> the exact integrator used by main.py
    config.CarParams                  -> mass, grip, stiffness, limits
    physics.motor.propulsion_force    -> throttle -> force (back-EMF model)
    physics.braking.braking_force     -> pedal/pressures -> braking force
    physics.drag / rolling_resistance -> resistive forces
A Car instance is driven step-by-step with the very commands being written to
the CSV, so the CSV replays to the same trajectory in main.py / run_sim.py.
(This codebase has no steering.py / dynamics.py / tire.py; the lateral model
lives in physics/traction.py and car.py.)

Run it from the simulator root (or keep it there) so the imports resolve.

Usage:
    python generate_csv.py                 # uses TRACK below
    python generate_csv.py my_track.csv    # CSV with x,y columns (no/with header)

Sign convention: positive steerAngle increases heading (counter-clockwise in
x-y, i.e. a left turn when +x is forward and +y is left).  The track is
translated/rotated so the first point is the origin and the first segment
points along +x, because the simulator always starts at x=0, y=0, heading=0.
"""

import csv
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

from car import Car, DriverInputs                                  # noqa: E402
from config import CarParams                                       # noqa: E402
from physics.braking import braking_force as engine_braking_force  # noqa: E402
from physics.drag import drag_force                                # noqa: E402
from physics.motor import propulsion_force                         # noqa: E402
from physics.rolling_resistance import rolling_resistance_force    # noqa: E402

# ============================================================================
# USER SETTINGS
# ============================================================================
OUTPUT_FILE = "generate_natural_3laps.csv"
NUM_LAPS = 3

# Centerline of the track (x, y) in metres.  The loop is closed automatically
# (last point connects back to the first).  Replace with your own polyline.
TRACK = [
    (0, 0), (0,240), (120, 0), (165, 5), (200, 25), (210, 60),
    (195, 90), (160, 100), (125, 95), (100, 115), (95, 150),
    (75, 175), (40, 180), (10, 165), (-5, 135), (10, 105),
    (35, 85), (30, 55), (5, 30),
]

TRACK_HALF_WIDTH = 6.0          # m, centerline to edge
CAR_MARGIN = 1.5                # m, keep this far from the edge
USE_RACING_LINE = True

# ---------------------------------------------------------------------------
# Vehicle parameters come straight from the simulator's config.py
# ---------------------------------------------------------------------------
P = CarParams()
MASS = P.mass
MAX_STEER_DEG = P.max_steering_angle_deg
DT = P.sim_dt                   # 0.01 s (100 Hz)

# ---------------------------------------------------------------------------
# Driving style
# ---------------------------------------------------------------------------
STEER_USE = 0.80                # fraction of 30 deg the speed plan may use
A_LAT_MAX = 7.0                 # m/s^2 comfortable lateral accel (k v^2)
V_TOP = 24.0                    # m/s plan ceiling (above full-throttle limit)
A_BRAKE_PLAN = 3.8              # m/s^2 planned braking decel
A_ACCEL_SCALE = 0.90            # fraction of available accel the plan assumes
KAPPA_SMOOTH_M = 5.0            # m, Gaussian smoothing of curvature
KAPPA_MAX_WINDOW_M = 8.0        # m, window for corner-speed "max filter"

# Throttle envelope vs |curvature| (1/m)
THR_K = [0.003, 0.008, 0.016, 0.025, 0.040]
THR_CAP = [1.00, 0.70, 0.55, 0.40, 0.30]
THR_FLOOR = [0.95, 0.45, 0.40, 0.22, 0.20]

# Brakes: front-biased 2:1.  At light braking this is 40 % front / 20 % rear.
BRAKE_FRONT_MIN = 0.40
BRAKE_REAR_RATIO = 0.5
BRAKE_ENGAGE_N = 150.0          # ignore tiny brake demands (coast instead)
BRAKE_RELEASE_N = 50.0          # hysteresis: release only below this demand

# Actuator smoothing (per second)
THR_RATE_UP, THR_RATE_DOWN = 3.0, 6.0
BRK_RATE_UP, BRK_RATE_DOWN = 4.0, 5.0
STEER_TAU = 0.05                # s, first-order steering filter
STEER_RATE_DEG = 200.0          # deg/s steering slew limit

# Path-tracking feedback (closes the loop on the real Car)
FB_OMEGA_N = 0.8
FB_ZETA = 0.9
STEER_LEAD_EXTRA = 0.15         # s, extra preview => early turn-in

CTRL_DS = 1.0                   # m, spacing of the control path


# ============================================================================
# Geometry helpers
# ============================================================================
def _wrap(a):
    return (a + np.pi) % (2.0 * np.pi) - np.pi


def _periodic_spline_coeffs(t, y):
    """Second derivatives of a periodic natural cubic spline. t has n+1 knots."""
    n = len(t) - 1
    h = np.diff(t)
    A = np.zeros((n, n))
    rhs = np.zeros(n)
    for i in range(n):
        im = (i - 1) % n
        ip = (i + 1) % n
        A[i, im] += h[im]
        A[i, i] += 2.0 * (h[im] + h[i])
        A[i, ip] += h[i]
        rhs[i] = 6.0 * ((y[ip] - y[i]) / h[i] - (y[i] - y[im]) / h[im])
    M = np.linalg.solve(A, rhs)
    return np.append(M, M[0])


def _spline_eval(t, y, M, tq):
    idx = np.clip(np.searchsorted(t, tq, side="right") - 1, 0, len(t) - 2)
    h = t[idx + 1] - t[idx]
    a = (t[idx + 1] - tq) / h
    b = (tq - t[idx]) / h
    return (a * y[idx] + b * y[idx + 1]
            + ((a ** 3 - a) * M[idx] + (b ** 3 - b) * M[idx + 1]) * h * h / 6.0)


def resample_closed(points, ds):
    """Periodic cubic spline through points, resampled at uniform arc length."""
    p = np.asarray(points, dtype=float)
    if np.hypot(*(p[0] - p[-1])) < 1e-6:
        p = p[:-1]
    keep = np.r_[True, np.hypot(*np.diff(p, axis=0).T) > 1e-9]
    p = p[keep]
    pc = np.vstack([p, p[:1]])
    chord = np.r_[0.0, np.cumsum(np.hypot(*np.diff(pc, axis=0).T))]
    Mx = _periodic_spline_coeffs(chord, pc[:, 0])
    My = _periodic_spline_coeffs(chord, pc[:, 1])
    tf = np.linspace(0.0, chord[-1], max(20000, 40 * len(p)) + 1)
    xf = _spline_eval(chord, pc[:, 0], Mx, tf)
    yf = _spline_eval(chord, pc[:, 1], My, tf)
    arc = np.r_[0.0, np.cumsum(np.hypot(np.diff(xf), np.diff(yf)))]
    total = arc[-1]
    n = max(8, int(round(total / ds)))
    sq = np.arange(n) * (total / n)
    return np.interp(sq, arc, xf), np.interp(sq, arc, yf), total


def _gauss_smooth_circular(a, sigma_pts):
    if sigma_pts < 0.5:
        return a.copy()
    half = int(math.ceil(4 * sigma_pts))
    k = np.exp(-0.5 * (np.arange(-half, half + 1) / sigma_pts) ** 2)
    k /= k.sum()
    pad = np.concatenate([a[-half:], a, a[:half]]) if half < len(a) else np.tile(a, 3)
    if half >= len(a):
        half = len(a)
    return np.convolve(pad, k, mode="same")[half:half + len(a)]


def _max_filter_circular(a, half):
    out = a.copy()
    for k in range(1, half + 1):
        out = np.maximum(out, np.maximum(np.roll(a, k), np.roll(a, -k)))
    return out


def tangents_normals(x, y):
    dx = (np.roll(x, -1) - np.roll(x, 1)) * 0.5
    dy = (np.roll(y, -1) - np.roll(y, 1)) * 0.5
    nrm = np.hypot(dx, dy)
    tx, ty = dx / nrm, dy / nrm
    return tx, ty, -ty, tx


def minimum_curvature_line(x, y, max_offset, iters_lap=800, iters_bilap=5000):
    """Offset the centerline inside +-max_offset to minimise path curvature."""
    _, _, nx, ny = tangents_normals(x, y)
    qx, qy = x.copy(), y.copy()

    def project(qx, qy):
        off = np.clip((qx - x) * nx + (qy - y) * ny, -max_offset, max_offset)
        return x + off * nx, y + off * ny

    for _ in range(iters_lap):          # shortens the path (cuts corners)
        qx = qx + 0.4 * (0.5 * (np.roll(qx, 1) + np.roll(qx, -1)) - qx)
        qy = qy + 0.4 * (0.5 * (np.roll(qy, 1) + np.roll(qy, -1)) - qy)
        qx, qy = project(qx, qy)
    for _ in range(iters_bilap):        # flattens curvature (smooth line)
        d2x = np.roll(qx, 1) - 2 * qx + np.roll(qx, -1)
        d2y = np.roll(qy, 1) - 2 * qy + np.roll(qy, -1)
        gx = np.roll(d2x, 1) - 2 * d2x + np.roll(d2x, -1)
        gy = np.roll(d2y, 1) - 2 * d2y + np.roll(d2y, -1)
        qx = qx - 0.06 * gx
        qy = qy - 0.06 * gy
        qx, qy = project(qx, qy)
    return qx, qy


def curvature_from_points(x, y, ds):
    """Signed curvature (left/CCW positive) from heading change between points."""
    dx = (np.roll(x, -1) - np.roll(x, 1)) * 0.5
    dy = (np.roll(y, -1) - np.roll(y, 1)) * 0.5
    th = np.arctan2(dy, dx)
    dth = _wrap(np.roll(th, -1) - np.roll(th, 1))
    return th, dth / (2.0 * ds)


class Path:
    """Closed control path in the simulator frame (start at origin, heading 0)."""

    def __init__(self, track):
        # coarse resample -> optional racing line -> control-resolution resample
        x, y, total = resample_closed(track, 2.0)
        if USE_RACING_LINE:
            w = max(0.0, TRACK_HALF_WIDTH - CAR_MARGIN)
            x, y = minimum_curvature_line(x, y, w)
        x, y, total = resample_closed(np.column_stack([x, y]), CTRL_DS)

        self.n = len(x)
        self.ds = total / self.n
        self.length = total
        self.s = np.arange(self.n) * self.ds

        # Move into the simulator frame: start at (0,0), first heading = 0.
        th0 = math.atan2(y[1] - y[-1], x[1] - x[-1])
        c, s_ = math.cos(-th0), math.sin(-th0)
        xs, ys = x - x[0], y - y[0]
        self.x = c * xs - s_ * ys
        self.y = s_ * xs + c * ys

        theta, kappa = curvature_from_points(self.x, self.y, self.ds)
        sig = KAPPA_SMOOTH_M / self.ds
        self.kappa = _gauss_smooth_circular(kappa, sig)
        # heading from smoothed curvature (integrated) is avoided: use raw
        # heading from geometry, which is what the car must match.
        self.theta = theta

        half = max(1, int(round(KAPPA_MAX_WINDOW_M / self.ds)))
        self.kappa_eff = _gauss_smooth_circular(
            _max_filter_circular(np.abs(self.kappa), half), sig * 0.5)

    def at(self, arr, s):
        return float(np.interp(s % self.length, self.s, arr, period=self.length))


# ============================================================================
# Speed plan
# ============================================================================
def _drag(v):
    return drag_force(v, P.frontal_area, P.drag_coefficient, P.air_density)


def _roll(v):
    return rolling_resistance_force(P.rolling_resistance_coefficient, P.normal_force, v)


def _prop(throttle, v):
    return propulsion_force(throttle, v, P.max_propulsion_force, P.vmax)


def accel_full_throttle(v):
    return (_prop(1.0, v) - _drag(v) - _roll(v)) / MASS


def plan_speed(path):
    k = np.maximum(path.kappa_eff, 1e-6)
    v_steer = STEER_USE * math.radians(MAX_STEER_DEG) / k
    v_grip = np.sqrt(A_LAT_MAX / k)
    v = np.minimum(np.minimum(v_steer, v_grip), V_TOP)
    n, ds = path.n, path.ds

    for _ in range(3):
        for i in range(2 * n - 1, -1, -1):          # braking (backward)
            a, b = i % n, (i + 1) % n
            v[a] = min(v[a], math.sqrt(v[b] ** 2 + 2.0 * A_BRAKE_PLAN * ds))
        for i in range(2 * n):                       # acceleration (forward)
            a, b = i % n, (i + 1) % n
            acc = max(0.05, A_ACCEL_SCALE * accel_full_throttle(v[a]))
            v[b] = min(v[b], math.sqrt(v[a] ** 2 + 2.0 * acc * ds))
    dvds = (np.roll(v, -1) - np.roll(v, 1)) / (2.0 * ds)
    return v, dvds


def standing_start_table(ds, length):
    """Speed vs distance when accelerating at full throttle from rest."""
    s = [0.0]
    v = [0.0]
    vv = 0.0
    while s[-1] < length:
        acc = max(0.05, A_ACCEL_SCALE * accel_full_throttle(vv))
        vv = math.sqrt(vv * vv + 2.0 * acc * ds) if vv > 0 else math.sqrt(2.0 * acc * ds)
        s.append(s[-1] + ds)
        v.append(vv)
    return np.array(s), np.array(v)


# ============================================================================
# Braking helpers (force model = physics/braking.py)
# ============================================================================
def braking_force(front, rear, pedal):
    return engine_braking_force(front, rear, pedal,
                                P.max_braking_capacity, P.max_grip)


def brake_levels(u):
    """Pedal travel and front/rear pressures for a brake demand u in [0,1]."""
    u = min(1.0, max(0.0, u))
    ramp = min(1.0, u / 0.40)                         # pressure builds with pedal
    front = min(1.0, BRAKE_FRONT_MIN * ramp + (1.0 - BRAKE_FRONT_MIN) * u)
    return u, front, front * BRAKE_REAR_RATIO


def brake_demand_for_force(force):
    """Brake demand u that produces the requested braking force."""
    target = min(force, P.max_grip)
    lo, hi = 0.0, 1.0
    for _ in range(30):                               # monotonic -> bisection
        mid = 0.5 * (lo + hi)
        _, f, r = brake_levels(mid)
        if braking_force(f, r, mid) < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _slew(cur, target, up, down, dt):
    d = target - cur
    return cur + max(-down * dt, min(up * dt, d))


# ============================================================================
# Control generation
# ============================================================================
def generate_controls(path):
    v_plan, dvds = plan_speed(path)
    s_tab, v_tab = standing_start_table(1.0, path.length * 1.5)
    total_dist = NUM_LAPS * path.length

    car = Car(P)                                    # the real simulator car
    thr_s = bp_s = steer_s = 0.0
    braking_on = False
    idx_total = 0
    last_idx = 0
    n_pts = path.n
    win = np.arange(-20, 21)

    wn, zeta = FB_OMEGA_N, FB_ZETA
    k1 = 2.0 * zeta * wn
    rows = []
    max_steps = int(3000.0 / DT)
    tau_lat = MASS / P.cornering_stiffness          # lateral lag = v * tau_lat

    for i in range(max_steps):
        cs = car.state
        x, y, psi, v = cs.x, cs.y, cs.heading, cs.speed

        # ---- locate the car on the path (progress + tracking errors) ----
        cand = (last_idx + win) % n_pts
        d2 = (path.x[cand] - x) ** 2 + (path.y[cand] - y) ** 2
        j = int(cand[int(np.argmin(d2))])
        delta_idx = (j - last_idx + n_pts // 2) % n_pts - n_pts // 2
        idx_total += delta_idx
        last_idx = j
        th_j = path.theta[j]
        dxp, dyp = x - path.x[j], y - path.y[j]
        e_y = -dxp * math.sin(th_j) + dyp * math.cos(th_j)       # left +
        s_frac = dxp * math.cos(th_j) + dyp * math.sin(th_j)
        s_tot = idx_total * path.ds + s_frac
        e_psi = float(_wrap(psi - th_j))
        s_m = s_tot % path.length

        if s_tot >= total_dist:
            break

        # ---- steering: curvature feed-forward with preview + feedback ----
        # Engine lateral model (physics/traction.py, used by car.py): slip = steer - vy/v.
        # slip -> 0 gives vy = steer*v and yaw rate = steer, so steer = k*v.
        t_lead = max(v, 0.0) * tau_lat + STEER_LEAD_EXTRA
        s_la = s_m + max(v, 0.0) * t_lead
        k_ff = path.at(path.kappa, s_la)
        delta_ff = k_ff * v                                      # rad
        gain = min(1.0, v / 4.0)
        k2 = wn * wn / max(v, 5.0)
        u_fb = -(k1 * e_psi + k2 * e_y) * gain
        low_speed = min(1.0, max(0.0, (v - 0.5) / 2.5))
        steer_cmd = math.degrees(delta_ff + u_fb) * low_speed
        steer_cmd = max(-MAX_STEER_DEG, min(MAX_STEER_DEG, steer_cmd))

        # ---- speed control ----
        s_ref = s_m + v * 0.15
        v_ref = path.at(v_plan, s_ref)
        dv_ds = path.at(dvds, s_ref)
        v_ref = min(v_ref, float(np.interp(s_tot, s_tab, v_tab)) + 1.5)
        a_des = v * dv_ds + 1.5 * (v_ref - v)
        a_des = max(-6.0, min(4.0, a_des))
        f_res = _drag(v) + _roll(v)
        f_net = MASS * a_des + f_res

        kap_now = path.at(path.kappa_eff, s_m + 5.0)
        cap = float(np.interp(kap_now, THR_K, THR_CAP))
        floor = float(np.interp(kap_now, THR_K, THR_FLOOR))

        thr_cmd = 0.0
        brake_u = 0.0
        if f_net >= 0.0:
            avail = max(1e-3, _prop(1.0, v))
            thr_cmd = min(cap, f_net / avail)
        else:
            f_brake = -f_net
            if f_brake > (BRAKE_RELEASE_N if braking_on else BRAKE_ENGAGE_N):
                brake_u = brake_demand_for_force(f_brake)
        braking_on = brake_u > 0.0
        if brake_u == 0.0 and v < v_ref + 1.0:
            thr_cmd = min(cap, max(thr_cmd, floor))     # stay in the style band

        # ---- actuator smoothing ----
        steer_target = steer_s + (steer_cmd - steer_s) * (DT / (STEER_TAU + DT))
        lim = STEER_RATE_DEG * DT
        steer_s += max(-lim, min(lim, steer_target - steer_s))

        bp_s = _slew(bp_s, brake_u, BRK_RATE_UP, BRK_RATE_DOWN, DT)
        if bp_s > 0.02:
            thr_cmd = 0.0
        thr_s = _slew(thr_s, thr_cmd, THR_RATE_UP, THR_RATE_DOWN, DT)

        pedal, bf, br = brake_levels(bp_s)
        rows.append((i * DT, thr_s, bf, br, pedal, steer_s))
        car.step(DT, DriverInputs(
            throttle=thr_s,
            brake_pressure_front=bf,
            brake_pressure_rear=br,
            brake_pedal_travel=pedal,
            steering_angle_deg=steer_s,
        ))
    else:
        raise RuntimeError("Car did not finish the laps (car stuck or off-track).")

    return rows


# ============================================================================
# I/O
# ============================================================================
def load_track_csv(fname):
    pts = []
    with open(fname, newline="") as fh:
        for row in csv.reader(fh):
            try:
                pts.append((float(row[0]), float(row[1])))
            except (ValueError, IndexError):
                continue                                  # header / blanks
    if len(pts) < 4:
        raise ValueError("track file needs at least 4 numeric x,y rows")
    return pts


def write_csv(rows, fname):
    with open(fname, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["time", "throttle", "brakePressureFront",
                    "brakePressureRear", "brakePedalTravel", "steerAngle"])
        for t, thr, bf, br, bp, steer in rows:
            w.writerow([f"{t:.2f}", f"{thr:.5f}", f"{bf:.5f}", f"{br:.5f}",
                        f"{bp:.5f}", f"{steer:.4f}"])


def main():
    track = load_track_csv(sys.argv[1]) if len(sys.argv) > 1 else TRACK
    path = Path(track)
    rows = generate_controls(path)

    arr = np.array(rows)
    assert np.all(np.isfinite(arr)), "non-finite value generated"
    assert np.allclose(np.diff(arr[:, 0]), DT), "time grid is not uniform"
    assert np.max(np.abs(arr[:, 5])) <= MAX_STEER_DEG + 1e-9

    write_csv(rows, OUTPUT_FILE)
    print(f"Track length : {path.length:.1f} m")
    print(f"Rows         : {len(rows)}  ({rows[-1][0]:.2f} s, {NUM_LAPS} laps)")
    print(f"Steer range  : {arr[:, 5].min():.1f} .. {arr[:, 5].max():.1f} deg")
    print(f"Saved        : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()