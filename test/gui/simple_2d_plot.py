import logging
import time

from plottr import QtGui
from plottr import log
from plottr.data.datadict import DataDict, datadict_to_meshgrid
from plottr.utils import testdata
from plottr.gui.widgets import SinglePlotWindow
from plottr.plot.mpl import MPLPlotWidget


def setup_logging():
    logger = log.getLogger()
    log.enableStreamHandler(True)
    log.LEVEL = logging.INFO
    return logger


logger = setup_logging()


def simple_2d_plot():
    app = QtGui.QApplication([])
    win = SinglePlotWindow()
    plot = MPLPlotWidget(parent=win)
    win.plot.setPlotWidget(plot)
    win.show()

    t0 = time.perf_counter()
    nsamples = 30
    for i in range(nsamples):
        data = datadict_to_meshgrid(testdata.one_2d_set(201, 151))
        win.plot.setData(data)

    t1 = time.perf_counter()
    fps = nsamples/(t1-t0)
    logger.info(f"Performance: {fps} FPS")

    return app.exec_()


if __name__ == '__main__':
    simple_2d_plot()