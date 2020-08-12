"""
plottr/apps/autoplot.py : tools for simple automatic plotting.
"""

import logging
import os
import time
import argparse
from typing import Union, Tuple, Optional, Type, List

from .. import QtCore, Flowchart, Signal, Slot, QtWidgets
from .. import log as plottrlog
from ..data.datadict import DataDictBase
from ..data.datadict_storage import DDH5Loader
from ..data.qcodes_dataset import QCodesDSLoader
from ..gui import PlotWindow
from ..gui.widgets import MonitorIntervalInput, SnapshotWidget
from ..node.data_selector import DataSelector
from ..node.dim_reducer import XYSelector
from ..node.filter.correct_offset import SubtractAverage
from ..node.grid import DataGridder, GridOption
from ..node.tools import linearFlowchart
from ..node.node import Node
from ..plot import PlotNode, makeFlowchartWithPlot
from ..utils.misc import unwrap_optional

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


# TODO: * separate logging window


def logger():
    logger = logging.getLogger('plottr.apps.autoplot')
    logger.setLevel(plottrlog.LEVEL)
    return logger


def autoplot(inputData: Union[None, DataDictBase] = None) \
        -> Tuple[Flowchart, 'AutoPlotMainWindow']:
    """
    Sets up a simple flowchart consisting of a data selector, gridder,
    an xy-axes selector, and creates a GUI together with an autoplot
    widget.

    :returns: the flowchart object and the dialog widget
    """

    nodes: List[Tuple[str, Type[Node]]] = [
        ('Data selection', DataSelector),
        ('Grid', DataGridder),
        ('Dimension assignment', XYSelector),
    ]

    widgetOptions = {
        "Data selection": dict(visible=True,
                               dockArea=QtCore.Qt.TopDockWidgetArea),
        "Dimension assignment": dict(visible=True,
                                     dockArea=QtCore.Qt.TopDockWidgetArea),
    }

    fc = makeFlowchartWithPlot(nodes)
    win = AutoPlotMainWindow(fc, widgetOptions=widgetOptions)
    win.show()

    if inputData is not None:
        win.setInput(data=inputData)

    return fc, win


class UpdateToolBar(QtWidgets.QToolBar):
    """
    A very simple toolbar to enable monitoring or triggering based on a timer.
    Contains a timer whose interval can be set.
    The toolbar will then emit a signal each interval.
    """

    #: Signal emitted after each trigger interval
    trigger = Signal()

    def __init__(self, name, parent=None):
        super().__init__(name, parent)

        self.monitorInput = MonitorIntervalInput()
        self.monitorInput.setToolTip('Set to 0 for disabling triggering')
        self.monitorInput.intervalChanged.connect(self.setMonitorInterval)
        self.addWidget(self.monitorInput)

        self.monitor = QtCore.QTimer()
        self.monitor.timeout.connect(self.monitorTriggered)

    Slot()
    def monitorTriggered(self):
        """
        Is called whenever the monitor timer triggers, and emit the
        :attr:`trigger` Signal.
        """
        logger().debug('Emit trigger')
        self.trigger.emit()

    Slot(int)
    def setMonitorInterval(self, val: int):
        """
        Start a background timer that is triggered every `val' seconds.

        :param val: trigger interval in seconds
        """
        self.monitor.stop()
        if val > 0:
            self.monitor.start(val * 1000)

        self.monitorInput.spin.setValue(val)

    Slot()
    def stop(self):
        """
        Stop the timer.
        """
        self.monitor.stop()


