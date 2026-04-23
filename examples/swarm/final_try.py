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


uri2 = 'radio://0/30/2M/E7E7E7E7E2'
uri3 = 'radio://0/30/2M/E7E7E7E7E3'

uri4 = 'radio://1/60/2M/E7E7E7E7E4'
uri5 = 'radio://1/60/2M/E7E7E7E7E5'
uri6 = 'radio://1/60/2M/E7E7E7E7E6'

uri7 = 'radio://2/90/2M/E7E7E7E7E8'
uri8 = 'radio://2/90/2M/E7E7E7E7E9'
uri9 = 'radio://2/90/2M/E7E7E7E7EA'
uri10 ='radio://2/90/2M/E7E7E7E7EB'

CSV_DIR = r"C:\Users\sfy0002\Documents\CSV_dir"

uris = [
   
    uri2,
    uri3,
    uri4,
    uri5,
    uri6,
    uri7,
    uri8,
    uri9,
    uri10,
    # Add more URIs if you want more copters in the swarm
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
    
    uri2: x0 + 1*x_offset,
    uri3: x0,
    uri4: x0 - 1*x_offset,
    uri5: x0 - 2*x_offset,
    uri6: x0 - 2*x_offset,
    uri7: x0 -1*x_offset,
    uri8: x0,
    uri9: x0 + 1*x_offset,
    uri10: x0 + 2*x_offset,
}


starting_y = {
    
    uri2: y0,
    uri3: y0,
    uri4: y0,
    uri5: y0,
    uri6: -y0,
    uri7: -y0,
    uri8: -y0,
    uri9: -y0,
    uri10:-y0,
}



pos1_y = {
    
    uri2:  1.348561,
    uri3:  1.291376,
    uri4:  0.756028,
    uri5:  0.261029,
    uri6: -0.261029,
    uri7: -1.291376,
    uri8: -0.756028,
    uri9: -1.348561,
    uri10: -1.064794,
}


pos1_x = {
    
    uri2:  0.282828,
    uri3: -0.366522,
    uri4: -0.727273,
    uri5: -0.842713,
    uri6: -0.842713,
    uri7: -0.366522,
    uri8: -0.727273,
    uri9:  0.282828,
    uri10: 0.571429,
}





starting_z = {

    uri2: z0,
    uri3: z0,
    uri4: z0,
    uri5: z0,
    uri6: z0,
    uri7: z0,
    uri8: z0,
    uri9: z0,
    uri10: z0,
}

pos2_x = {

    uri2:  0.250000,
    uri3:  0.000000,
    uri4: -0.250000,
    uri5:  0.000000,
    uri6: -0.500000,
    uri7: -1.000000,
    uri8: -0.750000,
    uri9:  1.000000,
    uri10: 0.750000,
}

pos2_y = {

    uri2:  0.714286,
    uri3:  1.428571,
    uri4:  0.714286,
    uri5:  0.000000,
    uri6:  0.000000,
    uri7: -1.428571,
    uri8: -0.714286,
    uri9: -1.428571,
    uri10: -0.714286,
}

pos3_x = {
    
    uri2:  0.714286,
    uri3:  0.428571,
    uri4: -0.571429,
    uri5:  0.000000,
    uri6: -0.571429,
    uri7: -0.571429,
    uri8: -0.571429,
    uri9:  0.714286,
    uri10: 0.285714

}

pos3_y = {
    
    
    uri2:  0.714286,
    uri3:  1.428571,
    uri4:  1.428571,
    uri5:  0.142857,
    uri6:  0.571429,
    uri7: -1.428571,
    uri8: -0.571429,
    uri9: -1.428571,
    uri10: -0.571429,


}

#Alternate postion 3 for "R" letter

# pos3_x = {
#     uri2:  0.714286,
#     uri3:  0.428571,
#     uri4: -0.571429,
#     uri5:  0.428571,
#     uri6: -0.571429,
#     uri7: -0.571429,
#     uri8: -0.571429,
#     uri9:  0.714286,
#     uri10: 0.285714,
# }

# pos3_y = {
    
#     uri2:  0.714286,
#     uri3:  0.428571,
#     uri4: -0.571429,
#     uri5:  0.000000,
#     uri6: -0.571429,
#     uri7: -0.571429,
#     uri8: -0.571429,
#     uri9:  0.714286,
#     uri10: 0.285714,

# }

pos4_x = {
    uri2:  0.857143,
    uri3:  0.142857,
    uri4: -0.571429,
    uri5:  0.571429,
    uri6: -0.571429,
    uri7: -0.571429,
    uri8: -0.571429,
    uri9:  0.857143,
    uri10: 0.142857,
}

pos4_y = {
    uri2:  1.428571,
    uri3:  1.428571,
    uri4:  1.428571,
    uri5:  0.000000,
    uri6:  0.000000,
    uri7: -1.428571,
    uri8: -0.714286,
    uri9: -1.428571,
    uri10: -1.428571,
}


def run_shared_sequence(scf: SyncCrazyflie):
    circle_duration = 5  # Duration of a full-circle
    commander = scf.cf.high_level_commander
    uri = scf._link_uri

    commander.takeoff(starting_z[uri], 2)
    time.sleep(2.1)

    # Go to the starting position
    commander.go_to(starting_x[uri], starting_y[uri], starting_z[uri], yaw0, 2)
    time.sleep(2.1)

    # Go to next position
    commander.go_to(pos1_x[uri], pos1_y[uri], starting_z[uri], yaw0, 4)
    time.sleep(4.1)

    commander.go_to(pos2_x[uri], pos2_y[uri], starting_z[uri], yaw0, 4)
    time.sleep(4.1)
    
    commander.go_to(pos3_x[uri], pos3_y[uri], starting_z[uri], yaw0, 4)
    time.sleep(4.1)

    commander.go_to(pos4_x[uri], pos4_y[uri], starting_z[uri], yaw0, 4)
    time.sleep(4.1)


    commander.land(0, 4)
    time.sleep(8)


if __name__ == '__main__':
    cflib.crtp.init_drivers()
    factory = CachedCfFactory(rw_cache='./cache')
    with Swarm(uris, factory=factory) as swarm:
        # swarm.reset_estimators()
        time.sleep(0.5)
        print('arming...')
        swarm.parallel_safe(arm)
        print('starting sequence...')
        swarm.parallel_safe(run_shared_sequence)
        time.sleep(1)
