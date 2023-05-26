"""Testing the autoplot app for live plotting and performance.

To change what kind of data to plot, modify the data source in the main script at the bottom.

Structure:
To be able to pass data in given intervals to the the autoplot window, we implement a DataSource object
that lives in a different thread from the GUI.
It's .data method should return a generator or other iterable.
In given intervals, the next data is then passed to the plotting app until the iterable is exhausted.
"""

import logging
import sys
from time import time, sleep
from typing import Iterable

import numpy as np

from plottr import QtCore, QtWidgets, Signal
from plottr import log as plottrlog
from plottr.apps.autoplot import autoplot
from plottr.data.datadict import DataDictBase, DataDict
from plottr.plot.mpl.autoplot import AutoPlot as MPLAutoPlot
from plottr.plot.pyqtgraph.autoplot import AutoPlot as PGAutoPlot
from plottr.utils import testdata

plottrlog.enableStreamHandler(True, level=logging.DEBUG)
logger = plottrlog.getLogger('plottr.test.autoplot_app')


class DataSource(QtCore.QObject):
    """Abstract data source. For specific data, implement a child class."""
    dataready = Signal(object)
    nomoredata = Signal()
    initialdelay: float = 1.0
    delay: float = 0.0

    def data(self) -> Iterable[DataDictBase]:
        raise NotImplementedError

    def gimmesomedata(self) -> None:
        _nsets = 0
        sleep(self.initialdelay)

        _t0 = time()
        logger.info("DataSource: start producing data.")
        for d in self.data():
            logger.info(f"DataSource: producing set {_nsets}")
            self.dataready.emit(d)
            _nsets += 1
            sleep(self.delay)
        logger.info(f"DataSource: Finished production after {time() - _t0} s")
        self.nomoredata.emit()


class LineDataMovie(DataSource):
    """Produce a series of dummy line data (each rep reproduces the full set with different noise)"""

    def __init__(self, nreps: int = 1, nsets: int = 3, nsamples: int = 51):
        super().__init__(None)
        self.nreps = nreps
        self.nsets = nsets
        self.nsamples = nsamples

    def data(self) -> Iterable[DataDictBase]:
        for i in range(self.nreps):
            yield testdata.get_1d_scalar_cos_data(self.nsamples, self.nsets)


class ImageDataMovie(DataSource):
    """Produce a series of dummy image data (each rep reproduces the full set with different noise)"""

    def __init__(self, nreps: int = 1, nsets: int = 2, nx: int = 21):
        super().__init__(None)
        self.nreps = nreps
        self.nsets = nsets
        self.nx = nx

    def data(self) -> Iterable[DataDictBase]:
        for i in range(self.nreps):
            data = testdata.get_2d_scalar_cos_data(self.nx, self.nx, self.nsets)
            yield data


class ImageDataLiveAcquisition(DataSource):
    """Produce a set of image data with a size that increases in chunks every interval."""

    def __init__(self, nrows: int = 10, ncols=10, chunksize=10):
        super().__init__(None)
        self.nrows = nrows
        self.ncols = ncols
        self.chunksize = chunksize

    def data(self) -> Iterable[DataDictBase]:
        fulldata = testdata.get_2d_scalar_cos_data(self.nrows, self.ncols)
        idx = 0
        size = self.nrows * self.ncols
        if size == 0:
            raise ValueError('Data has size zero.')

        data = fulldata.structure(same_type=True)
        assert isinstance(data, DataDictBase)

        while idx < size:
            idx += self.chunksize
            if idx >= size:
                idx = size
            for k, v in fulldata.data_items():
                data[k]['values'] = fulldata.data_vals(k)[:idx]
            yield data
        yield data


class ComplexImage(DataSource):
    """Produce a complex image."""

    def __init__(self, nx: int = 10, ny: int = 10):
        super().__init__(None)
        self.nx = nx
        self.ny = ny

    def data(self) -> Iterable[DataDictBase]:
        x = np.linspace(0, 10, self.nx)
        y = np.linspace(0, 2 * np.pi, self.ny)
        xx, yy = np.meshgrid(x, y, indexing='ij')
        zz = np.exp(-1j * (0.5 * xx + yy))
        data = DataDict(
            time=dict(values=xx.flatten()),
            phase=dict(values=yy.flatten()),
            data=dict(values=zz.flatten(), axes=['time', 'phase']),
            conjugate=dict(values=zz.conj().flatten(), axes=['time', 'phase'])
        )
        data.add_meta("title", "A complex data image (phasor vs time and phase)")
        data.add_meta("info", "This is a test data set to test complex data display.")
        yield data


def main(dataSrc):
    plottrlog.LEVEL = logging.DEBUG

    app = QtWidgets.QApplication([])
    fc, win = autoplot(plotWidgetClass=plotWidgetClass)

    dataThread = QtCore.QThread()
    dataSrc.moveToThread(dataThread)
    dataSrc.dataready.connect(lambda d: win.setInput(data=d, resetDefaults=False))
    dataSrc.nomoredata.connect(dataThread.quit)
    dataThread.started.connect(dataSrc.gimmesomedata)
    win.windowClosed.connect(dataThread.quit)

    dataThread.start()

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtWidgets.QApplication.instance().exec_()


# plotWidgetClass = MPLAutoPlot
plotWidgetClass = PGAutoPlot
# plotWidgetClass = None

if __name__ == '__main__':
    # src = LineDataMovie(20, 3, 31)
    # src = ImageDataMovie(10, 2, 101)
    src = ImageDataLiveAcquisition(101, 101, 67)
    # src = ComplexImage(21, 21)
    src.delay = 0.5
    main(src)
