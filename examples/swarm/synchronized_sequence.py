#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#     ||          ____  _ __
#  +------+      / __ )(_) /_______________ _____  ___
#  | 0xBC |     / __  / / __/ ___/ ___/ __ `/_  / / _ \
#  +------+    / /_/ / / /_/ /__/ /  / /_/ / / /_/  __/
#   ||  ||    /_____/_/\__/\___/_/   \__,_/ /___/\___/
#
#  Copyright (C) 2019 Bitcraze AB
#  GPLv2-or-later
#
"""
Synchronized swarm choreography with the High Level Commander, made robust for
multi-CF bring-up:

- Configurable bitrate/channel (use 1M for robustness during link bring-up)
- Per-CF single-link self-test before opening the Swarm
- Enable High Level Commander param on each CF
- Stable CF_id <-> URI mapping for control queues
"""

import threading
import time
from collections import namedtuple
from queue import Queue

import logging
logging.basicConfig(level=logging.INFO)

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.swarm import CachedCfFactory, Swarm

# ----------------------------
# ---- CONFIGURATION ----------
# ----------------------------
STEP_TIME = 1.0  # seconds per "step" in the sequence timeline

# For robust bring-up start with '1M'. Once stable, you can try '2M' again.
BITRATE = '250K'       # '250K' | '1M' | '2M'
CHANNEL = 80         # Must match CF radio config in cfclient

# Use the exact addresses you configured in cfclient (unique per drone)
ADDRESSES = [
    'E7E7E7E7E9',  # CF_id 0
    'E7E7E7E7EA',  # CF_id 1
    'E7E7E7E7EB',  # CF_id 2
]

# Construct URIs from the config above (dongle 0). Order IS the CF_id mapping.
URIS = [f'radio://0/{CHANNEL}/{BITRATE}/{addr}' for addr in ADDRESSES]

# Run a per-CF single-link test before Swarm to catch the one that might fail.
RUN_SELF_TEST = True

# ----------------------------
# ---- COMMAND DEFINITIONS ----
# ----------------------------
Arm = namedtuple('Arm', [])
Takeoff = namedtuple('Takeoff', ['height', 'time'])
Land = namedtuple('Land', ['time'])
Goto = namedtuple('Goto', ['x', 'y', 'z', 'time'])
Ring = namedtuple('Ring', ['r', 'g', 'b', 'intensity', 'time'])
Quit = namedtuple('Quit', [])  # reserved for control loop

# ----------------------------
# ---- SEQUENCE (timeline) ----
# ----------------------------
sequence = [
    # (step, cf_id, action)
    (0, 0, Arm()),
    (0, 1, Arm()),
    (0, 2, Arm()),

    (0, 0, Takeoff(0.5, 2)),
    (0, 2, Takeoff(0.5, 2)),
    (1, 1, Takeoff(1.0, 2)),

    (2, 0, Goto(-0.5, -0.5, 0.5, 1)),
    (2, 2, Goto( 0.5,  0.5, 0.5, 1)),
    (3, 1, Goto( 0.0,  0.0, 1.0, 1)),

    (4, 0, Ring(255, 255, 255, 0.2, 0)),
    (4, 1, Ring(255,   0,   0, 0.2, 0)),
    (4, 2, Ring(255, 255, 255, 0.2, 0)),

    (5, 0, Goto( 0.5, -0.5, 0.5, 2)),
    (5, 2, Goto(-0.5,  0.5, 0.5, 2)),
    (7, 0, Goto( 0.5,  0.5, 0.5, 2)),
    (7, 2, Goto(-0.5, -0.5, 0.5, 2)),
    (9, 0, Goto(-0.5,  0.5, 0.5, 2)),
    (9, 2, Goto( 0.5, -0.5, 0.5, 2)),
    (11, 0, Goto(-0.5, -0.5, 0.5, 2)),
    (11, 2, Goto( 0.5,  0.5, 0.5, 2)),

    (13, 0, Land(2)),
    (13, 1, Land(2)),
    (13, 2, Land(2)),

    (15, 0, Ring(0, 0, 0, 0, 5)),
    (15, 1, Ring(0, 0, 0, 0, 5)),
    (15, 2, Ring(0, 0, 0, 0, 5)),
]

# ----------------------------
# ---- HELPERS / ACTIONS -----
# ----------------------------
def enable_high_level(scf):
    # Ensure the High Level Commander is enabled.
    scf.cf.param.set_value('commander.enHighLevel', '1')
    time.sleep(0.05)

