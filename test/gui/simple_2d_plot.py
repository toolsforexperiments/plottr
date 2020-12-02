import logging
import time

from plottr import QtWidgets
from plottr import log
from plottr.data.datadict import DataDict, datadict_to_meshgrid
from plottr.utils import testdata
from plottr.gui import PlotWindow
from plottr.plot.mpl import AutoPlot


def setup_logging():
    logger = log.getLogger()
    log.enableStreamHandler(True)
    log.LEVEL = logging.INFO
    return logger


logger = setup_logging()


def simple_2d_plot():
    app = QtWidgets.QApplication([])
    win = PlotWindow()
    plot = AutoPlot(parent=win)
    win.plot.setPlotWidget(plot)
    win.show()

    # plotting 1d traces
    if False:
        logger.info(f"1D trace")
        t0 = time.perf_counter()
        nsamples = 30
        for i in range(nsamples):
            data = datadict_to_meshgrid(
                testdata.get_1d_scalar_cos_data(201, 2)
            )
            win.plot.setData(data)
        t1 = time.perf_counter()
        fps = nsamples/(t1-t0)
        logger.info(f"Performance: {fps} FPS")

    # plotting images
    if True:
        logger.info(f"2D image")
        t0 = time.perf_counter()
        nsamples = 30
        for i in range(nsamples):
            data = datadict_to_meshgrid(
                testdata.get_2d_scalar_cos_data(201, 101, 1)
            )
            win.plot.setData(data)
        t1 = time.perf_counter()
        fps = nsamples/(t1-t0)
        logger.info(f"Performance: {fps} FPS")

    # plotting 2d scatter
    if False:
        logger.info(f"2D scatter")
        t0 = time.perf_counter()
        nsamples = 30
        for i in range(nsamples):
            data = testdata.get_2d_scalar_cos_data(21, 21, 1)
            win.plot.setData(data)
        t1 = time.perf_counter()
        fps = nsamples/(t1-t0)
        logger.info(f"Performance: {fps} FPS")

    return app.exec_()


if __name__ == '__main__':
    from plottr import plottrPath
    print(plottrPath)
    simple_2d_plot()
