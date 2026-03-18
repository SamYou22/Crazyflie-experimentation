#!/usr/bin/env python3
import csv
import glob
import os
import time
from typing import List, Dict

import cflib
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.swarm import Swarm, CachedCfFactory

# =================== USER CONFIG ===================
# Directory containing per-drone CSV files (e.g., cf1.csv, cf2.csv, ...)
CSV_DIR = "./trajectories"

# Map drone-id (matching csv basename without extension) -> URI
# Replace with your real URIs
URI_BY_DRONE = {
    "cf1":  "radio://0/80/2M/E7E7E7E701",
    "cf2":  "radio://0/80/2M/E7E7E7E702",
    "cf3":  "radio://0/80/2M/E7E7E7E703",
    "cf4":  "radio://0/80/2M/E7E7E7E704",
    "cf5":  "radio://0/80/2M/E7E7E7E705",
    "cf6":  "radio://0/80/2M/E7E7E7E706",
    "cf7":  "radio://0/80/2M/E7E7E7E707",
    "cf8":  "radio://0/80/2M/E7E7E7E708",
    "cf9":  "radio://0/80/2M/E7E7E7E709",
    "cf10": "radio://0/80/2M/E7E7E7E70A",
}

# Flight defaults
TAKEOFF_Z = 0.6            # meters
TAKEOFF_DURATION = 2.0     # seconds
LAND_Z = 0.0
LAND_DURATION = 2.0
START_DELAY = 5.0          # seconds from now to synchronized t0
DEFAULT_YAW = 0.0          # deg
DEFAULT_MOVE_DURATION = 2.0  # if not specified in CSV
# ===================================================

def read_csv_timeline(csv_path: str) -> List[Dict]:
    """
    Load a single drone's waypoints from CSV.

    Supports two schemas:
      A) with absolute time:
         columns: t, x, y, z[, yaw][, duration]
      B) durations only (no 't' column):
         columns: x, y, z[, yaw][, duration]
         -> script accumulates durations to get target times

    Returns a list of waypoints with keys:
      {'t': float, 'x': float, 'y': float, 'z': float, 'yaw': float, 'duration': float}
    """
    with open(csv_path, newline='') as f:
        reader = csv.DictReader(row for row in f if not str(row).strip().startswith('#'))
        fields = [c.strip() for c in reader.fieldnames] if reader.fieldnames else []

        has_t = 't' in fields
        req = {'x', 'y', 'z'}
        if not req.issubset(set(fields)):
            raise ValueError(f"{os.path.basename(csv_path)} must include columns {req}; got {fields}")

        waypoints = []
        cum_time = 0.0
        for row in reader:
            # Clean row keys
            row = {k.strip(): v for k, v in row.items()}

            # Parse numerics with defaults
            x = float(row['x']); y = float(row['y']); z = float(row['z'])
            yaw = float(row['yaw']) if ('yaw' in row and row['yaw'] not in (None, '', 'nan')) else DEFAULT_YAW
            duration = float(row['duration']) if ('duration' in row and row['duration'] not in (None, '', 'nan')) else DEFAULT_MOVE_DURATION

            if has_t:
                t = float(row['t'])
            else:
                # Accumulate durations as target times
                cum_time += duration
                t = cum_time

            waypoints.append({'t': t, 'x': x, 'y': y, 'z': z, 'yaw': yaw, 'duration': duration})

        # Sort by target time just in case
        waypoints.sort(key=lambda w: w['t'])
        return waypoints

def load_all_timelines(csv_dir: str) -> Dict[str, List[Dict]]:
    """
    Scan csv_dir for files named <drone_id>.csv (e.g., cf1.csv)
    Returns dict: drone_id -> list of waypoints
    """
    timelines = {}
    for path in glob.glob(os.path.join(csv_dir, "*.csv")):
        drone_id = os.path.splitext(os.path.basename(path))[0]
        timelines[drone_id] = read_csv_timeline(path)

    if not timelines:
        raise RuntimeError(f"No CSV files found in {csv_dir}. Expected files like cf1.csv, cf2.csv, ...")
    return timelines

def setup_high_level(cf: Crazyflie):
    # Enable High-Level Commander
    cf.param.set_value('commander.enHighLevel', '1')
    # Stop any previous HL sequence
    try:
        cf.high_level_commander.stop()
        time.sleep(0.1)
    except Exception:
        pass

def execute_timeline(scf: SyncCrazyflie, drone_id: str, timeline: List[Dict], t0: float):
    cf = scf.cf
    setup_high_level(cf)
    hl = cf.high_level_commander

    # Takeoff
    hl.takeoff(TAKEOFF_Z, TAKEOFF_DURATION)
    time.sleep(TAKEOFF_DURATION + 0.2)

    # Sync start
    now = time.time()
    if now < t0:
        time.sleep(t0 - now)

    # Execute each waypoint at its target time
    for wp in timeline:
        target_time = t0 + wp['t']
        wait = target_time - time.time()
        if wait > 0:
            time.sleep(wait)

        hl.go_to(wp['x'], wp['y'], wp['z'], wp['yaw'], wp['duration'], relative=False)
        # Allow move to complete (keeps radio load low by avoiding spam)
        time.sleep(wp['duration'])

    # Land
    hl.land(LAND_Z, LAND_DURATION)
    time.sleep(LAND_DURATION + 0.2)
    hl.stop()

def main():
    cflib.crtp.init_drivers(enable_debug_driver=False)

    timelines = load_all_timelines(CSV_DIR)

    # Only include drones for which we have both a CSV and a URI
    missing_uri = [d for d in timelines if d not in URI_BY_DRONE]
    if missing_uri:
        raise RuntimeError(f"Provide URIs for these drones found in CSV_DIR: {missing_uri}")

    uris = [URI_BY_DRONE[d] for d in timelines.keys()]
    uri_to_drone = {URI_BY_DRONE[d]: d for d in timelines.keys()}

    factory = CachedCfFactory(rw_cache='./cache')

    # Global synchronized start
    t0 = time.time() + START_DELAY
    print(f"Synchronized start t0 = {t0:.3f} (in {START_DELAY:.1f}s) for drones: {list(timelines.keys())}")

    def per_cf_task(scf: SyncCrazyflie):
        drone_id = uri_to_drone[scf.link_uri]
        execute_timeline(scf, drone_id, timelines[drone_id], t0)

    # Connect and fly in parallel
    with Swarm(uris, factory=factory) as swarm:
        swarm.parallel_safe(per_cf_task)

if __name__ == "__main__":
    main()
