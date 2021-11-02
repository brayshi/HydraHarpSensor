# Modified code from PicoQuant
# Keno Goertz, PicoQUant GmbH, February 2018

# We do not keep it in memory because of the huge amout of memory
# this would take in case of large files. Of course you can change this, 
# e.g. if your files are not too big. 
# Otherwise it is best process the data on the fly and keep only the results.

# Purpose: to be able to "tail" PTU files to create a live time trace of photon counts
# Modified by Brayden Shinkawa

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

MAX_BUFFER_SIZE = 100096 * 3
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
plt.subplots_adjust(left=0.1, right = 0.9, top=0.9, bottom=0.4)
# unbind default key bindings
fig.canvas.mpl_disconnect(fig.canvas.manager.key_press_handler_id)

trace = Trace()
hist = Histogram(measDescRes)

# initialize global variables
ofl = 0
green_trace, = trace_ax.plot(trace.period, trace.green_line, 'g-')
red_trace, = trace_ax.plot(trace.period, trace.red_line, 'r-')
fret_trace, = trace_ax.plot(trace.period, trace._fret_line, 'b-')

green_hist, = hist_ax.plot(hist.period, hist.green_bins, 'g-')
red_hist, = hist_ax.plot(hist.period, hist.red_bins, 'r-')

buffer = deque(maxlen=MAX_BUFFER_SIZE)
# change the Trace Height with the value given by the trace height text box
def changeTraceHeight(value):
    if int(value) == 0:
        traceHeightBox.set_val(1)
        return
    TRACE_HEIGHT = int(value)
    trace_ax.set_ylim([1, TRACE_HEIGHT])

# change the Hist Height with the value given by the hist height text box
def changeHistHeight(value):
    if int(value) < 0:
        histHeightBox.set_val(1)
    HIST_HEIGHT = 10**int(value)
    hist_ax.set_ylim([10, HIST_HEIGHT])

# change the Trace Size with the value given by the trace size text box
# if period is smaller than the bin_size_milliseconds, then set period to bin_size_milliseconds instead
def changeTracePeriod(value):
    if int(value) < trace.bin_size_milliseconds:
        traceSizeBox.set_val(trace.bin_size_milliseconds)
        return
    trace.period_milliseconds_next = int(value)

def changeTraceBins(value):
    # if trace bin_size_milliseconds is too big, set it to period
    if int(value) > trace.period_milliseconds:
        traceSizeBox.set_val(int(value))
        return
    trace.bin_size_milliseconds_next = int(value)

def changeHistBins(value):
    hist.bin_size_picoseconds_next = int(value)

# the next frame that goes through will be checked on by the green and red select functions
def greenSelectMin(xmin):
    if float(xmin) < 0:
        histGreenStartBox.set_val(0.0)
    elif float(xmin) > hist._green_range[1]:
        histGreenStartBox.set_val(hist._green_range[1])
    else:
        hist._green_range[0] = float(xmin)

def greenSelectMax(xmax):
    if float(xmax) > 75:
        histGreenEndBox.set_val(75.0)
    elif float(xmax) < hist._green_range[0]:
        histGreenEndBox.set_val(hist._green_range[0])
    else:
        hist._green_range[1] = float(xmax)

def redSelectMin(xmin):
    if float(xmin) < 0:
        histRedStartBox.set_val(0.0)
    elif float(xmin) > hist._red_range[1]:
        histRedStartBox.set_val(hist._red_range[1])
    else:
        hist._red_range[0] = float(xmin)

def redSelectMax(xmax):
    if float(xmax) > 75:
        histRedEndBox.set_val(75.0)
    elif float(xmax) < hist._red_range[0]:
        histRedEndBox.set_val(hist._red_range[0])
    else:
        hist._red_range[1] = float(xmax)

def booleanGreenTrace(event):
    if trace._green_on == True:
        trace._green_on = False
        green_trace.set_alpha(0)
    else:
        trace._green_on = True
        green_trace.set_alpha(1)

def booleanRedTrace(event):
    if trace._red_on == True:
        trace._red_on = False
        red_trace.set_alpha(0)
    else:
        trace._red_on = True
        red_trace.set_alpha(1)

def booleanFretTrace(event):
    if trace._fret_on == True:
        trace._fret_on = False
        fret_trace.set_alpha(0)
    else:
        trace._fret_on = True
        fret_trace.set_alpha(1)

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
    hist_ax.set_xlim([0, 80])

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
        ctypes.windll.user32.MessageBoxW(0, "WARNING_INPT_RATE_RATIO:\nThe pulse rate ratio R(ch)/R(sync) is over 5%\nfor at least one input channel.\nThis may cause pile-up and deadtime artifacts.", "WARNING", 0)
        message_window_on = True
    elif len(buffer) != MAX_BUFFER_SIZE and message_window_on == True:
        message_window_on = False
    
    yield buffer

