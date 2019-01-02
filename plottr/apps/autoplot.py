"""
autoplot.py

Autoplotting app using plottr nodes.
"""

import os
import logging
import time
from typing import Union, Tuple

from pyqtgraph.flowchart import Flowchart
from pyqtgraph.Qt import QtGui, QtCore
from pyqtgraph.flowchart import library as fclib
from pyqtgraph.dockarea import Dock, DockArea

from ..data.datadict import DataDictBase, DataDict, MeshgridDataDict
from ..data.qcodes_dataset import QCodesDSLoader
from .. import log as plottrlog
from ..node.data_selector import DataSelector
from ..node.grid import DataGridder
from ..node.dim_reducer import XYAxesSelector
from ..plot.mpl import PlotNode, AutoPlot
from ..widgets import MonitorIntervalInput

from .tools import make_sequential_flowchart_with_gui

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'

# TODO: * separate logging window

def logger():
    logger = logging.getLogger('plottr.apps.autoplot')
    logger.setLevel(plottrlog.LEVEL)
    return logger

def autoplot(makeUI: bool = True, log: bool = False,
             inputData: Union[None, DataDictBase] = None):
    """
    Sets up a simple flowchart consisting of a data selector,
    an xy-axes selector, and creates a GUI together with an autoplot
    widget.

    returns the flowchart object and the dialog widget
    """

    nodelib = fclib.NodeLibrary()
    nodelib.addNodeType(DataSelector, [('Basic')])
    nodelib.addNodeType(DataGridder, [('Basic')])
    nodelib.addNodeType(XYAxesSelector, [('Basic')])
    nodelib.addNodeType(PlotNode, [('Plot')])

    fc = Flowchart(terminals={
        'dataIn': {'io': 'in'},
        'dataOut': {'io': 'out'}
    })
    fc.library = nodelib

    datasel = fc.createNode('DataSelector')
    grid = fc.createNode('Gridder')
    xysel = fc.createNode('XYAxesSelector')
    plot = fc.createNode('Plot')

    fc.connectTerminals(fc['dataIn'], datasel['dataIn'])
    fc.connectTerminals(datasel['dataOut'], grid['dataIn'])
    fc.connectTerminals(grid['dataOut'], xysel['dataIn'])
    fc.connectTerminals(xysel['dataOut'], fc['dataOut'])
    fc.connectTerminals(xysel['dataOut'], plot['dataIn'])

    # Setting up the GUI window
    area = DockArea()
    layout = QtGui.QVBoxLayout()
    layout.addWidget(area)
    win = QtGui.QDialog()
    win.setLayout(layout)
    win.setWindowTitle('Plottr | Autoplot')

    # data selector
    dataselDock = Dock('Data Selector', size=(250, 100))
    dataselDock.addWidget(datasel.ui)
    area.addDock(dataselDock)

    # grid
    gridDock = Dock('Grid', size=(250, 80))
    gridDock.addWidget(grid.ui)
    area.addDock(gridDock, 'bottom')

    # xy selector
    xyselDock = Dock('XY Axes Selector', size=(250, 100))
    xyselDock.addWidget(xysel.ui)
    area.addDock(xyselDock, 'bottom')

    # log
    if log:
        logDock = Dock('Log', size=(250, 100))
        logDock.addWidget(plottrlog.setupLogging(makeDialog=False))
        area.addDock(logDock, 'bottom', xyselDock)

    # plot widget
    plotWidget = AutoPlot()
    plot.setPlotWidget(plotWidget)
    plotDock = Dock('Plot', size=(500, 300))
    plotDock.addWidget(plotWidget)
    area.addDock(plotDock, 'right')

    win.show()

    if inputData is not None:
        fc.setInput(dataIn=inputData)

    return fc, win



