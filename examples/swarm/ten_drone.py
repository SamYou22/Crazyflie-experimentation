#!/usr/bin/env python3
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
CSV_DIR = r"C:\Users\sfy0002\Documents\CSV_dir"  # folder with step CSVs

# ROW ORDER DEFINES DRONE ASSIGNMENT
DRONES = [
    "cf1", "cf2", "cf3", "cf4", "cf5",
    "cf6", "cf7", "cf8", "cf9", "cf10"
]

# REPLACE WITH YOUR ACTUAL URIs
# Strongly recommend 1M for 10 drones
URI_BY_DRONE = {
    "cf1":  "radio://0/80/1M/E7E7E7E701",
    "cf2":  "radio://0/80/1M/E7E7E7E702",
    "cf3":  "radio://0/80/1M/E7E7E7E703",
    "cf4":  "radio://0/80/1M/E7E7E7E704",
    "cf5":  "radio://0/80/1M/E7E7E7E705",
    "cf6":  "radio://0/80/1M/E7E7E7E706",
    "cf7":  "radio://0/80/1M/E7E7E7E707",
    "cf8":  "radio://0/80/1M/E7E7E7E708",
    "cf9":  "radio://0/80/1M/E7E7E7E709",
    "cf10": "radio://0/80/1M/E7E7E7E70A",
}

# FLIGHT CONSTANTS
FIXED_Z = 0.5
FIXED_YAW = 0.0
TAKEOFF_DURATION = 2.0
MOVE_DURATION = 2.0
LAND_Z = 0.0
LAND_DURATION = 2.0
START_DELAY = 5.0
# ===================================================


_number_re = re.compile(r"(\d+)")

def natural_key(path: str):
    parts = _number_re.split(os.path.basename(path))
    return [int(p) if p.isdigit() else p.lower() for p in parts]


def read_step_csv(path: str, drones: List[str]) -> Dict[str, Tuple[float, float]]:
    rows: List[Tuple[float, float]] = []

    with open(path) as f:
        lines = [
            l.strip() for l in f
            if l.strip() and not l.strip().startswith("#")
        ]

    # Skip header if non-numeric
    if not lines:
        raise ValueError(f"{path} is empty")

    def parse(line):
        try:
            a, b = line.split(",")
            return float(a), float(b)
        except Exception:
            return None

    idx = 0
    if parse(lines[0]) is None:
        idx = 1

    for l in lines[idx:]:
        xy = parse(l)
        if xy is not None:
            rows.append(xy)

    if len(rows) < len(drones):
        raise ValueError(
            f"{os.path.basename(path)} needs {len(drones)} rows, got {len(rows)}"
        )

    return {drones[i]: rows[i] for i in range(len(drones))}


def load_all_steps(csv_dir: str, drones: List[str]):
    paths = sorted(glob.glob(os.path.join(csv_dir, "*.csv")), key=natural_key)
    if not paths:
        raise FileNotFoundError("No CSV files found")

    steps = []
    for p in paths:
        steps.append(read_step_csv(p, drones))
    return steps


def build_timelines(steps, drones):
    timelines = {d: [] for d in drones}
    for step in steps:
        for d in drones:
            timelines[d].append(step[d])
    return timelines


def setup_hl(cf: Crazyflie):
    cf.param.set_value("commander.enHighLevel", "1")
    try:
        cf.high_level_commander.stop()
    except Exception:
        pass
    time.sleep(0.1)


def fly_sequence(scf: SyncCrazyflie, xy_steps, t0):
    cf = scf.cf
    hl = cf.high_level_commander

    setup_hl(cf)

    hl.takeoff(FIXED_Z, TAKEOFF_DURATION)
    time.sleep(TAKEOFF_DURATION + 0.2)

    if time.time() < t0:
        time.sleep(t0 - time.time())

    for i, (x, y) in enumerate(xy_steps, start=1):
        print(f"{cf.link_uri} STEP {i}: x={x:.2f}, y={y:.2f}")
        hl.go_to(x, y, FIXED_Z, FIXED_YAW, MOVE_DURATION, relative=False)
        time.sleep(MOVE_DURATION + 0.05)

    hl.land(LAND_Z, LAND_DURATION)
    time.sleep(LAND_DURATION + 0.2)
    hl.stop()


def main():
    cflib.crtp.init_drivers(enable_debug_driver=False)

    steps = load_all_steps(CSV_DIR, DRONES)
    timelines = build_timelines(steps, DRONES)

    print(f"Loaded {len(steps)} steps")
    for d in DRONES:
        print(d, timelines[d])

    uris = [URI_BY_DRONE[d] for d in DRONES]
    uri_to_drone = {URI_BY_DRONE[d]: d for d in DRONES}

    factory = CachedCfFactory(rw_cache=None, ro_cache=None)

    t0 = time.time() + START_DELAY
    print(f"Starting swarm at t0 = {t0:.2f}")

    def task(scf):
        d = uri_to_drone[scf.cf.link_uri]
        fly_sequence(scf, timelines[d], t0)

    with Swarm(uris, factory=factory) as swarm:
        swarm.parallel_safe(task)


if __name__ == "__main__":
    main()