# Modified code from PicoQuant
# Keno Goertz, PicoQUant GmbH, February 2018

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
import time
import matplotlib.widgets as widget
from queue import Queue

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

measDescRes = tagValues[tagNames.index("MeasDesc_Resolution")] # the resolution of the measurements being done for each dtime

inputfile.seek(0, os.SEEK_END) #End-of-file. Next read will get to EOF.

# global variables
global ofl
global green_lst
global red_lst
global green_bins
global red_bins
global TRACE_SIZE
global TRACE_OVERFLOW

# channel numbers
GREEN = 2
RED = 1

# number of overflows needed before plotting on graph
# calculation being done is 75 ns * 1023 (number of bits in nsync) * OVERFLOW_MAX
# this comes out to around 0.1 s per overflow, or 100 ms when OVERFLOW_MAX is 1300

# Change these values to modify bin size
TRACE_MS_BIN = 1
BIN_INPUT = 64

# Change this to modify the number of data points allowed on the graph
TRACE_SIZE = 100

OVERFLOW_SECOND = 13000
TRACE_OVERFLOW = OVERFLOW_SECOND * TRACE_MS_BIN / 1000
TRACE_HEIGHT = 50
HIST_HEIGHT = 1e5
THOUSAND_MILLISECONDS = 1000

