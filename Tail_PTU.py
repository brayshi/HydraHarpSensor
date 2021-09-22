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
import sys
import struct
import os
from queue import Queue
# static variables
# channel numbers
GREEN = 2
RED = 1

# number of data points allowed on the graph
MAX_SIZE = 10
MILLISECOND_CONVERSION = float(1.0/MAX_SIZE) 
# number of overflows needed before plotting on graph
# calculation being done is 75 ns * 1023 (number of bits in nsync) * OVERFLOW_MAX
# this comes out to around 0.1 s per overflow, or 100 ms when OVERFLOW_MAX is 1300
OVERFLOW_MAX = 1300

# max number of data points on the graph at a time

MAX_HEIGHT = 500
THOUSAND_MILLISECONDS = 1000

# Tag Types
tyEmpty8      = struct.unpack(">i", bytes.fromhex("FFFF0008"))[0]
tyBool8       = struct.unpack(">i", bytes.fromhex("00000008"))[0]
tyInt8        = struct.unpack(">i", bytes.fromhex("10000008"))[0]
tyBitSet64    = struct.unpack(">i", bytes.fromhex("11000008"))[0]
tyColor8      = struct.unpack(">i", bytes.fromhex("12000008"))[0]
tyFloat8      = struct.unpack(">i", bytes.fromhex("20000008"))[0]
tyTDateTime   = struct.unpack(">i", bytes.fromhex("21000008"))[0]
tyFloat8Array = struct.unpack(">i", bytes.fromhex("2001FFFF"))[0]
tyAnsiString  = struct.unpack(">i", bytes.fromhex("4001FFFF"))[0]
tyWideString  = struct.unpack(">i", bytes.fromhex("4002FFFF"))[0]
tyBinaryBlob  = struct.unpack(">i", bytes.fromhex("FFFFFFFF"))[0]

# Record types
rtPicoHarpT3     = struct.unpack(">i", bytes.fromhex('00010303'))[0]
rtPicoHarpT2     = struct.unpack(">i", bytes.fromhex('00010203'))[0]
rtHydraHarpT3    = struct.unpack(">i", bytes.fromhex('00010304'))[0]
rtHydraHarpT2    = struct.unpack(">i", bytes.fromhex('00010204'))[0]
rtHydraHarp2T3   = struct.unpack(">i", bytes.fromhex('01010304'))[0]
rtHydraHarp2T2   = struct.unpack(">i", bytes.fromhex('01010204'))[0]
rtTimeHarp260NT3 = struct.unpack(">i", bytes.fromhex('00010305'))[0]
rtTimeHarp260NT2 = struct.unpack(">i", bytes.fromhex('00010205'))[0]
rtTimeHarp260PT3 = struct.unpack(">i", bytes.fromhex('00010306'))[0]
rtTimeHarp260PT2 = struct.unpack(">i", bytes.fromhex('00010206'))[0]
rtMultiHarpT3    = struct.unpack(">i", bytes.fromhex('00010307'))[0]
rtMultiHarpT2    = struct.unpack(">i", bytes.fromhex('00010207'))[0]

# global variables
global inputfile
global x
global ofl
global idx
global green_lst
global green_val
global red_lst
global red_val
global buffer

ofl = 0
idx = 0
# get to the part where it starts reciting numbers at the beginning
x = []
green_lst = []
green_val = 0
red_lst = []
red_val = 0
buffer = Queue()

fig, ax = plt.subplots()

if len(sys.argv) != 2:
    print("USAGE: Tail_PTU.py newFile.ptu")
    exit(0)

inputfile = open(sys.argv[1], "rb")

magic = inputfile.read(8).decode("utf-8").strip('\0')
if magic != "PQTTTR":
    print("ERROR: Magic invalid, this is not a PTU file.")
    inputfile.close()
    exit(0)

inputfile.seek(0, os.SEEK_END) #End-of-file. Next read will get to EOF.

plt.ylim([0, MAX_HEIGHT])
plt.title('Time Trace Live Plot')
plt.xlabel('Time [s]')
plt.ylabel('Counts per 100 ms bin')

# if we split the line and its second item is OFL, add the 4th item to OFL_number value  
# else split the value between green and red (for now. Figure out the FRET between number later)
# once OFL amount hits 1300 overflows, append new value totals into y_green and y_red lists



def animate(i):
    global inputfile, ofl, idx, x, green_lst, green_val, red_lst, red_val, buffer
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
                # plot the values presented on the graph
                x.append(float(idx*MILLISECOND_CONVERSION))
                x = x[-MAX_SIZE:]

                green_lst.append(green_val)
                green_lst = green_lst[-MAX_SIZE:]

                red_lst.append(red_val)
                red_lst = red_lst[-MAX_SIZE:]

                plt.cla()
                plt.ylim([0, MAX_HEIGHT])
                plt.title('Live Time Trace')
                plt.xlabel('Time [s]')
                plt.ylabel('Counts per 100 ms bin')
                plt.plot(x, green_lst, 'g-')
                plt.plot(x, red_lst, 'r-')

                ofl = 0
                green_val = 0
                red_val = 0

                idx += 1
                break
        else: # regular input channel to count 100 ms bins
            if int(channel) == GREEN:
                green_val += 1
            elif int(channel) == RED:
                red_val += 1

ani = animation.FuncAnimation(fig, animate, interval=THOUSAND_MILLISECONDS / 10000.0)

plt.show()
inputfile.close()
