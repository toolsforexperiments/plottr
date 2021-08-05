"""``plottr.plot.pyqtgraph.autoplot`` -- tools for automatic plotting with pyqtgraph.
"""

import logging
from typing import Dict, List, Tuple, Union, Optional, Any, Type

import numpy as np

from pyqtgraph import GraphicsLayoutWidget, mkPen, mkBrush, HistogramLUTItem, ImageItem

from plottr import QtWidgets, QtCore, QtGui, config_entry as getcfg
from plottr.data.datadict import DataDictBase
from ..base import AutoFigureMaker as BaseFM, PlotDataType, \
    PlotItem, ComplexRepresentation, determinePlotDataType, \
    PlotWidgetContainer, PlotWidget
from .plots import Plot, PlotWithColorbar, PlotBase

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class _FigureMakerWidget(QtWidgets.QWidget):

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent=parent)

        self.subPlots: List[PlotBase] = []

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.setLayout(self.layout)
        self.setMinimumSize(*getcfg('main', 'pyqtgraph', 'minimum_plot_size',
                                    default=(400, 400)))

    def addPlot(self, plot: PlotBase):
        self.layout.addWidget(plot)
        self.subPlots.append(plot)

    def clearAllPlots(self):
        for p in self.subPlots:
            p.clearPlot()

    def deleteAllPlots(self):
        for p in self.subPlots:
            p.deleteLater()
        self.subPlots = []


class FigureMaker(BaseFM):
    """pyqtgraph implementation for :class:`.AutoFigureMaker`.
    """

    # TODO: make scrollable when many figures (set min size)?
    # TODO: check for valid plot data

    def __init__(self, widget: Optional[_FigureMakerWidget] = None,
                 clearWidget: bool = True,
                 parentWidget: Optional[QtWidgets.QWidget] = None):
        super().__init__()

        self.clearWidget: bool = clearWidget
        if widget is None:
            self.widget = _FigureMakerWidget(parent=parentWidget)
        else:
            self.widget = widget

    # re-implementing to get correct type annotation.
    def __enter__(self) -> "FigureMaker":
        return self

    def subPlotFromId(self, subPlotId):
        subPlots = self.subPlots[subPlotId].axes
        assert isinstance(subPlots, list) and len(subPlots) > 0 and \
               isinstance(subPlots[0], PlotBase)
        return subPlots[0]

    def makeSubPlots(self, nSubPlots: int) -> List[List[PlotBase]]:
        if self.clearWidget:
            self.widget.deleteAllPlots()

            for i in range(nSubPlots):
                if max(self.dataDimensionsInSubPlot(i).values()) == 1:
                    plot = Plot(self.widget)
                    self.widget.addPlot(plot)
                elif max(self.dataDimensionsInSubPlot(i).values()) == 2:
                    plot = PlotWithColorbar(self.widget)
                    self.widget.addPlot(plot)

        else:
            self.widget.clearAllPlots()

        return self.widget.subPlots

    def formatSubPlot(self, subPlotId: int) -> Any:
        if len(self.plotIdsInSubPlot(subPlotId)) == 0:
            return

        labels = self.subPlotLabels(subPlotId)
        subPlot = self.subPlotFromId(subPlotId)

        # label the x axis if there's only one x label
        if isinstance(subPlot, Plot):
            if len(set(labels[0])) == 1:
                subPlot.plot.setLabel("bottom", labels[0][0])

        if isinstance(subPlot, PlotWithColorbar):
            if len(set(labels[0])) == 1:
                subPlot.plot.setLabel("bottom", labels[0][0])

            if len(set(labels[1])) == 1:
                subPlot.plot.setLabel('left', labels[1][0])

            if len(set(labels[2])) == 1:
                subPlot.colorbar.setLabel('left', labels[2][0])

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

        subPlot = self.subPlotFromId(plotItem.subPlot)

        assert len(plotItem.data) == 2
        x, y = plotItem.data

        color = colors[self.findPlotIndexInSubPlot(plotItem.id) % len(colors)]
        symbol = symbols[self.findPlotIndexInSubPlot(plotItem.id) % len(symbols)]

        if plotItem.plotDataType == PlotDataType.line1d:
            return subPlot.plot.plot(x.flatten(), y.flatten(), name=plotItem.labels[-1],
                                    pen=mkPen(color, width=2),
                                    symbol=symbol, symbolBrush=color, symbolPen=None, symbolSize=symbolSize)
        else:
            return subPlot.plot.plot(x.flatten(), y.flatten(), name=plotItem.labels[-1],
                                    pen=None,
                                    symbol=symbol, symbolBrush=color, symbolPen=None, symbolSize=symbolSize)

    def _colorPlot(self, plotItem):
        subPlot = self.subPlotFromId(plotItem.subPlot)
        assert isinstance(subPlot, PlotWithColorbar) and len(plotItem.data) == 3
        subPlot.setImage(*plotItem.data)

    def _scatterPlot2d(self, plotItem):
        subPlot = self.subPlotFromId(plotItem.subPlot)
        assert isinstance(subPlot, PlotWithColorbar) and len(plotItem.data) == 3
        subPlot.setScatter2d(*plotItem.data)


class AutoPlot(PlotWidget):
    """Widget for automatic plotting with pyqtgraph."""

    def __init__(self, parent: Optional[PlotWidgetContainer]):
        """Constructor for the pyqtgraph auto plot widget.

        :param parent:
        """
        super().__init__(parent=parent)

        self.fmWidget: Optional[PlotWidget] = None
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.setLayout(self.layout)
        self.setMinimumSize(*getcfg('main', 'pyqtgraph', 'minimum_plot_size', default=(400, 400)))

    def setData(self, data: Optional[DataDictBase]) -> None:
        super().setData(data)
        if self.data is None:
            return

        fmKwargs = {'widget': self.fmWidget}
        dc = self.dataChanges
        if not dc['dataTypeChanged'] and not dc['dataStructureChanged'] \
                and not dc['dataShapesChanged']:
            fmKwargs['clearWidget'] = False
        else:
            fmKwargs['clearWidget'] = True

        with FigureMaker(parentWidget=self, **fmKwargs) as fm:
            inds = self.data.axes()
            for dep in self.data.dependents():
                dvals = self.data.data_vals(dep)
                plotId = fm.addData(
                    *[np.asanyarray(self.data.data_vals(n)) for n in inds] + [dvals]
                )

        if self.fmWidget is None:
            self.fmWidget = fm.widget
            self.layout.addWidget(self.fmWidget)
