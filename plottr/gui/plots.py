"""
plots.py

Contains the included plot nodes/widgets.
"""

from ..node import NodeWidget

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'

class MPLPlotWidget(NodeWidget):
    """
    Simple base class for a node that's a plot widget based on
    matplotlib. `processData` simply calls `updatePlot`.
    Reimplementation requires that `self.plot` is available and of type
    `plottr.gui.mpl.MPLPlot`.
    """

    def processData(self):
        self.updatePlot()
        return None

    def updatePlot(self):
        self.plot.clearFig()