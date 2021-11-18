"""Convenience tools for generating ``pyqtgraph`` plots that can
be used in plottr's automatic plotting framework."""

from typing import Optional, Tuple, NoReturn

import numpy as np
import pyqtgraph as pg

from plottr import QtCore, QtWidgets

__all__ = ['PlotBase', 'Plot']


class PlotBase(QtWidgets.QWidget):
    """A simple convenience widget class as container for ``pyqtgraph`` plots.

    The widget contains a layout that contains a ``GraphicsLayoutWidget``.
    This is handy because a plot may contain multiple elements (like an image
    and a colorbar).

    This base class should be inherited to use.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        #: central layout of the widget. only contains a graphics layout.
        layout = QtWidgets.QHBoxLayout(self)
        #: ``pyqtgraph`` graphics layout
        self.graphicsLayout = pg.GraphicsLayoutWidget(self)

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)
        layout.addWidget(self.graphicsLayout)

        #: ``pyqtgraph`` plot item
        self.plot: pg.PlotItem = self.graphicsLayout.addPlot()

    def clearPlot(self) -> None:
        """Clear all plot contents (but do not delete plot elements, like axis
        spines, insets, etc).

        To be implemented by inheriting classes."""
        raise NotImplementedError


class Plot(PlotBase):
    """A simple plot with a single ``PlotItem``."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        legend = self.plot.addLegend(offset=(5, 5), pen='#999',
                                     brush=(255, 255, 255, 150))
        legend.layout.setContentsMargins(0, 0, 0, 0)
        self.plot.showGrid(True, True)

    def clearPlot(self) -> None:
        """Clear the plot item."""
        self.plot.clear()


class PlotWithColorbar(PlotBase):
    """Plot containing a plot item and a colorbar item.

    Plot is suited for either an image plot (:meth:`.setImage`) or a color
    scatter plot (:meth:`.setScatter2D`).
    The color scale is displayed in an interactive colorbar.
    """
    #: colorbar
    colorbar: pg.ColorBarItem

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        cmap = pg.colormap.get('viridis', source='matplotlib')
        self.colorbar: pg.ColorBarItem = pg.ColorBarItem(interactive=True, values=(0, 1),
                                                         cmap=cmap, width=15)
        self.graphicsLayout.addItem(self.colorbar)

        self.img: Optional[pg.ImageItem] = None
        self.scatter: Optional[pg.ScatterPlotItem] = None
        self.scatterZVals: Optional[np.ndarray] = None

    def clearPlot(self) -> None:
        """Clear the content of the plot."""
        self.img = None
        self.scatter = None
        self.scatterZVals = None
        self.plot.clear()
        try:
            self.colorbar.sigLevelsChanged.disconnect(self._colorScatterPoints)
        except TypeError:
            pass

    def setImage(self, x: np.ndarray, y: np.ndarray, z: np.ndarray) -> None:
        """Set data to be plotted as image.

        Clears the plot before creating a new image item that gets places in the
        plot and linked to the colorscale.

        :param x: x coordinates (as 2D meshgrid)
        :param y: y coordinates (as 2D meshgrid)
        :param z: data values (as 2D meshgrid)
        :return: None
        """
        self.clearPlot()

        self.img = pg.ImageItem()
        self.plot.addItem(self.img)
        self.img.setImage(z)
        self.img.setRect(QtCore.QRectF(x.min(), y.min(), x.max() - x.min(), y.max() - y.min()))

        self.colorbar.setImageItem(self.img)
        self.colorbar.rounding = (z.max() - z.min()) * 1e-2
        self.colorbar.setLevels((z.min(), z.max()))

    def setScatter2d(self, x: np.ndarray, y: np.ndarray, z: np.ndarray) -> None:
        """Set data to be plotted as image.

        Clears the plot before creating a new scatter item (based on flattened
        input data) that gets placed in the plot and linked to the colorscale.

        :param x: x coordinates
        :param y: y coordinates
        :param z: data values
        :return: None
        """
        self.clearPlot()

        self.scatter = pg.ScatterPlotItem()
        self.scatter.setData(x=x.flatten(), y=y.flatten(), symbol='o', size=8)
        self.plot.addItem(self.scatter)
        self.scatterZVals = z.flatten()

        self.colorbar.setLevels((z.min(), z.max()))
        self.colorbar.rounding = (z.max() - z.min()) * 1e-2
        self._colorScatterPoints(self.colorbar)

        self.colorbar.sigLevelsChanged.connect(self._colorScatterPoints)

    # TODO: this seems crazy slow.
    def _colorScatterPoints(self, cbar: pg.ColorBarItem) -> None:
        if self.scatter is not None and self.scatterZVals is not None:
            z_norm = self._normalizeColors(self.scatterZVals, cbar.levels())
            colors = self.colorbar.cmap.mapToQColor(z_norm)
            self.scatter.setBrush(colors)

    def _normalizeColors(self, z: np.ndarray, levels: Tuple[float, float]) -> np.ndarray:
        scale = levels[1] - levels[0]
        if scale > 0:
            return (z - levels[0]) / scale
        else:
            return np.ones(z.size) * 0.5
