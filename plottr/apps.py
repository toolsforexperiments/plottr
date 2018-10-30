"""
apps.py

A collection of pre-compiled analysis and plot tools based on plottr.
"""

import logging
from typing import Union

from pyqtgraph.flowchart import Flowchart
from pyqtgraph.Qt import QtGui, QtCore
from pyqtgraph.flowchart import library as fclib
from pyqtgraph.dockarea import Dock, DockArea

from .data.datadict import togrid, DataDictBase, DataDict, GridDataDict
from . import log as plottrlog
from .node.data_selector import DataSelector
from .node.dim_reducer import XYAxesSelector
from .plot.mpl import PlotNode, AutoPlot

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'

# TODO:
# * separate logging window

def autoplot(makeUI: bool=True, log: bool=False, loglevel: int=logging.INFO,
             inputData: Union[None, DataDictBase]=None):
    """
    Sets up a simple flowchart consisting of a data selector,
    an xy-axes selector, and creates a GUI together with an autoplot
    widget.

    returns the flowchart object and the dialog widget
    """

    nodelib = fclib.NodeLibrary()
    nodelib.addNodeType(DataSelector, [('Basic')])
    nodelib.addNodeType(XYAxesSelector, [('Basic')])
    nodelib.addNodeType(PlotNode, [('Plot')])

    fc = Flowchart(terminals={
        'dataIn': {'io': 'in'},
        'dataOut': {'io': 'out'}
    })
    fc.library = nodelib

    datasel = fc.createNode('DataSelector')
    xysel = fc.createNode('XYAxesSelector')
    plot = fc.createNode('Plot')

    fc.connectTerminals(fc['dataIn'], datasel['dataIn'])
    fc.connectTerminals(datasel['dataOut'], xysel['dataIn'])
    fc.connectTerminals(xysel['dataOut'], fc['dataOut'])
    fc.connectTerminals(xysel['dataOut'], plot['dataIn'])

    # Create the plot widget
    plotWidget = AutoPlot()
    plot.setPlotWidget(plotWidget)

    # Setting up the GUI window -- use a dialog here.
    win = QtGui.QDialog()
    area = DockArea()
    layout = QtGui.QVBoxLayout()
    layout.addWidget(area)
    win.setLayout(layout)

    # data selector
    dataselDock = Dock('Data Selector')
    dataselDock.addWidget(datasel.ui)
    area.addDock(dataselDock)

    # xy selector
    xyselDock = Dock('XY Axes Selector')
    xyselDock.addWidget(xysel.ui)
    area.addDock(xyselDock, 'bottom', dataselDock)

    # logger
    if log:
        logDock = Dock('Log')
        logDock.addWidget(plottrlog.setupLogging(makeDialog=False))
        area.addDock(logDock, 'bottom', xyselDock)

    # plot
    plotDock = Dock('Plot')
    plotDock.addWidget(plotWidget)
    area.addDock(plotDock, 'right')

    # show the whole thing
    win.show()

    if inputData is not None:
        fc.setInput(dataIn=inputData)

    return fc, win