def activate_mellinger_controller(scf, use_mellinger=False):
    # 1 = PID, 2 = Mellinger (check your firmware docs)
    controller = 2 if use_mellinger else 1
    scf.cf.param.set_value('stabilizer.controller', str(controller))
    time.sleep(0.05)

def arm(scf):
    scf.cf.platform.send_arming_request(True)
    time.sleep(0.8)

def set_ring_color(cf, r, g, b, intensity, fade_time):
    cf.param.set_value('ring.fadeTime', str(fade_time))
    r = int(r * intensity) & 0xFF
    g = int(g * intensity) & 0xFF
    b = int(b * intensity) & 0xFF
    color = (r << 16) | (g << 8) | b
    cf.param.set_value('ring.fadeColor', str(color))

def crazyflie_control(scf):
    """Worker that executes commands coming from the control thread."""
    cf = scf.cf
    # Map link_uri to CF_id via stable URIS list order
    cf_id = URIS.index(cf.link_uri)
    control = controlQueues[cf_id]

    # Pre-flight per-CF setup
    enable_high_level(scf)
    activate_mellinger_controller(scf, use_mellinger=False)

    # Set fade-to-color effect and reset ring off
    set_ring_color(cf, 0, 0, 0, 0.0, 0)
    cf.param.set_value('ring.effect', '14')  # "fade to color" effect

    commander = cf.high_level_commander

    while True:
        command = control.get()
        if isinstance(command, Quit):
            return
        elif isinstance(command, Arm):
            arm(scf)
        elif isinstance(command, Takeoff):
            commander.takeoff(command.height, command.time)
        elif isinstance(command, Land):
            commander.land(0.0, command.time)
        elif isinstance(command, Goto):
            commander.go_to(command.x, command.y, command.z, 0, command.time)
        elif isinstance(command, Ring):
            set_ring_color(cf, command.r, command.g, command.b,
                           command.intensity, command.time)
        else:
            print(f'Warning! unknown command {command} for URI {cf.link_uri}')

def control_thread():
    """Timeline scheduler: dispatch commands to each CF's queue."""
    pointer = 0
    step = 0
    stop = False

    while not stop:
        print(f'Step {step}:')
        while pointer < len(sequence) and sequence[pointer][0] <= step:
            cf_id, command = sequence[pointer][1], sequence[pointer][2]
            print(f' - Running: {command} on {cf_id}')
            controlQueues[cf_id].put(command)
            pointer += 1
            if pointer >= len(sequence):
                print('Reaching the end of the sequence, stopping!')
                stop = True
                break
        step += 1
        time.sleep(STEP_TIME)

    # Flush workers
    for ctrl in controlQueues:
        ctrl.put(Quit())

def self_test_each_uri(uris):
    """Open each URI once to verify radio params and RF conditions."""
    print('--- Single-link self-test ---')
    for uri in uris:
        print(f'Testing {uri} …')
        try:
            with SyncCrazyflie(uri, cf=Crazyflie(rw_cache='./cache')) as scf:
                enable_high_level(scf)
                print(f'  OK: {uri}')
        except Exception as e:
            print(f'  FAIL: {uri} :: {e}')
            raise  # Fail fast so you can fix that unit before attempting swarm

# ----------------------------
# ---- MAIN -------------------
# ----------------------------
if __name__ == '__main__':
    # Sanity: CF_ids in the sequence must be in range
    max_cf_id = max(cf_id for _, cf_id, _ in sequence)
    assert max_cf_id < len(URIS), "Sequence references a CF_id not in URIS!"

    controlQueues = [Queue() for _ in range(len(URIS))]

    # Initialize low-level Crazyradio/CRTP drivers
    cflib.crtp.init_drivers()

    # Optional: per-CF single-link bring-up (more robust than failing in Swarm)
    if RUN_SELF_TEST:
        self_test_each_uri(URIS)

    factory = CachedCfFactory(rw_cache='./cache')

    # NOTE: Swarm.__enter__ opens links in parallel; if any link fails, it raises.
    # Our self-test above ensures all links are healthy before this point.
    with Swarm(URIS, factory=factory) as swarm:
        # Basic estimator reset (if you use an absolute positioning system)
        swarm.reset_estimators()

        print('Starting sequence!')
        t = threading.Thread(target=control_thread, daemon=True)
        t.start()

        # This runs one worker per CF in parallel
        swarm.parallel_safe(crazyflie_control)

        # Allow threads to settle if needed
        time.sleep(1.0)