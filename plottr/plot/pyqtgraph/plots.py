from typing import Any, Optional, List, Tuple

import numpy as np
import pyqtgraph as pg

from plottr import QtCore, QtWidgets
from . import *


__all__ = ['PlotBase', 'Plot']


class PlotBase(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.setLayout(self.layout)

        self.graphicsLayout = pg.GraphicsLayoutWidget(self)
        self.layout.addWidget(self.graphicsLayout)

    def clearPlot(self):
        return


class Plot(PlotBase):

    plot: pg.PlotItem

    def __init__(self, parent=None):
        super().__init__(parent)
        self.plot: pg.PlotItem = self.graphicsLayout.addPlot()
        self.plot.addLegend(offset=(5, 5), pen='#999', brush=(255, 255, 255, 150))

    def clearPlot(self):
        self.plot.clear()


class PlotWithColorbar(PlotBase):

    plot: pg.PlotItem
    colorbar: pg.ColorBarItem

    def __init__(self, parent=None):
        super().__init__(parent)

        self.plot: pg.PlotItem = self.graphicsLayout.addPlot()

        cmap = pg.colormap.get('viridis', source='matplotlib')
        self.colorbar: pg.ColorBarItem = pg.ColorBarItem(interactive=True, values=(0, 1),
                                                         cmap=cmap, width=15)
        self.graphicsLayout.addItem(self.colorbar)

        self.img: Optional[pg.ImageItem] = None
        self.scatter: Optional[pg.ScatterPlotItem] = None
        self.scatterZVals: Optional[np.ndarray] = None

    def clearPlot(self):
        self.img = None
        self.scatter = None
        self.scatterZVals = None
        self.plot.clear()
        try:
            self.colorbar.sigLevelsChanged.disconnect(self._colorScatterPoints)
        except TypeError:
            pass

    def setImage(self, x: np.ndarray, y: np.ndarray, z: np.ndarray):
        self.clearPlot()

        self.img = pg.ImageItem()
        self.plot.addItem(self.img)
        self.img.setImage(z)
        self.img.setRect(QtCore.QRectF(x.min(), y.min(), x.max()-x.min(), y.max()-y.min()))

        self.colorbar.setImageItem(self.img)
        self.colorbar.rounding = (z.max()-z.min()) * 1e-2
        self.colorbar.setLevels((z.min(), z.max()))

    def setScatter2d(self, x: np.ndarray, y: np.ndarray, z: np.ndarray):
        self.clearPlot()

        self.scatter = pg.ScatterPlotItem()
        self.scatter.setData(x=x.flatten(), y=y.flatten(), symbol='o', size=8)
        self.plot.addItem(self.scatter)
        self.scatterZVals = z

        self.colorbar.setLevels((z.min(), z.max()))
        self.colorbar.rounding = (z.max() - z.min()) * 1e-2
        self._colorScatterPoints(self.colorbar)

        self.colorbar.sigLevelsChanged.connect(self._colorScatterPoints)

    def _colorScatterPoints(self, cbar: pg.ColorBarItem):
        if self.scatter is not None and self.scatterZVals is not None:
            z_norm = self._normalizeColors(self.scatterZVals, cbar.levels())
            colors = self.colorbar.cmap.mapToQColor(z_norm)
            self.scatter.setBrush(colors)

    def _normalizeColors(self, z: np.ndarray, levels: Tuple[float, float]):
        scale = levels[1] - levels[0]
        if scale > 0:
            return (z - levels[0]) / scale
        else:
            return np.ones(z.size()) * 0.5
