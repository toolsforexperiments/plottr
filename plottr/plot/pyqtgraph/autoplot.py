"""``plottr.plot.pyqtgraph.autoplot`` -- tools for automatic plotting with pyqtgraph.
"""

import logging
from typing import Dict, List, Tuple, Union, Optional, Any, Type

import numpy as np

from pyqtgraph import GraphicsLayoutWidget, mkPen, mkBrush, HistogramLUTItem, ImageItem

from plottr import QtWidgets, QtCore, QtGui, config_entry as getcfg
from ..base import AutoFigureMaker as BaseFM, PlotDataType, \
    PlotItem, ComplexRepresentation, determinePlotDataType, \
    PlotWidgetContainer
from .plots import Plot, PlotWithColorbar

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class FigureMaker(BaseFM):
    """pyqtgraph implementation for :class:`.AutoFigureMaker`.
    """

    # TODO: need to figure out how to reuse widgets when we just update data
    # TODO: make scrollable when many figures (set min size)?
    # TODO: check for valid plot data?

    def __init__(self, parentWidget: Optional[QtWidgets.QWidget] = None):
        super().__init__()
        self.widget = QtWidgets.QWidget(parentWidget)

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.widget.setLayout(self.layout)
        self.widget.setMinimumSize(400, 400)

    # re-implementing to get correct type annotation.
    def __enter__(self) -> "FigureMaker":
        return self

    def makeSubPlots(self, nSubPlots: int) -> List[Any]:

        plotWidgets = []  # FIXME: needs correct type
        for i in range(nSubPlots):
            if max(self.dataDimensionsInSubPlot(i).values()) == 1:
                plot = Plot(self.widget)
                self.layout.addWidget(plot)
                plotWidgets.append([plot])

            elif max(self.dataDimensionsInSubPlot(i).values()) == 2:
                plot = PlotWithColorbar(self.widget)
                self.layout.addWidget(plot)
                plotWidgets.append([plot])

        return plotWidgets

    def formatSubPlot(self, subPlotId: int) -> Any:
        if len(self.plotIdsInSubPlot(subPlotId)) == 0:
            return

        labels = self.subPlotLabels(subPlotId)
        plotwidgets = self.subPlots[subPlotId].axes

        assert isinstance(plotwidgets, list) and len(plotwidgets) > 0
        pw = plotwidgets[0]

        # label the x axis if there's only one x label
        if isinstance(pw, Plot):
            if len(set(labels[0])) == 1:
                pw.plot.setLabel("bottom", labels[0][0])

        if isinstance(pw, PlotWithColorbar):
            if len(set(labels[0])) == 1:
                pw.plot.setLabel("bottom", labels[0][0])

            if len(set(labels[1])) == 1:
                pw.plot.setLabel('left', labels[1][0])

            if len(set(labels[2])) == 1:
                pw.colorbar.setLabel('left', labels[2][0])

    def plot(self, plotItem: PlotItem) -> None:
        if plotItem.plotDataType is PlotDataType.unknown:
            if len(plotItem.data) == 2:
                plotItem.plotDataType = PlotDataType.scatter1d
            elif len(plotItem.data) == 3:
                plotItem.plotDataType = PlotDataType.scatter2d

        if plotItem.plotDataType in [PlotDataType.scatter1d, PlotDataType.line1d]:
            self._1dPlot(plotItem)
        elif plotItem.plotDataType == PlotDataType.grid2d:
            self._colorPlot(plotItem)
        elif plotItem.plotDataType == PlotDataType.scatter2d:
            self._scatterPlot2d(plotItem)
        else:
            raise NotImplementedError('Cannot plot this data.')

    def _1dPlot(self, plotItem):
        colors = getcfg('main', 'pyqtgraph', 'line_colors', default=['r', 'b', 'g'])
        symbols = getcfg('main', 'pyqtgraph', 'line_symbols', default=['o'])
        symbolSize = getcfg('main', 'pyqtgraph', 'line_symbol_size', default=5)

        plotwidgets = self.subPlots[plotItem.subPlot].axes
        assert isinstance(plotwidgets, list) and len(plotwidgets) > 0
        pw = plotwidgets[0]

        assert len(plotItem.data) == 2
        x, y = plotItem.data

        color = colors[self.findPlotIndexInSubPlot(plotItem.id) % len(colors)]
        symbol = symbols[self.findPlotIndexInSubPlot(plotItem.id) % len(symbols)]

        if plotItem.plotDataType == PlotDataType.line1d:
            return pw.plot.plot(x.flatten(), y.flatten(), name=plotItem.labels[-1],
                                pen=mkPen(color, width=2),
                                symbol=symbol, symbolBrush=color, symbolPen=None, symbolSize=symbolSize)
        else:
            return pw.plot.plot(x.flatten(), y.flatten(), name=plotItem.labels[-1],
                                pen=None,
                                symbol=symbol, symbolBrush=color, symbolPen=None, symbolSize=symbolSize)

    def _colorPlot(self, plotItem):
        plotwidgets = self.subPlots[plotItem.subPlot].axes
        assert isinstance(plotwidgets, list) and len(plotwidgets) > 0
        pw = plotwidgets[0]

        assert isinstance(pw, PlotWithColorbar) and len(plotItem.data) == 3
        pw.setImage(*plotItem.data)

    def _scatterPlot2d(self, plotItem):
        plotwidgets = self.subPlots[plotItem.subPlot].axes
        assert isinstance(plotwidgets, list) and len(plotwidgets) > 0
        pw = plotwidgets[0]

        assert isinstance(pw, PlotWithColorbar) and len(plotItem.data) == 3
        pw.setScatter2d(*plotItem.data)