# number of data points allowed on the graph
MAX_DTIME = 2**15-1
binMultiple = int(-(BIN_INPUT / -(measDescRes * 1e12))) # BIN_INPUT / 4 = 16x larger bins
NUM_BINS = int(-(MAX_DTIME // -binMultiple)) # "ceiling" division for number of bins needed

# initialize subplots for the graph
fig, (trace_ax, hist_ax) = plt.subplots(1, 2)
plt.subplots_adjust(left=0.1, right = 0.9, top=0.9, bottom=0.2)
# unbind default key bindings
fig.canvas.mpl_disconnect(fig.canvas.manager.key_press_handler_id)

# initialize global variables
ofl = 0
idx = 0
x = np.arange(0, TRACE_SIZE*np.float16(TRACE_OVERFLOW/13000), np.float16(TRACE_OVERFLOW/13000))
green_lst = np.ones(TRACE_SIZE, dtype=np.uint32, order='C')
green_trace, = trace_ax.plot(x, green_lst, 'g-')
red_lst = np.ones(TRACE_SIZE, dtype=np.uint32, order='C')
red_trace, = trace_ax.plot(x, red_lst, 'r-')

HIST_BINS = np.linspace(0, MAX_DTIME * measDescRes * 1e9, num=NUM_BINS, endpoint=True)
green_bins = np.ones(NUM_BINS, dtype=np.uint32, order='C')
green_hist, = hist_ax.plot(HIST_BINS, green_bins, 'g-')
red_bins = np.ones(NUM_BINS, dtype=np.uint32, order='C')
red_hist, = hist_ax.plot(HIST_BINS, red_bins, 'r-')

buffer = Queue()
# change the Trace Height with the value given by the trace height text box
def changeTraceHeight(value):
    TRACE_HEIGHT = int(value)
    trace_ax.set_ylim([1, TRACE_HEIGHT])

# change the Hist Height with the value given by the hist height text box
def changeHistHeight(value):
    HIST_HEIGHT = 10**int(value)
    hist_ax.set_ylim([10, HIST_HEIGHT])

# change the Trace Size with the value given by the trace size text box
def changeTraceSize(value):
    global TRACE_SIZE, green_lst, red_lst, x
    TRACE_SIZE = int(value)
    max_x = TRACE_SIZE*np.float16(TRACE_OVERFLOW/13000)
    x = np.arange(0, max_x, np.float16(TRACE_OVERFLOW/13000))
    green_lst = np.ones(TRACE_SIZE, dtype=np.uint32, order='C')
    red_lst = np.ones(TRACE_SIZE, dtype=np.uint32, order='C')
    trace_ax.set_xlim(0, max_x)

def changeTraceBins(value):
    global TRACE_OVERFLOW, x
    TRACE_OVERFLOW = OVERFLOW_SECOND * 10**int(value) / 1000
    max_x = TRACE_SIZE*np.float16(TRACE_OVERFLOW/13000)
    x = np.arange(0, max_x, np.float16(TRACE_OVERFLOW/13000))
    trace_ax.set_xlim(0, max_x)

# initializes the figure, axis, and passes artists through
def init_fig(fig, trace_ax, hist_ax, artists):
    # set up trace's values
    trace_ax.set_title('Time Trace Live Plot')
    trace_ax.set_xlabel('Time [s]')

    # set up hist's values
    hist_ax.set_title('Histogram Live Plot')
    hist_ax.set_xlabel('Time [ns]')
    hist_ax.set_ylabel('Counts per {size} ps bin'.format(size = int(BIN_INPUT)))
    hist_ax.grid(True)
    hist_ax.semilogy()
    hist_ax.set_xlim([0, 100])

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
def animate(buffer, red_trace, green_trace, red_hist, green_hist):
    global x, ofl, green_lst, red_lst, green_bins, red_bins, TRACE_SIZE

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
            # TODO
            # add an if statement that checks the size of the TRACE_OVERFLOW to swap between two different algorithms (the rolling one and the updating one)
            # also remember that if the trace 
            if ofl >= TRACE_OVERFLOW * TRACE_SIZE: # once the overflow amount is over a threshold,
                # add the values into the graph's lists
                # draw new trace frame
                red_trace.set_data(x, red_lst)
                green_trace.set_data(x, green_lst)
                # draw new histogram frame
                red_hist.set_data(HIST_BINS, red_bins)
                green_hist.set_data(HIST_BINS, green_bins)
                # reset the values, and finish the function call
                ofl = 0
                green_lst = np.ones(TRACE_SIZE, dtype=np.uint32, order='C')
                red_lst = np.ones(TRACE_SIZE, dtype=np.uint32, order='C')
                break
        else: # regular input channel to count 100 ms bins
            trace_indx = int(ofl // TRACE_OVERFLOW)
            hist_indx = int((dtime * measDescRes * 1e12)//BIN_INPUT)-1 # this bins out where the dtime corresponds to and which bin it should go into (by dividing it into binSize)
            if (trace_indx >= np.prod(green_lst.shape)):
                ofl = 0
            else:
                if int(channel) == GREEN:
                    green_lst[trace_indx] += 1
                elif int(channel) == RED:
                    red_lst[trace_indx] += 1

            if (hist_indx >= np.prod(green_bins.shape)):
                continue
            else:
                if int(channel) == GREEN:
                    green_bins[hist_indx] += 1
                elif int(channel) == RED:
                    red_bins[hist_indx] += 1
        
    return red_trace, green_trace, red_hist, green_hist

update = partial(animate, red_trace=red_trace, green_trace=green_trace, red_hist=red_hist, green_hist=green_hist)
init = partial(init_fig, fig=fig, trace_ax=trace_ax, hist_ax=hist_ax, artists=(red_trace,green_trace,red_hist,green_hist))

# FuncAnimation calls animate for the figure that was passed into it at every interval
ani = animation.FuncAnimation(fig=fig, func=update, frames=frame_iter, init_func = init, interval=THOUSAND_MILLISECONDS/10000.0, blit=True)

WIDGET_WIDTH = 0.047
WIDGET_HEIGHT = 0.027
WIDGET_Y = 0.005

trace_plot_position = trace_ax.get_position()
hist_plot_position = hist_ax.get_position()

# Add a slider for changing Trace size between 1 -> 10 -> 100
traceSizeAx = fig.add_axes([trace_plot_position.x0 + WIDGET_WIDTH * 3, WIDGET_Y + WIDGET_HEIGHT * 1.5, WIDGET_WIDTH, WIDGET_HEIGHT])
traceSizeBox = widget.TextBox(traceSizeAx, "Trace Size ")
traceSizeBox.on_text_change(changeTraceSize)
traceSizeBox.set_val(100)

# text box to change the trace height
traceHeightAx = fig.add_axes([trace_plot_position.x0, WIDGET_Y + WIDGET_HEIGHT * 1.5, WIDGET_WIDTH, WIDGET_HEIGHT])
traceHeightBox = widget.TextBox(traceHeightAx, "Trace Height ")
traceHeightBox.on_text_change(changeTraceHeight)
traceHeightBox.set_val(100)

# text box to change the hist height
histHeightAx = fig.add_axes([hist_plot_position.x0, WIDGET_Y + WIDGET_HEIGHT * 1.5, WIDGET_WIDTH * 1.5, WIDGET_HEIGHT])
histHeightBox = widget.TextBox(histHeightAx, "Hist Height 10^")
histHeightBox.on_text_change(changeHistHeight)
histHeightBox.set_val(5)

# TODO
# Add a slider to change Trace bin size between [1, 10, and 100]
traceBinAx = fig.add_axes([trace_plot_position.x0 + WIDGET_WIDTH * 2, WIDGET_Y, WIDGET_WIDTH * 2, WIDGET_HEIGHT])
traceBinSlider = widget.Slider(traceBinAx, "Trace Bin 10^", valmin=0, valmax=2, valinit=0, valstep=1)
traceBinSlider.on_changed(changeTraceBins)

# TODO
# Add a slider with 4^n for changing Histogram bins. i.e. [4, 16, 64, 256]

# TODO
# Add a cursor widget for selecting the four cursor lines alongside a button that resets the cursor positions
# This can be used for fret signal (DA) when adding the green_1, green_2, red_1, red_2 lines (in that order from left to right)

plt.show()
inputfile.close()
