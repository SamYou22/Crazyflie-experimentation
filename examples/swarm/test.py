# swarm_square_sequential_then_parallel.py
# Python 3.13 + cflib >= 0.1.29
import time
import logging

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.swarm import Swarm, CachedCfFactory

logging.basicConfig(level=logging.INFO)

# --- Choose bitrate for bring-up: '2M', '1M', or '250K'
BITRATE = '1M'   # Try 1M first for robustness; switch back to '2M' when stable

# Paste the URIs EXACTLY as cfclient shows them, but replace the bitrate part if testing BITRATE
URIS = {
    f'radio://0/30/{BITRATE}/E7E7E7E7E9',
    f'radio://0/30/{BITRATE}/E7E7E7E7EA',
    f'radio://0/30/{BITRATE}/E7E7E7E7EB',
    f'radio://0/30/{BITRATE}/E7E7E7E7EC',
}

def enable_high_level(scf):
    # Make sure High Level Commander is enabled
    scf.cf.param.set_value('commander.enHighLevel', '1')
    time.sleep(0.1)

def activate_mellinger_controller(scf, use_mellinger=False):
    # 1 = PID, 2 = Mellinger (check your firmware docs)
    controller = 2 if use_mellinger else 1
    scf.cf.param.set_value('stabilizer.controller', str(controller))
    time.sleep(0.1)

def arm(scf):
    # Requires recent firmware that supports arming request
    scf.cf.platform.send_arming_request(True)
    time.sleep(0.8)

def run_shared_sequence(scf):
    enable_high_level(scf)
    activate_mellinger_controller(scf, use_mellinger=False)

    box_size = 1.0
    flight_time = 2.0
    commander = scf.cf.high_level_commander

    commander.takeoff(1.0, 2.0)
    time.sleep(3.0)

    commander.go_to(box_size, 0, 0, 0, flight_time, relative=True)
    time.sleep(flight_time)

    commander.go_to(0, box_size, 0, 0, flight_time, relative=True)
    time.sleep(flight_time)

    commander.go_to(-box_size, 0, 0, 0, flight_time, relative=True)
    time.sleep(flight_time)

    commander.go_to(0, -box_size, 0, 0, flight_time, relative=True)
    time.sleep(flight_time)

    commander.land(0.0, 2.0)
    time.sleep(2.0)
    commander.stop()

def self_test_each_uri(uris):
    """Open each URI once to verify link parameters and RF conditions."""
    print('--- Single-link self-test ---')
    for uri in sorted(uris):
        print(f'Testing {uri} …')
        try:
            with SyncCrazyflie(uri, cf=Crazyflie(rw_cache='./cache')) as scf:
                print(f'  OK: {uri}')
        except Exception as e:
            print(f'  FAIL: {uri} :: {e}')
            raise   # Fail fast so we can fix this unit before the swarm

if __name__ == '__main__':
    cflib.crtp.init_drivers()

    # 1) Make sure each URI can link on its own
    self_test_each_uri(URIS)

    # 2) Try opening links in the swarm SEQUENTIALLY first (clearer errors)
    factory = CachedCfFactory(rw_cache='./cache')
    with Swarm(URIS, factory=factory) as swarm:
        # This forces a per-link open in sequence. If we reach here, links are open.
        swarm.sequential(lambda scf: enable_high_level(scf))

        # Optional: estimator reset if you use an absolute positioning system
        swarm.reset_estimators()

        # Arm and fly in PARALLEL
        swarm.parallel_safe(arm)
        swarm.parallel_safe(run_shared_sequence)