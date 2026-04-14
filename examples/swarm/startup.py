#!/usr/bin/env python3
"""
Sequential prop spin test (repeatable, correct for current cflib)
- 6 drones
- 3 radios
- Motors can spin on EVERY run
- NO takeoff
"""

import time
import cflib
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

DRONES = ["cf1", "cf2", "cf3", "cf4", "cf5", "cf6"]

URI_BY_DRONE = {
    "cf1": "radio://0/80/2M/E7E7E7E7EC",
    "cf2": "radio://0/80/2M/E7E7E7E7EB",
    "cf3": "radio://1/80/2M/E7E7E7E7EA",
    "cf4": "radio://1/80/2M/E7E7E7E7E9",
    "cf5": "radio://2/80/2M/E7E7E7E7E8",
    "cf6": "radio://2/80/2M/E7E7E7E7E7",
}

START_THRUST = 8000
SPIN_TIME = 3.0
INTER_DRONE_DELAY = 2.0

def stop_and_disarm(cf):
    # Stop motors
    cf.commander.send_setpoint(0, 0, 0, 0)
    time.sleep(0.1)
    # ✅ Properly clear the supervisor latch
    cf.commander.send_stop_setpoint()
    time.sleep(0.2)

def main():
    print("\n=== REPEATABLE PROP SPIN TEST ===")
    print("⚠️ Props may spin — keep clear\n")

    cflib.crtp.init_drivers(enable_debug_driver=False)

    for drone in DRONES:
        uri = URI_BY_DRONE[drone]
        print(f"Connecting to {drone} ({uri})")

        try:
            with SyncCrazyflie(uri) as scf:
                cf = scf.cf

                # Clean start
                stop_and_disarm(cf)

                print(f"{drone}: motors ON")
                cf.commander.send_setpoint(0, 0, 0, START_THRUST)
                time.sleep(SPIN_TIME)

                print(f"{drone}: motors OFF")
                stop_and_disarm(cf)
                print()

        except Exception as e:
            print(f"[ERROR] {drone}: {e}\n")

        time.sleep(INTER_DRONE_DELAY)

    print("=== TEST COMPLETE ===\n")

if __name__ == "__main__":
    main()