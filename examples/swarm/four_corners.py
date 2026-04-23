# -*- coding: utf-8 -*-
#
#     ||          ____  _ __
#  +------+      / __ )(_) /_______________ _____  ___
#  | 0xBC |     / __  / / __/ ___/ ___/ __ `/_  / / _ \
#  +------+    / /_/ / / /_/ /__/ /  / /_/ / / /_/  __/
#   ||  ||    /_____/_/\__/\___/_/   \__,_/ /___/\___/
#
#  Copyright (C) 2025 Bitcraze AB
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
"""
Script for flying a swarm of 8 Crazyflies performing a coordinated spiral choreography
resembling a Christmas tree outline in 3D space. Each drone takes off to a different
height, flies in spiraling circular layers, and changes radius as it rises and descends,
forming the visual structure of a cone when viewed from outside.

The script is using the high level commanded and has been tested with 3 Crazyradios 2.0
and the Lighthouse positioning system.
"""
import math
import time

import cflib.crtp
from cflib.crazyflie.swarm import CachedCfFactory
from cflib.crazyflie.swarm import Swarm
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

uri1 = 'radio://0/30/2M/E7E7E7E7E2'
uri2 = 'radio://0/30/2M/E7E7E7E7E3'



uri3 = 'radio://1/60/2M/E7E7E7E7E4'
uri4 = 'radio://1/60/2M/E7E7E7E7E5'


CSV_DIR = r"C:\Users\sfy0002\Documents\CSV_dir"

uris = [
    uri1,
    uri2,
    uri3,
    uri4,
]


def arm(scf: SyncCrazyflie):
    scf.cf.platform.send_arming_request(True)
    time.sleep(1.0)


# starting position references
x0 = 0
y0 = 0.9
z0 = 0.5
yaw0 = math.pi/2

x_offset = 0.4  # Vertical distance between 2 layers
z_offset = 0.5  # Radius difference between 2 layers

starting_x = {
    uri1: x0 + 2*x_offset,
    uri2: x0 - 2*x_offset,
    uri3: x0 + 2*x_offset,
    uri4: x0 - 2*x_offset,
}


starting_y = {
    uri1: y0,
    uri2: y0,
    uri3: -y0,
    uri4: -y0,
}



pos1_y = {
    uri1: -y0,
    uri2: y0,
    uri3: -y0,
    uri4: y0,
   
}


pos1_x = {
    uri1: x0 + 2*x_offset,
    uri2: x0 + 2*x_offset,
    uri3: x0 - 2*x_offset,
    uri4: x0 - 2*x_offset,
    
}





starting_z = {
    uri1: z0,
    uri2: z0,
    uri3: z0,
    uri4: z0,
}





def run_shared_sequence(scf: SyncCrazyflie):
    circle_duration = 5  # Duration of a full-circle
    commander = scf.cf.high_level_commander
    uri = scf._link_uri

    commander.takeoff(starting_z[uri], 3)
    time.sleep(3.1)

    # Go to the starting position
    commander.go_to(starting_x[uri], starting_y[uri], starting_z[uri], yaw0, 2)
    time.sleep(2.1)

    # Go to next position
    commander.go_to(pos1_x[uri], pos1_y[uri], starting_z[uri], yaw0, 6)
    time.sleep(6.1)


    commander.land(0, 4)
    time.sleep(8)

def run_emergency_land(scf: SyncCrazyflie):
    commander = scf.cf.high_level_commander
    uri = scf._link_uri
    commander.land(0,4)
    time.sleep(8)


if __name__ == '__main__':
    cflib.crtp.init_drivers()
    factory = CachedCfFactory(rw_cache='./cache')
    try:
        with Swarm(uris, factory=factory) as swarm:
            # swarm.reset_estimators()
            time.sleep(0.5)
            print('arming...')
            swarm.parallel_safe(arm)
            print('starting sequence...')
            swarm.parallel_safe(run_shared_sequence)
            time.sleep(1)
    except Exception as e:
        print("Exception in flight: ", e)
        try:
            with Swarm(uris, factory=factory) as swarm:
                swarm.parallel_safe(run_emergency_land)
        except Exception as e:
            print("Emergency land failed: ", e)

