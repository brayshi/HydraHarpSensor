import numpy as np

# the amount of overflows needed for a 1 ms overflow update
OVERFLOW_MILLISECOND = 13
HIST_BIN_AMOUNT = 2**15-1
CONVERT_SECONDS = 1000

class Histogram:

    @property
    def height(self):
        return self._height
    
    @height.setter
    def height(self, value):
        self._height = value

    @property
    def bin_size_picoseconds(self):
        return self._bin_size_picoseconds

    @bin_size_picoseconds.setter
    def bin_size_picoseconds(self, value):
        self._bin_size_picoseconds = value

    @property
    def bin_size_picoseconds_next(self):
        return self._bin_size_picoseconds_next

    @bin_size_picoseconds_next.setter
    def bin_size_picoseconds_next(self, value):
        self._bin_size_picoseconds_next = value

    @property
    def measDescRes(self):
        return self._measDescRes

    @property
    def green_bins(self):
        return self._green_bins

    @green_bins.setter
    def green_bins(self, indx):
        self._green_bins[indx] += 1

    @property
    def red_bins(self):
        return self._red_bins

    @red_bins.setter
    def red_bins(self, indx):
        self._red_bins[indx] += 1

    @property
    def period(self):
        return self._period

    def change_hist(self):
        binMultiple = int(-(self.bin_size_picoseconds // -(self.measDescRes * 1e12)))
        num_bins = int(-(HIST_BIN_AMOUNT // -binMultiple))
        self._period = np.linspace(0, HIST_BIN_AMOUNT * self.measDescRes * 1e9, num=num_bins, endpoint=True)
        self._green_bins = np.ones(num_bins, dtype=np.uint32, order='C')
        self._red_bins = np.ones(num_bins, dtype=np.uint32, order='C')

    def __init__(self, measDescRes):
        self._height = 1e5
        self._period_picoseconds = 100000 # will convert this to nanoseconds for period
        self._bin_size_picoseconds = 64 # can only be 16, 64, and 256
        self._bin_size_picoseconds_next = 64 # the next value for bin size that will be applied later
        self._measDescRes = measDescRes
        binMultiple = int(-(self.bin_size_picoseconds // -(self.measDescRes * 1e12)))
        num_bins = int(-(HIST_BIN_AMOUNT // -binMultiple))
        self._period = np.linspace(0, HIST_BIN_AMOUNT * self.measDescRes * 1e9, num=num_bins, endpoint=True)
        self._green_bins = np.ones(num_bins, dtype=np.uint32, order='C')
        self._red_bins = np.ones(num_bins, dtype=np.uint32, order='C')