# Used to animate the graph based off of what has been saved into the buffer
def animate(buffer, red_trace, green_trace, fret_trace, red_hist, green_hist):
    global ofl

    while buffer:
        
        recordData = buffer.popleft()
        special = recordData >> 31
        channel = (recordData >> 25) & 63
        dtime = (recordData >> 10) & 32767
        nsync = recordData & 1023

        trace_overflow = OVERFLOW_SECOND * trace.bin_size_milliseconds / CONVERT_SECONDS
        trace._DA_range = [hist._green_range[0]/(measDescRes*1e9), hist._green_range[1]/(measDescRes*1e9)]

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
                if trace._red_on == True:
                    red_trace.set_data(trace.period, trace.red_line)

                if trace._green_on == True:
                    green_trace.set_data(trace.period, trace.green_line)

                if trace._fret_on == True:
                    fret_trace.set_data(trace.period, trace._fret_line)

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
                
                # check if button was pressed to set the fret line on for the next trace
                break
        else: # regular input channel to count 100 ms bins
            # TODO
            # check if the items are in the boxes.
            # i.e. if the channel is red, check if it was excited within the green range of dtime
            # add a 
            trace_indx = int(ofl // trace_overflow)
            hist_indx = int((dtime * hist.measDescRes * 1e12)//hist.bin_size_picoseconds)-1
            if int(channel) == GREEN:
                trace.green_line[trace_indx] += 1
                hist.green_bins[hist_indx] += 1
            elif int(channel) == RED:
                # if in green area (trace._DD_range), put it in fret line. Else put in red line if it isn't
                # or if the fret button isn't on true
                if (trace._DA_range[0] <= dtime and dtime <= trace._DA_range[1]) and trace._fret_on == True:
                    trace._fret_line[trace_indx] += 1
                else:
                    trace.red_line[trace_indx] += 1
                hist.red_bins[hist_indx] += 1
                
        
    return red_trace, green_trace, fret_trace, red_hist, green_hist

update = partial(animate, red_trace=red_trace, green_trace=green_trace, fret_trace=fret_trace, red_hist=red_hist, green_hist=green_hist)
init = partial(init_fig, fig=fig, trace_ax=trace_ax, hist_ax=hist_ax, artists=(red_trace, green_trace, fret_trace, red_hist,green_hist))

# FuncAnimation calls animate for the figure that was passed into it at every interval
ani = animation.FuncAnimation(fig=fig, func=update, frames=frame_iter, init_func=init, interval=1, blit=True)

WIDGET_WIDTH = 0.040
WIDGET_HEIGHT = 0.027
X_PADDING = WIDGET_WIDTH * 2.75
Y_PADDING = WIDGET_HEIGHT * 1.5
PADDING_FROM_GRAPH = Y_PADDING * 3

trace_plot_position = trace_ax.get_position()
hist_plot_position = hist_ax.get_position()

def reconfigureTextBox(textBox):
    textBox.disconnect_events()
    textBox.connect_event('button_press_event', textBox._click)
    textBox.connect_event('button_release_event', textBox._release)
    textBox.connect_event('key_press_event', textBox._keypress)
    textBox.label.set_fontsize(7)

def reconfigureButton(button):
    button.disconnect_events()
    button.connect_event('button_press_event', button._click)
    button.connect_event('button_release_event', button._release)
    button.label.set_fontsize(7)

# text box to change the trace height
traceHeightAx = fig.add_axes([trace_plot_position.x0, trace_plot_position.y0 - PADDING_FROM_GRAPH, WIDGET_WIDTH, WIDGET_HEIGHT])
traceHeightBox = widget.TextBox(traceHeightAx, "Trace Height ")
traceHeightBox.on_submit(changeTraceHeight)
traceHeightBox.set_val(100)
reconfigureTextBox(traceHeightBox)

# Add a slider for changing Trace size between 1 -> 10 -> 100
traceSizeAx = fig.add_axes([trace_plot_position.x0, trace_plot_position.y0 - PADDING_FROM_GRAPH - Y_PADDING, WIDGET_WIDTH, WIDGET_HEIGHT])
traceSizeBox = widget.TextBox(traceSizeAx, "Trace Size (ms) ")
traceSizeBox.on_submit(changeTracePeriod)
traceSizeBox.set_val(1000)
reconfigureTextBox(traceSizeBox)

# slider that changes Trace bin size between [1, 10, and 100]
traceBinAx = fig.add_axes([trace_plot_position.x0, trace_plot_position.y0 - PADDING_FROM_GRAPH - Y_PADDING*2, WIDGET_WIDTH, WIDGET_HEIGHT])
traceBinBox = widget.TextBox(traceBinAx, "Trace Bin (ms) ")
traceBinBox.on_submit(changeTraceBins)
traceBinBox.set_val(1)
reconfigureTextBox(traceBinBox)

# text box to change the hist height
histHeightAx = fig.add_axes([hist_plot_position.x0, hist_plot_position.y0-PADDING_FROM_GRAPH, WIDGET_WIDTH, WIDGET_HEIGHT])
histHeightBox = widget.TextBox(histHeightAx, "Hist Height 10^")
histHeightBox.on_submit(changeHistHeight)
histHeightBox.set_val(5)
reconfigureTextBox(histHeightBox)

traceGreenAx = fig.add_axes([trace_plot_position.x0 + X_PADDING * 0.75, trace_plot_position.y0-PADDING_FROM_GRAPH, WIDGET_WIDTH*1.5, WIDGET_HEIGHT*1.25])
traceGreenButton = widget.Button(traceGreenAx, "Green Trace")  
traceGreenButton.on_clicked(booleanGreenTrace)
reconfigureButton(traceGreenButton)

traceRedAx = fig.add_axes([trace_plot_position.x0 + X_PADDING * 0.75, trace_plot_position.y0-PADDING_FROM_GRAPH-Y_PADDING, WIDGET_WIDTH*1.5, WIDGET_HEIGHT*1.25])
traceRedButton = widget.Button(traceRedAx, "Red Trace")
traceRedButton.on_clicked(booleanRedTrace)
reconfigureButton(traceRedButton)

traceFretAx = fig.add_axes([trace_plot_position.x0 + X_PADDING * 0.75, trace_plot_position.y0 - PADDING_FROM_GRAPH - Y_PADDING*2, WIDGET_WIDTH*1.5, WIDGET_HEIGHT*1.25])
traceFretButton = widget.Button(traceFretAx, "Fret Trace")
traceFretButton.on_clicked(booleanFretTrace)
reconfigureButton(traceFretButton)

# slider with 4^n for changing Histogram bins. i.e. [16, 64, 256]
histBinAx = fig.add_axes([hist_plot_position.x0, hist_plot_position.y0 - PADDING_FROM_GRAPH - Y_PADDING, WIDGET_WIDTH, WIDGET_HEIGHT])
histBinBox = widget.TextBox(histBinAx, "Hist Bin (ps) ")
histBinBox.on_submit(changeHistBins)
histBinBox.set_val(64)
reconfigureTextBox(histBinBox)

histGreenStartAx = fig.add_axes([hist_plot_position.x0 + X_PADDING, hist_plot_position.y0 - PADDING_FROM_GRAPH, WIDGET_WIDTH, WIDGET_HEIGHT])
histGreenStartBox = widget.TextBox(histGreenStartAx, "Green x min (ns) ")
histGreenStartBox.on_submit(greenSelectMin)
histGreenStartBox.set_val(5.0)
reconfigureTextBox(histGreenStartBox)

histGreenEndAx = fig.add_axes([hist_plot_position.x0 + X_PADDING, hist_plot_position.y0 - PADDING_FROM_GRAPH - Y_PADDING, WIDGET_WIDTH, WIDGET_HEIGHT])
histGreenEndBox = widget.TextBox(histGreenEndAx, "Green x max (ns) ")
histGreenEndBox.on_submit(greenSelectMax)
histGreenEndBox.set_val(40.0)
reconfigureTextBox(histGreenEndBox)

histRedStartAx = fig.add_axes([hist_plot_position.x0 + X_PADDING*2, hist_plot_position.y0 - PADDING_FROM_GRAPH, WIDGET_WIDTH, WIDGET_HEIGHT])
histRedStartBox = widget.TextBox(histRedStartAx, "Red x min (ns) ")
histRedStartBox.on_submit(redSelectMin)
histRedStartBox.set_val(0.0)
reconfigureTextBox(histRedStartBox)

histRedEndAx = fig.add_axes([hist_plot_position.x0 + X_PADDING*2, hist_plot_position.y0 - PADDING_FROM_GRAPH - Y_PADDING, WIDGET_WIDTH, WIDGET_HEIGHT])
histRedEndBox = widget.TextBox(histRedEndAx, "Red x max (ns) ")
histRedEndBox.on_submit(redSelectMax)
histRedEndBox.set_val(75.0)
reconfigureTextBox(histRedEndBox)

plt.show()
inputfile.close()
