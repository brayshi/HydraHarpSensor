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
import time
import sys
import struct
from functools import partial
import os
from queue import Queue
# static variables
# channel numbers
GREEN = 2
RED = 1


# number of overflows needed before plotting on graph
# calculation being done is 75 ns * 1023 (number of bits in nsync) * OVERFLOW_MAX
# this comes out to around 0.1 s per overflow, or 100 ms when OVERFLOW_MAX is 1300
OVERFLOW_MAX = 1300
MAX_HEIGHT = 1e5
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

version = inputfile.read(8).decode("utf-8").strip('\0')

tagDataList = []    # Contains tuples of (tagName, tagValue)
while True:
    tagIdent = inputfile.read(32).decode("utf-8").strip('\0')
    tagIdx = struct.unpack("<i", inputfile.read(4))[0]
    tagTyp = struct.unpack("<i", inputfile.read(4))[0]
    if tagIdx > -1:
        evalName = tagIdent + '(' + str(tagIdx) + ')'
    else:
        evalName = tagIdent
    if tagTyp == tyEmpty8:
        inputfile.read(8)
        tagDataList.append((evalName, "<empty Tag>"))
    elif tagTyp == tyBool8:
        tagInt = struct.unpack("<q", inputfile.read(8))[0]
        if tagInt == 0:
            tagDataList.append((evalName, "False"))
        else:
            tagDataList.append((evalName, "True"))
    elif tagTyp == tyInt8:
        tagInt = struct.unpack("<q", inputfile.read(8))[0]
        tagDataList.append((evalName, tagInt))
    elif tagTyp == tyBitSet64:
        tagInt = struct.unpack("<q", inputfile.read(8))[0]
        tagDataList.append((evalName, tagInt))
    elif tagTyp == tyColor8:
        tagInt = struct.unpack("<q", inputfile.read(8))[0]
        tagDataList.append((evalName, tagInt))
    elif tagTyp == tyFloat8:
        tagFloat = struct.unpack("<d", inputfile.read(8))[0]
        tagDataList.append((evalName, tagFloat))
    elif tagTyp == tyFloat8Array:
        tagInt = struct.unpack("<q", inputfile.read(8))[0]
        tagDataList.append((evalName, tagInt))
    elif tagTyp == tyTDateTime:
        tagFloat = struct.unpack("<d", inputfile.read(8))[0]
        tagTime = int((tagFloat - 25569) * 86400)
        tagTime = time.gmtime(tagTime)
        tagDataList.append((evalName, tagTime))
    elif tagTyp == tyAnsiString:
        tagInt = struct.unpack("<q", inputfile.read(8))[0]
        tagString = inputfile.read(tagInt).decode("utf-8").strip("\0")
        tagDataList.append((evalName, tagString))
    elif tagTyp == tyWideString:
        tagInt = struct.unpack("<q", inputfile.read(8))[0]
        tagString = inputfile.read(tagInt).decode("utf-16le", errors="ignore").strip("\0")
        tagDataList.append((evalName, tagString))
    elif tagTyp == tyBinaryBlob:
        tagInt = struct.unpack("<q", inputfile.read(8))[0]
        tagDataList.append((evalName, tagInt))
    else:
        print("ERROR: Unknown tag type")
        exit(0)
    if tagIdent == "Header_End":
        break

tagNames = [tagDataList[i][0] for i in range(0, len(tagDataList))]
tagValues = [tagDataList[i][1] for i in range(0, len(tagDataList))]
globRes = tagValues[tagNames.index("MeasDesc_GlobalResolution")] # the period of the histogram
measDescRes = tagValues[tagNames.index("MeasDesc_Resolution")] # the resolution of the measurements being done for each dtime

# global variables
global ofl
global green_lst
global red_lst

# initialize subplots for the graph
fig, ax = plt.subplots()

# number of data points allowed on the graph
binSize = measDescRes*16 # 4 ps * 16 = 64 ps bins
NUM_BINS = int(-(globRes // -binSize)) # "ceiling" division for number of bins needed

inputfile.seek(0, os.SEEK_END) #End-of-file. Next read will get to EOF.

# initialize global variables
ofl = 0
HIST_BINS = np.linspace(0, globRes*1e9, num=NUM_BINS, endpoint=True)
green_lst = np.ones(NUM_BINS, dtype=np.uint32, order='C')
green_line, = ax.plot(HIST_BINS, green_lst, 'g-')
red_lst = np.ones(NUM_BINS, dtype=np.uint32, order='C')
red_line, = ax.plot(HIST_BINS, red_lst, 'r-')
buffer = Queue()

# initializes the figure, axis, and passes artists through
def init_fig(fig, ax, artists):
    # set up plot's values
    plt.title('Histogram Live Plot')
    plt.xlabel('Time [ns]')
    plt.ylabel('Counts per 64 ps bin')
    plt.grid(True)
    plt.yscale('log')
    ax.set_ylim([10, MAX_HEIGHT])

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
# Used to animate the graph based off of what is being written into the PTU file
def animate(buffer, red_line, green_line):
    global ofl, green_lst, red_lst
    while not buffer.empty():
        recordData = buffer.get()
        special = int(recordData[0:1], base=2)
        channel = int(recordData[1:7], base=2)
        dtime = int(recordData[7:22], base=2)
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
                # draw new graph frame (OVERFLOW_MAX's value causes the graph to return every 100 ms)
                red_line.set_data(HIST_BINS, red_lst)
                green_line.set_data(HIST_BINS, green_lst)
                # reset the values, and finish the function call
                ofl = 0
                break
        else: # regular input channel to count bins
            indx = int((dtime * measDescRes)//binSize)-1 # this bins out where the dtime corresponds to and which bin it should go into (by dividing it into binSize)
            if int(channel) == GREEN:
                green_lst[indx] += 1
            elif int(channel) == RED:
                red_lst[indx] += 1
    return red_line, green_line

update = partial(animate, red_line=red_line, green_line=green_line)
init = partial(init_fig, fig=fig, ax=ax, artists=(red_line, green_line))

# FuncAnimation calls animate for the figure that was passed into it at every interval
ani = animation.FuncAnimation(fig=fig, func=update, frames=frame_iter, init_func = init, interval=THOUSAND_MILLISECONDS/10000.0, blit=True)

plt.show()
inputfile.close()
