# Modified code from PicoQuant
# Keno Goertz, PicoQUant GmbH, February 2018

# T Mode data are written to an output file [filename]
# We do not keep it in memory because of the huge amout of memory
# this would take in case of large files. Of course you can change this, 
# e.g. if your files are not too big. 
# Otherwise it is best process the data on the fly and keep only the results.

# Purpose: to be able to "tail" PTU files to create a live time trace of photon counts
# Modified by Brayden Shinkawa

import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
import sys
import struct
import os
from queue import Queue
# static variables
# channel numbers
GREEN = 2
RED = 1

# number of data points allowed on the graph
MAX_SIZE = 100
MILLISECOND_CONVERSION = float(1.0/MAX_SIZE) 
# number of overflows needed before plotting on graph
# calculation being done is 75 ns * 1023 (number of bits in nsync) * OVERFLOW_MAX
# this comes out to around 0.1 s per overflow, or 100 ms when OVERFLOW_MAX is 1300
OVERFLOW_MAX = 1300
MAX_HEIGHT = 10**3
THOUSAND_MILLISECONDS = 1000

# global variables
global inputfile
global x
global ofl
global green_lst
global green_val
global green_line
global red_lst
global red_val
global red_line
global buffer
global lines

# initialize subplots for the graph
fig, ax = plt.subplots()

# initialize global variables
ofl = 0
idx = 0
x = list(np.arange(MAX_SIZE/10, 0, -0.1))
green_lst = [1] * MAX_SIZE
green_val = 0
green_line, = ax.plot(x, green_lst, 'g-')
red_lst = [1] * MAX_SIZE
red_val = 0
red_line, = ax.plot(x, red_lst, 'r-')
lines = [red_line, green_line]
buffer = Queue()

# if the command doesn't contain both Tail_PTU.py and the PTU file, the command will exit without an output
if len(sys.argv) != 2:
    print("USAGE: Tail_PTU.py newFile.ptu")
    exit(0)

inputfile = open(sys.argv[1], "rb")

# if the PTU file isn't a PicoQuant PTU file, exit and print error
magic = inputfile.read(8).decode("utf-8").strip('\0')
if magic != "PQTTTR":
    print("ERROR: Magic invalid, this is not a PTU file.")
    inputfile.close()
    exit(0)

inputfile.seek(0, os.SEEK_END) #End-of-file. Next read will get to EOF.

# set up plot's values
plt.title('Time Trace Live Plot')
plt.xlabel('Time [s]')
plt.ylabel('Counts per 100 ms bin')
plt.grid()
plt.yscale('log')
ax.set_ylim([1, MAX_HEIGHT])

# Used to animate the graph based off of what is being written into the PTU file
def animate(i):
    global ofl, green_lst, green_val, red_lst, red_val, buffer, lines
    # loop until the inputfile reads a new input
    while True:
        recordData = inputfile.read(4)
        if not recordData:
            break
        # split recordData into a list of 4 bytes in each element, since there's 4 bytes per 32 bit integer
        buffer.put("{0:0{1}b}".format(struct.unpack("<I", recordData)[0], 32))


    while not buffer.empty():
        recordData = buffer.get()
        special = int(recordData[0:1], base=2)
        channel = int(recordData[1:7], base=2)
        nsync = int(recordData[22:32], base=2)
        if special == 1:
            if channel == 0x3F: # Overflow
                # Number of overflows in nsync. If 0, it's an
                # old style single overflow
                if nsync == 0:
                    ofl += 1
                else:
                    ofl += nsync
            if ofl >= OVERFLOW_MAX: # once the overflow amount is over a threshold,
                # add the values into the graph's lists

                green_lst.append(green_val)
                green_lst = green_lst[-MAX_SIZE:]

                red_lst.append(red_val)
                red_lst = red_lst[-MAX_SIZE:]
                
                # draw new graph frame
                lines[RED-1].set_data(x, red_lst)
                lines[GREEN-1].set_data(x, green_lst)
                # reset the values, and finish the function call
                ofl = 0
                green_val = 0
                red_val = 0
                return lines
        else: # regular input channel to count 100 ms bins
            if int(channel) == GREEN:
                green_val += 1
            elif int(channel) == RED:
                red_val += 1

# FuncAnimation calls animate for the figure that was passed into it at every interval
ani = animation.FuncAnimation(fig, animate, interval=THOUSAND_MILLISECONDS / 10000.0, blit=True)

plt.show()
inputfile.close()
