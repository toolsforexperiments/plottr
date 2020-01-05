"""
autoplot.py

Autoplotting app using plottr nodes.
"""

import os
import logging
import time
from typing import Union, Tuple, Any

from .. import QtGui, QtCore, Flowchart
from ..data.datadict import DataDictBase
from ..data.datadict_storage import DDH5Loader
from ..data.qcodes_dataset import QCodesDSLoader
from .. import log as plottrlog
from ..node.tools import linearFlowchart
from ..node.data_selector import DataSelector
from ..node.grid import DataGridder, GridOption
from ..node.dim_reducer import XYSelector
from ..node.filter.correct_offset import SubtractAverage
from ..plot.mpl import PlotNode, AutoPlot
from ..gui.widgets import MonitorIntervalInput, PlotWindow, SnapshotWidget
from ..gui.tools import flowchartAutoPlot



__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'

# TODO: * separate logging window

def logger():
    logger = logging.getLogger('plottr.apps.autoplot')
    logger.setLevel(plottrlog.LEVEL)
    return logger


def autoplot(log: bool = False,
             inputData: Union[None, DataDictBase] = None):
    """
    Sets up a simple flowchart consisting of a data selector,
    an xy-axes selector, and creates a GUI together with an autoplot
    widget.

    returns the flowchart object and the dialog widget
    """

    nodes = [
        ('Data selection', DataSelector),
        ('Grid', DataGridder),
        ('Dimension assignment', XYSelector),
        ('Subtract average', SubtractAverage),
    ]

    win, fc = flowchartAutoPlot(nodes)
    win.show()

    if inputData is not None:
        fc.setInput(dataIn=inputData)

    return fc, win


class AutoPlotMainWindow(PlotWindow):

    def __init__(self, fc: Flowchart,
                 parent: Union[QtGui.QWidget, None] = None,
                 monitorInterval: Union[int, None] = None,
                 loaderName: str = 'Data loader'):

        super().__init__(parent)

        self.fc = fc
        self.loaderNode = fc.nodes()[loaderName]
        self.monitor = QtCore.QTimer()

        # a flag we use to set reasonable defaults when the first data
        # is processed
        self._initialized = False

        windowTitle = "Plottr | Autoplot"
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

        # add UI elements
        if self.fc is not None:
            self.addNodeWidgetsFromFlowchart(fc)

        
        # start monitor
        if monitorInterval is not None:
            self.setMonitorInterval(monitorInterval)

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
        self.status.showMessage(f"loaded: {tstamp}")


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
        drs = dict()
        if len(axes) >= 2:
            drs = {axes[-1]: 'x-axis', axes[-2]: 'y-axis'}
        if len(axes) == 1:
            drs = {axes[0]: 'x-axis'}

        self.fc.nodes()['Data selection'].selectedData = selected
        self.fc.nodes()['Grid'].grid = GridOption.guessShape, {}
        self.fc.nodes()['Dimension assignment'].dimensionRoles = drs
        self.plotWidget.plot.draw()


class QCAutoPlotMainWindow(AutoPlotMainWindow):
    """
    Main Window for autoplotting a qcodes dataset.

    Comes with menu options for refreshing the loaded dataset,
    and a toolbar for enabling live-monitoring/refreshing the loaded
    dataset.
    """

    def __init__(self, fc: Flowchart,
                 parent: Union[QtGui.QWidget, None] = None,
                 monitorInterval: Union[int, None] = None,
                 pathAndId: Union[Tuple[str, int], None] = None):

        super().__init__(fc, parent, monitorInterval)

        windowTitle = "Plottr | QCoDeS autoplot"
        if pathAndId is not None:
            path = os.path.abspath(pathAndId[0])
            windowTitle += f" | {os.path.split(path)[1]} [{pathAndId[1]}]"
            pathAndId = path, pathAndId[1]
        self.setWindowTitle(windowTitle)

        if pathAndId is not None:
            self.loaderNode.pathAndId = pathAndId
        
        #add qcodes specific snapshot widget
        d = QtGui.QDockWidget('snapshot', self)
        self.snapshotWidget = SnapshotWidget()
        d.setWidget(self.snapshotWidget)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, d)
        
        if self.loaderNode.nLoadedRecords > 0:
            self.setDefaults()
            #also setup the snapshot here since the loader node is now initialized 
            logger().debug('loaded snapshot')
            self.snapshotWidget.loadSnapshot(self.loaderNode.dataSnapshot)
            self._initialized = True


def autoplotQcodesDataset(log: bool = False,
                          pathAndId: Union[Tuple[str, int], None] = None) \
        -> (Flowchart, QCAutoPlotMainWindow):
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

    win = QCAutoPlotMainWindow(fc, pathAndId=pathAndId)
    win.show()

    return fc, win


def autoplotDDH5(filepath: str = '', groupname: str = 'data') \
        -> (Flowchart, AutoPlotMainWindow):
    fc = linearFlowchart(
        ('Data loader', DDH5Loader),
        ('Data selection', DataSelector),
        ('Grid', DataGridder),
        ('Dimension assignment', XYSelector),
        ('Subtract average', SubtractAverage),
        ('plot', PlotNode)
    )

    win = AutoPlotMainWindow(fc)
    win.show()

    fc.nodes()['Data loader'].filepath = filepath
    fc.nodes()['Data loader'].groupname = groupname
    if fc.nodes()['Data loader'].nLoadedRecords > 0:
        win.setDefaults()

    win.setMonitorInterval(2)

    return fc, win


