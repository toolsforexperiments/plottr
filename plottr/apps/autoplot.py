"""
autoplot.py

Autoplotting app using plottr nodes.
"""

import logging
from typing import Union

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

from .tools import make_sequential_flowchart_with_gui

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'

# TODO: * separate logging window

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

    def __init__(self, fc, parent=None):
        super().__init__(parent)

        self.fc = fc

        # # toolbar
        # self.toolbar = self.addToolBar('Options')

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

    @QtCore.pyqtSlot()
    def refreshData(self):
        self.fc.nodes()['QCodesDSLoader.0'].update()


def autoplotQcodesDataset(makeUI: bool = True, log: bool = False):
    """
    Sets up a simple flowchart consisting of a data selector,
    an xy-axes selector, and creates a GUI together with an autoplot
    widget.

    returns the flowchart object and the dialog widget
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

    area = DockArea()
    win = QCAutoPlotMainWindow(fc=fc)
    win.setCentralWidget(area)

    ### Docks

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

    return fc, win
