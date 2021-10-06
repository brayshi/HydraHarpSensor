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
from functools import partial
from queue import Queue
# static variables
# channel numbers
GREEN = 2
RED = 1

# number of data points allowed on the graph
MAX_SIZE = 1000
MILLISECOND_CONVERSION = float(1.0/MAX_SIZE) 
# number of overflows needed before plotting on graph
# calculation being done is 75 ns * 1023 (number of bits in nsync) * OVERFLOW_MAX
# this comes out to around 0.1 s per overflow, or 100 ms when OVERFLOW_MAX is 1300
OVERFLOW_MAX = 1300/100
MAX_HEIGHT = 50
THOUSAND_MILLISECONDS = 1000

# global variables
global ofl
global green_lst
global green_val
global red_lst
global red_val

# initialize subplots for the graph
fig, ax = plt.subplots()

# initialize global variables
ofl = 0
idx = 0
x = list(np.arange(MAX_SIZE/10, 0, -0.1))
green_lst = np.ones(MAX_SIZE, dtype=np.uint32, order='C')
green_val = 0
green_line, = ax.plot(x, green_lst, 'g-')
red_lst = np.ones(MAX_SIZE, dtype=np.uint32, order='C')
red_val = 0
red_line, = ax.plot(x, red_lst, 'r-')
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

# initializes the figure, axis, and passes artists through
def init_fig(fig, ax, artists):
    # set up plot's values
    plt.title('Time Trace Live Plot')
    plt.xlabel('Time [s]')
    plt.ylabel('Counts per 1 ms bin')
    ax.set_ylim([1, MAX_HEIGHT])

    return artists

# saves information from PTU file for the next animated frame
def frame_iter():
    global buffer
    while True:
        recordData = inputfile.read(4)
        if not recordData:
            break
        # split recordData into a list of 4 bytes in each element, since there's 4 bytes per 32 bit integer
        buffer.put("{0:0{1}b}".format(struct.unpack("<I", recordData)[0], 32))
    
    yield buffer

# Used to animate the graph based off of what has been saved into the buffer
def animate(buffer, red_line, green_line):
    global ofl, green_lst, green_val, red_lst, red_val

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

                green_lst = np.roll(green_lst, -1)
                green_lst[MAX_SIZE-1] = green_val
                red_lst = np.roll(red_lst, -1)
                red_lst[MAX_SIZE-1] = red_val
                # draw new graph frame
                red_line.set_data(x, red_lst)
                green_line.set_data(x, green_lst)
                # reset the values, and finish the function call
                ofl = 0
                green_val = 0
                red_val = 0
                break
        else: # regular input channel to count 100 ms bins
            if int(channel) == GREEN:
                green_val += 1
            elif int(channel) == RED:
                red_val += 1
    return red_line, green_line

update = partial(animate, red_line=red_line, green_line=green_line)
init = partial(init_fig, fig=fig, ax=ax, artists=(red_line,green_line))

# FuncAnimation calls animate for the figure that was passed into it at every interval
ani = animation.FuncAnimation(fig=fig, func=update, frames=frame_iter, init_func = init, interval=THOUSAND_MILLISECONDS/10000.0, blit=True)

plt.show()
inputfile.close()