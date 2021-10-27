# Modified code from PicoQuant
# Keno Goertz, PicoQUant GmbH, February 2018

# We do not keep it in memory because of the huge amout of memory
# this would take in case of large files. Of course you can change this, 
# e.g. if your files are not too big. 
# Otherwise it is best process the data on the fly and keep only the results.

# Purpose: to be able to "tail" PTU files to create a live time trace of photon counts
# Modified by Brayden Shinkawa

from tkinter.constants import TRUE
import ReadFile
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
import sys
import struct
from functools import partial
from Trace import CONVERT_SECONDS, Trace
from Histogram import Histogram
import matplotlib.widgets as widget
from collections import deque
import ctypes

# global variables
global ofl

# channel numbers
GREEN = 2
RED = 1

MAX_BUFFER_SIZE = 100096
BUFFER_READ = 256

# number of overflows needed before plotting on graph
# calculation being done is 75 ns * 1023 (number of bits in nsync) * OVERFLOW_MAX
# this comes out to around 0.1 s per overflow, or 100 ms when OVERFLOW_MAX is 1300

OVERFLOW_SECOND = 13000

# message window on boolean
message_window_on = False

inputfile = ReadFile.confirmHeader(sys.argv)
measDescRes = ReadFile.readHeader(inputfile)

# initialize subplots for the graph
fig, (trace_ax, hist_ax) = plt.subplots(1, 2)
plt.subplots_adjust(left=0.1, right = 0.9, top=0.9, bottom=0.2)
# unbind default key bindings
fig.canvas.mpl_disconnect(fig.canvas.manager.key_press_handler_id)

trace = Trace()
hist = Histogram(measDescRes)

# initialize global variables
ofl = 0
green_trace, = trace_ax.plot(trace.period, trace.green_line, 'g-')
red_trace, = trace_ax.plot(trace.period, trace.red_line, 'r-')

green_hist, = hist_ax.plot(hist.period, hist.green_bins, 'g-')
red_hist, = hist_ax.plot(hist.period, hist.red_bins, 'r-')

buffer = deque(maxlen=MAX_BUFFER_SIZE)
# change the Trace Height with the value given by the trace height text box
def changeTraceHeight(value):
    if int(value) == 0:
        traceHeightBox.set_val(1)
        print("Can't have a height of 0")
        return
    TRACE_HEIGHT = int(value)
    trace_ax.set_ylim([1, TRACE_HEIGHT])

# change the Hist Height with the value given by the hist height text box
def changeHistHeight(value):
    if int(value) < 0:
        histHeightBox.set_val(1)
        print("Can only have an integer height")
    HIST_HEIGHT = 10**int(value)
    hist_ax.set_ylim([10, HIST_HEIGHT])

# change the Trace Size with the value given by the trace size text box
# if period is smaller than the bin_size_milliseconds, then set period to bin_size_milliseconds instead
def changeTracePeriod(value):
    if int(value) < trace.bin_size_milliseconds:
        traceSizeBox.set_val(trace.bin_size_milliseconds)
        print("trace period has to be larger than the bin size")
        return
    trace.period_milliseconds_next = int(value)

def changeTraceBins(value):
    # if trace bin_size_milliseconds is too big, set it to period
    if 10**int(value) > trace.period_milliseconds:
        traceSizeBox.set_val(10**int(value))
        print("trace bin size has to fit in period")
        return
    trace.bin_size_milliseconds_next = 10**int(value)

def changeHistBins(value):
    hist.bin_size_picoseconds_next = 4**int(value)


# initializes the figure, axis, and passes artists through
def init_fig(fig, trace_ax, hist_ax, artists):
    # set up trace's values
    trace_ax.set_title('Time Trace Live Plot')
    trace_ax.set_xlabel('Time [s]')

    # set up hist's values
    hist_ax.set_title('Histogram Live Plot')
    hist_ax.set_xlabel('Time [ns]')
    hist_ax.grid(True)
    hist_ax.semilogy()
    hist_ax.set_xlim([0, 100])

    return artists

# saves information from PTU file for the next animated frame
def frame_iter():
    global buffer, message_window_on
    while True:
        recordData = inputfile.read(BUFFER_READ)
        if not recordData:
            break
        # split recordData into a list of 4 bytes in each element, since there's 4 bytes per 32 bit integer
        for i in range(0, len(recordData), 4):
            buffer.append(struct.unpack("<I", recordData[i:i+4])[0])

    # if len(buffer) is equal to the maximum buffer size, then pop up warning window
    if len(buffer) == MAX_BUFFER_SIZE and message_window_on == False:
        ctypes.windll.user32.MessageBoxW(0, "Photon pile up is occuring. Data won't be accurate", "WARNING", 0)
        message_window_on = True
    elif len(buffer) != MAX_BUFFER_SIZE and message_window_on == True:
        message_window_on = False
    
    yield buffer

