import numpy as np

# the amount of overflows needed for a 1 ms overflow update
OVERFLOW_MILLISECOND = 13
HIST_BIN_AMOUNT = 2**15-1
CONVERT_SECONDS = 1000

class Trace():

    @property
    def bin_size_milliseconds(self):
        return self._bin_size_milliseconds

    @bin_size_milliseconds.setter
    def bin_size_milliseconds(self, value):
        self._bin_size_milliseconds = value

    @property
    def bin_size_milliseconds_next(self):
        return self._bin_size_milliseconds_next

    @bin_size_milliseconds_next.setter
    def bin_size_milliseconds_next(self, value):
        self._bin_size_milliseconds_next = value
    
    @property
    def period_milliseconds(self):
        return self._period_milliseconds
    
    @period_milliseconds.setter
    def period_milliseconds(self, value):
        self._period_milliseconds = value

    @property
    def period_milliseconds_next(self):
        return self._period_milliseconds_next

    @period_milliseconds_next.setter
    def period_milliseconds_next(self, value):
        self._period_milliseconds_next = value

    @property
    def height(self):
        return self._height
    
    @height.setter
    def height(self, value):
        self._height = value
    
    @property
    def period(self):
        return self._period

    @property
    def green_line(self):
        return self._green_line

    @green_line.setter
    def green_line(self, indx):
        if (self._bin_size_milliseconds >= 100):
            self._green_line = np.roll(self._green_line, -1) # remove oldest value
            self._green_line[np.prod(self._period.size)-1] += 1
        else:
            print("before:", self._green_line)
            self._green_line[indx] += 1
            print("after:", self._green_line)
    
    @property
    def red_line(self):
        return self._red_line
    
    @red_line.setter
    def red_line(self, indx):
        if (self._bin_size_milliseconds >= 100):
            print(self._red_line)
            self._red_line = np.roll(self._red_line, -1) # remove oldest value
            self._red_line[np.prod(self._period.size)-1] += 1
            print(self._red_line)
        else:
            self._red_line[indx] += 1

    def change_traces(self):
        self._period = np.arange(0, self.period_milliseconds / CONVERT_SECONDS, step=self.bin_size_milliseconds / CONVERT_SECONDS)
        self._green_line = np.ones(int(-(self._period_milliseconds//-self._bin_size_milliseconds)), dtype=np.uint32, order='C')
        self._red_line = np.ones(int(-(self._period_milliseconds//-self._bin_size_milliseconds)), dtype=np.uint32, order='C')
        self._fret_line = np.zeros(int(-(self._period_milliseconds//-self._bin_size_milliseconds)), dtype=np.uint32, order='C')

    def __init__(self):
        super().__init__()

        self._height = 100 # the height of the graph
        self._period_milliseconds = 1000 # can only be in multiples of 100. i.e. 100, 200, 300, 400, ..., 900, 1000 (max)
        self._period_milliseconds_next = 100 # the next period size in milliseconds that will be used
        self._bin_size_milliseconds = 1 # only 3 choices will be 1, 10, and 100 ms
        self._bin_size_milliseconds_next = 1 # the next bin size in milliseconds that will be used
        self._period = np.arange(0, self._period_milliseconds / CONVERT_SECONDS, step=self._bin_size_milliseconds / CONVERT_SECONDS)
        self._green_line = np.zeros(int(-(self._period_milliseconds//-self._bin_size_milliseconds)), dtype=np.uint32, order='C')
        self._red_line = np.zeros(int(-(self._period_milliseconds//-self._bin_size_milliseconds)), dtype=np.uint32, order='C')
        
        # fret variables
        self._DA_range = np.array([0, 2**15 - 1])

        self._fret_line = np.zeros(int(-(self._period_milliseconds//-self._bin_size_milliseconds)), dtype=np.uint32, order='C')

        # these check if the traces will be used
        self._green_on = True
        self._red_on = True
        self._fret_on = False