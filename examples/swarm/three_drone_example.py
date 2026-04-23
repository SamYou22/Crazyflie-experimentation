#!/usr/bin/env python3
import csv
import glob
import os
import re
import time
from typing import Dict, List, Tuple

import cflib
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.swarm import Swarm, CachedCfFactory

# =================== USER CONFIG ===================
CSV_DIR = r"C:\Users\sfy0002\Documents\CSV_dir"  # folder with cf1.csv, cf2.csv, cf3.csv, ...

# Row order in each step file MUST match this list:
DRONES = ["cf1", "cf2", "cf3"]

# Replace these with your actual Crazyflie URIs.
# If the CF Client connects at 1M reliably, change "2M" -> "1M".
URI_BY_DRONE = {
    "cf1": "radio://0/80/2M/E7E7E7E7E1",
    "cf2": "radio://0/80/2M/E7E7E7E7E2",
    "cf3": "radio://0/80/2M/E7E7E7E7E3",
}

# Flight parameters
FIXED_Z = 0.5              # meters
FIXED_YAW = 0.0            # degrees
TAKEOFF_DURATION = 2.0     # seconds
LAND_Z = 0.0
LAND_DURATION = 2.0
MOVE_DURATION = 2.0        # constant duration per step
START_DELAY = 4.0          # seconds from now to synchronized t0
# ===================================================

_number_re = re.compile(r"(\d+)")

def _natural_key(path: str):
    """Sort so cf2.csv < cf10.csv."""
    name = os.path.basename(path)
    parts = _number_re.split(name)
    return [int(p) if p.isdigit() else p.lower() for p in parts]

def _read_lines_skip_comments(path: str):
    with open(path, newline='') as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            yield line

def parse_step_file_roworder(path: str, drones: List[str]) -> Dict[str, Tuple[float, float]]:
    """
    Parse one 'step' CSV whose rows are in the same order as DRONES.
    Accepts either:
      - header 'x,y' followed by numeric rows, or
      - just raw numeric rows 'x,y'.
    Returns: { drone_id: (x, y), ... } for all drones.
    """
    rows: List[Tuple[float, float]] = []
    lines = list(_read_lines_skip_comments(path))
    if not lines:
        raise ValueError(f"{os.path.basename(path)} is empty (after skipping comments).")

    def try_parse_xy(text: str):
        parts = [p.strip() for p in text.split(',')]
        if len(parts) < 2:
            return None
        try:
            return float(parts[0]), float(parts[1])
        except Exception:
            return None

    # Skip a header-like first line if it's not numeric
    start_idx = 0
    if try_parse_xy(lines[0]) is None:
        start_idx = 1

    for i in range(start_idx, len(lines)):
        xy = try_parse_xy(lines[i])
        if xy is not None:
            rows.append(xy)

    if len(rows) < len(drones):
        raise ValueError(
            f"{os.path.basename(path)} has {len(rows)} data rows, needs at least {len(drones)} "
            f"(one per drone in order: {drones})."
        )

    # Map the first N rows to the drones by order
    return {drones[i]: rows[i] for i in range(len(drones))}

def load_all_steps(csv_dir: str, drones: List[str]) -> List[Dict[str, Tuple[float, float]]]:
    """
    Load every *.csv as a 'step', sorted naturally by filename.
    Each step returns a dict {drone -> (x, y)}.
    """
    paths = sorted(glob.glob(os.path.join(csv_dir, "*.csv")), key=_natural_key)
    if not paths:
        raise FileNotFoundError(f"No CSV files found in {csv_dir}")
    steps = []
    for p in paths:
        step = parse_step_file_roworder(p, drones)
        steps.append(step)
    return steps

def build_timelines_from_steps(steps: List[Dict[str, Tuple[float, float]]],
                               drones: List[str]) -> Dict[str, List[Tuple[float, float]]]:
    """Transform per-step positions into per-drone waypoints."""
    per_drone: Dict[str, List[Tuple[float, float]]] = {d: [] for d in drones}
    for step in steps:
        for d in drones:
            per_drone[d].append(step[d])
    return per_drone

def setup_high_level(cf: Crazyflie):
    cf.param.set_value('commander.enHighLevel', '1')
    try:
        cf.high_level_commander.stop()
        time.sleep(0.1)
    except Exception:
        pass

def fly_timed_steps(scf: SyncCrazyflie, waypoints_xy: List[Tuple[float, float]], t0: float):
    """
    Execute each step with constant MOVE_DURATION in a deterministic way:
      - Wait to t0 so all drones start together after takeoff
      - For each step: send go_to, then sleep MOVE_DURATION
    """
    cf = scf.cf
    setup_high_level(cf)
    hl = cf.high_level_commander

    # Takeoff
    hl.takeoff(FIXED_Z, TAKEOFF_DURATION)
    time.sleep(TAKEOFF_DURATION + 0.2)

    # Wait until synchronized start
    now = time.time()
    if now < t0:
        time.sleep(t0 - now)

    # Step-by-step execution
    for idx, (x, y) in enumerate(waypoints_xy, start=1):
        print(f"[{time.time():.3f}] {cf.link_uri} STEP {idx}/{len(waypoints_xy)} -> "
              f"go_to(x={x:.3f}, y={y:.3f}, z={FIXED_Z:.3f}, yaw={FIXED_YAW}, dur={MOVE_DURATION})")
        hl.go_to(x, y, FIXED_Z, FIXED_YAW, MOVE_DURATION, relative=False)
        time.sleep(MOVE_DURATION + 0.05)  # ensure full duration elapses

    # Land after the final segment has finished
    hl.land(LAND_Z, LAND_DURATION)
    time.sleep(LAND_DURATION + 0.2)
    hl.stop()

def main():
    # Sanity: all drones have URIs
    for d in DRONES:
        if d not in URI_BY_DRONE:
            raise RuntimeError(f"No URI configured for drone '{d}' in URI_BY_DRONE")

    cflib.crtp.init_drivers(enable_debug_driver=False)

    # Load steps and build per-drone timelines
    steps = load_all_steps(CSV_DIR, DRONES)
    timelines = build_timelines_from_steps(steps, DRONES)

    print(f"Loaded {len(steps)} step files from: {CSV_DIR}")
    print("Parsed timelines (per drone):")
    for d in DRONES:
        print(f"  {d}: {timelines[d]}")

    # Prepare swarm
    uris = [URI_BY_DRONE[d] for d in DRONES]
    uri_to_drone = {URI_BY_DRONE[d]: d for d in DRONES}

    # Disable on-disk cache to avoid warnings while testing
    factory = CachedCfFactory(rw_cache=None, ro_cache=None)

    # Global synchronized start time (after takeoff)
    t0 = time.time() + START_DELAY
    print(f"Synchronized step start t0 = {t0:.3f} (in {START_DELAY:.1f}s)")

    def per_cf_task(scf: SyncCrazyflie):
        link = scf.cf.link_uri  # correct attribute
        drone_id = uri_to_drone[link]
        waypoints_xy = timelines[drone_id]
        print(f"Flying {drone_id} via {link} with {len(waypoints_xy)} steps")
        fly_timed_steps(scf, waypoints_xy, t0)

    with Swarm(uris, factory=factory) as swarm:
        swarm.parallel_safe(per_cf_task)

if __name__ == "__main__":
    main()