# Used to animate the graph based off of what has been saved into the buffer
def animate(buffer, red_trace, green_trace, red_hist, green_hist):
    global ofl

    while buffer:
        
        recordData = buffer.popleft()
        special = recordData >> 31
        channel = (recordData >> 25) & 63
        dtime = (recordData >> 10) & 32767
        nsync = recordData & 1023

        trace_overflow = OVERFLOW_SECOND * trace.bin_size_milliseconds / CONVERT_SECONDS

        if special == 1:
            if channel == 0x3F: # Overflow
                # Number of overflows in nsync. If 0, it's an
                # old style single overflow
                if nsync == 0:
                    ofl += 1
                else:
                    ofl += nsync
            if ofl >= trace_overflow * np.prod(trace.period.shape): # once the overflow amount is over a threshold,
                # add the values into the graph's lists
                # draw new trace frame
                red_trace.set_data(trace.period, trace.red_line)
                green_trace.set_data(trace.period, trace.green_line)
                # draw new histogram frame
                red_hist.set_data(hist.period, hist.red_bins)
                green_hist.set_data(hist.period, hist.green_bins)
                # reset the values, and finish the function call
                ofl = 0
                trace.period_milliseconds = trace.period_milliseconds_next
                trace.bin_size_milliseconds = trace.bin_size_milliseconds_next
                if trace.bin_size_milliseconds > trace.period_milliseconds:
                    trace.period_milliseconds = trace.bin_size_milliseconds
                trace.change_traces()
                trace_ax.set_xlim([0, trace.period_milliseconds / CONVERT_SECONDS])
                if (hist.bin_size_picoseconds != hist.bin_size_picoseconds_next):
                    hist.bin_size_picoseconds = hist.bin_size_picoseconds_next
                    hist.change_hist()
                break
        else: # regular input channel to count 100 ms bins
            trace_indx = int(ofl // trace_overflow)
            hist_indx = int((dtime * hist.measDescRes * 1e12)//hist.bin_size_picoseconds)-1
            if int(channel) == GREEN:
                trace.green_line[trace_indx] += 1
                hist.green_bins[hist_indx] += 1
            elif int(channel) == RED:
                trace.red_line[trace_indx] += 1
                hist.red_bins[hist_indx] += 1
                
        
    return red_trace, green_trace, red_hist, green_hist

update = partial(animate, red_trace=red_trace, green_trace=green_trace, red_hist=red_hist, green_hist=green_hist)
init = partial(init_fig, fig=fig, trace_ax=trace_ax, hist_ax=hist_ax, artists=(red_trace,green_trace,red_hist,green_hist))

# FuncAnimation calls animate for the figure that was passed into it at every interval
ani = animation.FuncAnimation(fig=fig, func=update, frames=frame_iter, init_func=init, interval=1, blit=True)

WIDGET_WIDTH = 0.047
WIDGET_HEIGHT = 0.027
WIDGET_Y = 0.005

trace_plot_position = trace_ax.get_position()
hist_plot_position = hist_ax.get_position()

def reconfigureTextBox(textBox):
    textBox.disconnect_events()
    textBox.connect_event('button_press_event', textBox._click)
    textBox.connect_event('button_release_event', textBox._release)
    textBox.connect_event('key_press_event', textBox._keypress)


# Add a slider for changing Trace size between 1 -> 10 -> 100
traceSizeAx = fig.add_axes([trace_plot_position.x0 + WIDGET_WIDTH * 3, WIDGET_Y + WIDGET_HEIGHT * 1.5, WIDGET_WIDTH, WIDGET_HEIGHT])
traceSizeBox = widget.TextBox(traceSizeAx, "Trace Size (ms) ")
traceSizeBox.on_submit(changeTracePeriod)
traceSizeBox.set_val(1000)
reconfigureTextBox(traceSizeBox)

# text box to change the trace height
traceHeightAx = fig.add_axes([trace_plot_position.x0, WIDGET_Y + WIDGET_HEIGHT * 1.5, WIDGET_WIDTH, WIDGET_HEIGHT])
traceHeightBox = widget.TextBox(traceHeightAx, "Trace Height ")
traceHeightBox.on_submit(changeTraceHeight)
traceHeightBox.set_val(100)
reconfigureTextBox(traceHeightBox)

# text box to change the hist height
histHeightAx = fig.add_axes([hist_plot_position.x0, WIDGET_Y + WIDGET_HEIGHT * 1.5, WIDGET_WIDTH * 1.5, WIDGET_HEIGHT])
histHeightBox = widget.TextBox(histHeightAx, "Hist Height 10^")
histHeightBox.on_submit(changeHistHeight)
histHeightBox.set_val(5)
reconfigureTextBox(histHeightBox)

# slider that changes Trace bin size between [1, 10, and 100]
traceBinAx = fig.add_axes([trace_plot_position.x0 + WIDGET_WIDTH * 2, WIDGET_Y, WIDGET_WIDTH * 2, WIDGET_HEIGHT])
traceBinSlider = widget.Slider(traceBinAx, "Trace Bin (ms) 10^", valmin=0, valmax=2, valinit=0, valstep=1)
traceBinSlider.on_changed(changeTraceBins)

# slider with 4^n for changing Histogram bins. i.e. [16, 64, 256]
histBinAx = fig.add_axes([hist_plot_position.x0, WIDGET_Y, WIDGET_WIDTH * 2, WIDGET_HEIGHT])
histBinSlider = widget.Slider(histBinAx, "Hist Bin (ps) 4^", valmin=2, valmax=4, valinit=3, valstep=1)
histBinSlider.on_changed(changeHistBins)

# TODO
# Add a cursor widget for selecting the four cursor lines alongside a button that resets the cursor positions
# This can be used for fret signal (DA) when adding the green_1, green_2, red_1, red_2 lines (in that order from left to right)

plt.show()
inputfile.close()
