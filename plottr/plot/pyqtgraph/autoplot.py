"""``plottr.plot.pyqtgraph.autoplot`` -- tools for automatic plotting with pyqtgraph.
"""

import logging
from typing import Dict, List, Tuple, Union, Optional, Any, Type

import numpy as np

from pyqtgraph import GraphicsLayoutWidget, GraphicsItem

from plottr import QtWidgets, QtCore, QtGui
from ..base import AutoFigureMaker as BaseFM, PlotDataType, \
    PlotItem, ComplexRepresentation, determinePlotDataType, \
    PlotWidgetContainer

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class FigureMaker(BaseFM):
    """pyqtgraph implementation for :class:`.AutoFigureMaker`.

    """
    # TODO: need to figure out how to reuse widgets when we just update data

    def __init__(self, parentWidget: Optional[QtWidgets.QWidget] = None):

        super().__init__()
        self.parentWidget = parentWidget
        self.layoutWidget = None

    # re-implementing to get correct type annotation.
    def __enter__(self) -> "FigureMaker":
        return self

    def makeSubPlots(self, nSubPlots: int) -> List[Any]:
        # this is for the case of having only 1d plots
        self.layoutWidget = GraphicsLayoutWidget(parent=self.parentWidget)
        plotItems = []
        for i in range(nSubPlots):
            plotItems.append(self.layoutWidget.addPlot())
        return plotItems

    def formatSubPlot(self, subPlotId: int) -> Any:
        pass

    def plot(self, plotItem: PlotItem) -> None:
        plots = self.subPlots[plotItem.subPlot].axes
        assert isinstance(plots, list) and len(plots) == 1
        assert len(plotItem.data) == 2
        x, y = plotItem.data
        return plots[0].plot(x, y)