class QCAutoPlotMainWindow(QtGui.QMainWindow):
    """
    Main Window for autoplotting a qcodes dataset.

    Comes with menu options for refreshing the loaded dataset,
    and a toolbar for enabling live-monitoring/refreshing the loaded
    dataset.
    """

    def __init__(self, fc: Flowchart, parent: Union[QtGui.QWidget, None] = None,
                 pathAndId: Union[Tuple[str, int], None] = None,
                 monitorInterval: Union[int, None] = None):

        super().__init__(parent)

        self.fc = fc
        self.loaderNode = fc.nodes()['QCodesDSLoader.0']
        self.monitor = QtCore.QTimer()

        # a flag we use to set reasonable defaults when the first data
        # is processed
        self._initialized = False

        windowTitle = "Plottr | QCoDeS autoplot"
        if pathAndId is not None:
            path = os.path.abspath(pathAndId[0])
            windowTitle += f" | {os.path.split(path)[1]} [{pathAndId[1]}]"
            pathAndId = path, pathAndId[1]

        self.setWindowTitle(windowTitle)

        # toolbar
        self.toolbar = self.addToolBar('Data monitoring')

        # toolbar item: monitor interval
        self.monitorInput = MonitorIntervalInput()
        self.monitorInput.setToolTip('Set to 0 for disabling monitoring')
        self.monitorInput.intervalChanged.connect(self.setMonitorInterval)
        self.toolbar.addWidget(self.monitorInput)

        # status bar
        self.status = QtGui.QStatusBar()
        self.setStatusBar(self.status)

        # menu bar
        menu = self.menuBar()
        fileMenu = menu.addMenu('&Data')

        # action: updates from the db file
        refreshAction = QtGui.QAction('&Refresh', self)
        refreshAction.setShortcut('R')
        refreshAction.triggered.connect(self.refreshData)
        fileMenu.addAction(refreshAction)

        # more signals/slots
        self.monitor.timeout.connect(self.monitorTriggered)

        if pathAndId is not None:
            self.loaderNode.pathAndId = pathAndId
            if monitorInterval is not None:
                self.setMonitorInterval(monitorInterval)

            if self.loaderNode.nLoadedRecords > 0:
                self.setDefaults()
                self._initialized = True

    def closeEvent(self, event):
        """
        When closing the inspectr window, do some house keeping:
        * stop the monitor, if running
        """
        if self.monitor.isActive():
            self.monitor.stop()

    def showTime(self):
        """
        Displays current time and DS info in the status bar.
        """
        tstamp = time.strftime("%Y-%m-%d %H:%M:%S")
        path, runId = self.fc.nodes()['QCodesDSLoader.0'].pathAndId
        self.status.showMessage(f"{path} [{runId}] (loaded: {tstamp})")


    @QtCore.pyqtSlot()
    def refreshData(self):
        """
        Refresh the dataset by calling `update' on the dataset loader node.
        """
        self.loaderNode.update()
        self.showTime()

        if not self._initialized and self.loaderNode.nLoadedRecords > 0:
            self.setDefaults()
            self._initialized = True


    @QtCore.pyqtSlot(int)
    def setMonitorInterval(self, val):
        """
        Start a background timer that is triggered every `val' seconds.
        """
        self.monitor.stop()
        if val > 0:
            self.monitor.start(val * 1000)

        self.monitorInput.spin.setValue(val)


    @QtCore.pyqtSlot()
    def monitorTriggered(self):
        """
        Is called whenever the monitor timer triggers, and calls for a refresh
        of the current dataset.
        """
        logger().debug('Refreshing data')
        self.refreshData()


    def setDefaults(self):
        """
        set some defaults (for convenience).
        """
        data = self.loaderNode.outputValues()['dataOut']
        selected = data.dependents()
        if len(selected) > 0:
            selected = selected[:1]

        axes = data.axes(selected)
        if len(axes) > 2:
            axes = axes[-2:]
        if len(axes) == 1:
            axes = axes[0], None

        self.fc.nodes()['DataSelector.0'].selectedData = selected
        self.fc.nodes()['Gridder.0'].grid = 'guess'
        self.fc.nodes()['XYAxesSelector.0'].xyAxes = axes


def autoplotQcodesDataset(makeUI: bool = True, log: bool = False,
                          pathAndId: Union[Tuple[str, int], None] = None) -> (Flowchart, QCAutoPlotMainWindow):
    """
    Sets up a simple flowchart consisting of a data selector,
    an xy-axes selector, and creates a GUI together with an autoplot
    widget.

    returns the flowchart object and the mainwindow widget
    """

    nodelib = fclib.NodeLibrary()
    nodelib.addNodeType(QCodesDSLoader, [('Input')])
    nodelib.addNodeType(DataSelector, [('Basic')])
    nodelib.addNodeType(DataGridder, [('Basic')])
    nodelib.addNodeType(XYAxesSelector, [('Basic')])
    nodelib.addNodeType(PlotNode, [('Plot')])

    fc = Flowchart(terminals={
        'dataIn': {'io': 'in'},
        'dataOut': {'io': 'out'}
    })
    fc.library = nodelib

    loader = fc.createNode('QCodesDSLoader')
    datasel = fc.createNode('DataSelector')
    grid = fc.createNode('Gridder')
    xysel = fc.createNode('XYAxesSelector')
    plot = fc.createNode('Plot')

    fc.connectTerminals(fc['dataIn'], loader['dataIn'])
    fc.connectTerminals(loader['dataOut'], datasel['dataIn'])
    fc.connectTerminals(datasel['dataOut'], grid['dataIn'])
    fc.connectTerminals(grid['dataOut'], xysel['dataIn'])
    fc.connectTerminals(xysel['dataOut'], fc['dataOut'])
    fc.connectTerminals(xysel['dataOut'], plot['dataIn'])

    ### Setting up the GUI window

    ### Docks
    area = DockArea()

    # data selector
    dataselDock = Dock('Data Selector', size=(250, 100))
    dataselDock.addWidget(datasel.ui)
    area.addDock(dataselDock)

    # grid
    gridDock = Dock('Grid', size=(250, 80))
    gridDock.addWidget(grid.ui)
    area.addDock(gridDock, 'bottom')

    # xy selector
    xyselDock = Dock('XY Axes Selector', size=(250, 100))
    xyselDock.addWidget(xysel.ui)
    area.addDock(xyselDock, 'bottom')

    # log
    if log:
        logDock = Dock('Log', size=(250, 100))
        logDock.addWidget(plottrlog.setupLogging(makeDialog=False))
        area.addDock(logDock, 'bottom', xyselDock)

    # plot widget
    plotWidget = AutoPlot()
    plot.setPlotWidget(plotWidget)
    plotDock = Dock('Plot', size=(500, 300))
    plotDock.addWidget(plotWidget)
    area.addDock(plotDock, 'right')

    win = QCAutoPlotMainWindow(fc=fc, pathAndId=pathAndId)
    win.setCentralWidget(area)
    win.show()

    return fc, win