class AutoPlotMainWindow(PlotWindow):

    #: Signal() -- emitted when the window is closed
    windowClosed = Signal()

    def __init__(self, fc: Flowchart,
                 parent: Union[QtWidgets.QWidget, None] = None,
                 monitor: bool = False,
                 monitorInterval: Union[int, None] = None,
                 loaderName: str = None,
                 **kwargs):

        super().__init__(parent, fc=fc, **kwargs)

        self.fc = fc
        if loaderName is not None:
            self.loaderNode = fc.nodes()[loaderName]
        else:
            self.loaderNode = None

        # a flag we use to set reasonable defaults when the first data
        # is processed
        self._initialized = False

        windowTitle = "Plottr | Autoplot"
        self.setWindowTitle(windowTitle)

        # status bar
        self.status = QtWidgets.QStatusBar()
        self.setStatusBar(self.status)

        # menu bar
        self.menu = self.menuBar()
        self.fileMenu = self.menu.addMenu('&Data')

        if self.loaderNode is not None:
            refreshAction = QtWidgets.QAction('&Refresh', self)
            refreshAction.setShortcut('R')
            refreshAction.triggered.connect(self.refreshData)
            self.fileMenu.addAction(refreshAction)

        # add monitor if needed
        if monitor:
            self.monitorToolBar: Optional[UpdateToolBar] = UpdateToolBar('Monitor data')
            self.addToolBar(self.monitorToolBar)
            self.monitorToolBar.trigger.connect(self.refreshData)
            if monitorInterval is not None:
                self.setMonitorInterval(monitorInterval)
        else:
            self.monitorToolBar = None

    def setMonitorInterval(self, val):
        if self.monitorToolBar is not None:
            self.monitorToolBar.setMonitorInterval(val)

    def closeEvent(self, event):
        """
        When closing the inspectr window, do some house keeping:
        * stop the monitor, if running
        """
        if self.monitorToolBar is not None:
            self.monitorToolBar.stop()
        self.windowClosed.emit()
        return event.accept()

    def showTime(self):
        """
        Displays current time and DS info in the status bar.
        """
        tstamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.status.showMessage(f"loaded: {tstamp}")

    Slot()
    def refreshData(self):
        """
        Refresh the dataset by calling `update' on the dataset loader node.
        """
        if self.loaderNode is not None:

            self.loaderNode.update()
            self.showTime()

            if not self._initialized and self.loaderNode.nLoadedRecords > 0:
                self.setDefaults(self.loaderNode.outputValues()['dataOut'])
                self._initialized = True

    def setInput(self, data: DataDictBase, resetDefaults=True):
        """
        Set input to the flowchart. Can only be used when no loader node is
        defined.
        """
        if self.loaderNode is not None:
            logger().warning("A loader node is defined. Use that for inserting data.")
        else:
            self.fc.setInput(dataIn=data)
            if resetDefaults or not self._initialized:
                self.setDefaults(data)
                self._initialized = True

    def setDefaults(self, data: DataDictBase):
        """
        try to set some reasonable defaults so there's a plot right away.
        """
        selected = data.dependents()
        if len(selected) > 0:
            selected = selected[:1]

        axes = data.axes(selected)
        drs = dict()
        if len(axes) >= 2:
            drs = {axes[-1]: 'x-axis', axes[-2]: 'y-axis'}
        if len(axes) == 1:
            drs = {axes[0]: 'x-axis'}

        self.fc.nodes()['Data selection'].selectedData = selected
        self.fc.nodes()['Grid'].grid = GridOption.guessShape, {}
        self.fc.nodes()['Dimension assignment'].dimensionRoles = drs
        unwrap_optional(self.plotWidget).plot.draw()


class QCAutoPlotMainWindow(AutoPlotMainWindow):
    """
    Main Window for autoplotting a qcodes dataset.

    Comes with menu options for refreshing the loaded dataset,
    and a toolbar for enabling live-monitoring/refreshing the loaded
    dataset.
    """

    def __init__(self, fc: Flowchart,
                 parent: Union[QtWidgets.QWidget, None] = None,
                 pathAndId: Union[Tuple[str, int], None] = None, **kw):

        super().__init__(fc, parent, **kw)

        windowTitle = "Plottr | QCoDeS autoplot"
        if pathAndId is not None:
            path = os.path.abspath(pathAndId[0])
            windowTitle += f" | {os.path.split(path)[1]} [{pathAndId[1]}]"
            pathAndId = path, pathAndId[1]
        self.setWindowTitle(windowTitle)

        if pathAndId is not None:
            self.loaderNode.pathAndId = pathAndId

        if self.loaderNode.nLoadedRecords > 0:
            self.setDefaults(self.loaderNode.outputValues()['dataOut'])
            self._initialized = True


def autoplotQcodesDataset(log: bool = False,
                          pathAndId: Union[Tuple[str, int], None] = None) \
        -> Tuple[Flowchart, QCAutoPlotMainWindow]:
    """
    Sets up a simple flowchart consisting of a data selector,
    an xy-axes selector, and creates a GUI together with an autoplot
    widget.

    returns the flowchart object and the mainwindow widget
    """

    fc = linearFlowchart(
        ('Data loader', QCodesDSLoader),
        ('Data selection', DataSelector),
        ('Grid', DataGridder),
        ('Dimension assignment', XYSelector),
        ('Subtract average', SubtractAverage),
        ('plot', PlotNode)
    )

    widgetOptions = {
        "Data selection": dict(visible=True,
                               dockArea=QtCore.Qt.TopDockWidgetArea),
        "Dimension assignment": dict(visible=True,
                                     dockArea=QtCore.Qt.TopDockWidgetArea),
    }

    win = QCAutoPlotMainWindow(fc, pathAndId=pathAndId,
                               widgetOptions=widgetOptions,
                               monitor=True,
                               loaderName='Data loader')
    win.show()

    return fc, win


def autoplotDDH5(filepath: str = '', groupname: str = 'data') \
        -> Tuple[Flowchart, AutoPlotMainWindow]:

    fc = linearFlowchart(
        ('Data loader', DDH5Loader),
        ('Data selection', DataSelector),
        ('Grid', DataGridder),
        ('Dimension assignment', XYSelector),
        # ('Subtract average', SubtractAverage),
        ('plot', PlotNode)
    )

    win = AutoPlotMainWindow(fc, loaderName='Data loader', monitor=True,
                             monitorInterval=2)
    win.show()

    fc.nodes()['Data loader'].filepath = filepath
    fc.nodes()['Data loader'].groupname = groupname
    win.refreshData()
    win.setMonitorInterval(2)

    return fc, win


def main(f, g):
    app = QtWidgets.QApplication([])
    fc, win = autoplotDDH5(f, g)

    return app.exec_()


def script():
    parser = argparse.ArgumentParser(
        description='plottr autoplot .dd.h5 files.'
    )
    parser.add_argument('--filepath', help='path to .dd.h5 file',
                        default='')
    parser.add_argument('--groupname', help='group in the hdf5 file',
                        default='data')
    args = parser.parse_args()

    main(args.filepath, args.groupname)
