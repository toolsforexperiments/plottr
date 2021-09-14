"""
``plottr.plot.mpl.widgets`` -- This module contains general matplotlib plotting tools.
"""

import io
from typing import Tuple, Optional, List, Dict

from numpy import rint
from matplotlib import rcParams
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FCanvas,
    NavigationToolbar2QT as NavBar,
)

from plottr import QtWidgets, QtGui, QtCore, config as plottrconfig
from plottr.data.datadict import DataDictBase
from plottr.gui.tools import widgetDialog, dpiScalingFactor
from ..base import PlotWidget, PlotWidgetContainer


class MPLPlot(FCanvas):
    """
    This is the basic matplotlib canvas widget we are using for matplotlib
    plots. This canvas only provides a few convenience tools for automatic
    sizing, but is otherwise not very different from the class ``FCanvas``
    that comes with matplotlib (and which we inherit).
    It can be used as any QT widget.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None,
                 width: float = 4.0, height: float = 3.0, dpi: int = 150,
                 constrainedLayout: bool = True):
        """
        Create the canvas.

        :param parent: the parent widget
        :param width: canvas width (inches)
        :param height: canvas height (inches)
        :param dpi: figure dpi
        :param constrainedLayout:
        """

        self.fig = Figure(figsize=(width, height), dpi=dpi,
                          constrained_layout=constrainedLayout)
        super().__init__(self.fig)

        self.axes: List[Axes] = []
        self._tightLayout = False
        self._showInfo = False
        self._infoArtist = None
        self._info = ''
        self._meta_info: Dict[str, str] = {}
        self._constrainedLayout = constrainedLayout

        self.clearFig()
        self.setParent(parent)
        self.setRcParams()

    def autosize(self) -> None:
        """Sets some default spacings/margins."""
        if not self._constrainedLayout:
            self.fig.subplots_adjust(left=0.125, bottom=0.125,
                                     top=0.9, right=0.875,
                                     wspace=0.35, hspace=0.2)
        self.draw()

    def clearFig(self) -> None:
        """clear and reset the canvas."""
        self.fig.clear()
        self.autosize()

    def setRcParams(self) -> None:
        """apply matplotlibrc config from plottr configuration files."""
        cfg = plottrconfig().get('main', {}).get('matplotlibrc', {})
        for k, v in cfg.items():
            rcParams[k] = v
        rcParams['font.size'] = cfg.get('font.size', 6) * dpiScalingFactor(self)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        """
        Re-implementation of the widget resizeEvent method.
        Makes sure we resize the plots appropriately.
        """
        self.autosize()
        super().resizeEvent(event)

    def setShowInfo(self, show: bool) -> None:
        """Whether to show additional info in the plot"""
        self._showInfo = show
        self.updateInfo()

    def updateInfo(self) -> None:
        if self._infoArtist is not None:
            self._infoArtist.remove()
            self._infoArtist = None

        if self._showInfo:
            self._infoArtist = self.fig.text(
                0.02, 0.9, self._info,
                fontsize='small',
                verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.67, lw=1, ec='k')
            )
        self.draw()

    def toClipboard(self) -> None:
        """
        Copy the current canvas to the clipboard.
        """
        buf = io.BytesIO()
        self.fig.savefig(buf, dpi=300, facecolor='w', format='png',
                         transparent=True)

        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setImage(QtGui.QImage.fromData(buf.getvalue()))
        buf.close()

    def metaToClipboard(self) -> None:
        clipboard = QtWidgets.QApplication.clipboard()
        meta_info_string = "\n".join(f"{k}: {v}"
                                     for k, v in self._meta_info.items())
        clipboard.setText(meta_info_string)

    def setFigureTitle(self, title: str) -> None:
        """Add a title to the figure."""
        self.fig.suptitle(title,
                          horizontalalignment='center',
                          verticalalignment='top',
                          fontsize='small')
        self.draw()

    def setFigureInfo(self, info: str) -> None:
        """Display an info string in the figure"""
        self._info = info
        self.updateInfo()

    def setMetaInfo(self, meta_info: Dict[str, str]) -> None:
        self._meta_info = meta_info


class MPLPlotWidget(PlotWidget):
    """
    Base class for matplotlib-based plot widgets.
    Per default, add a canvas and the matplotlib NavBar.
    """

    def __init__(self, parent: Optional[PlotWidgetContainer] = None):
        super().__init__(parent=parent)

        #: the plot widget
        self.plot = MPLPlot()

        #: the matplotlib toolbar
        self.mplBar = NavBar(self.plot, self)

        self.addMplBarOptions()
        defaultIconSize = int(16 * dpiScalingFactor(self))
        self.mplBar.setIconSize(QtCore.QSize(defaultIconSize, defaultIconSize))
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.plot)
        layout.addWidget(self.mplBar)
        self.setLayout(layout)

    def setMeta(self, data: DataDictBase) -> None:
        """Add meta info contained in the data to the figure.

        :param data: data object containing the meta information
            if meta field ``title`` or ``info`` are in the data object, then
            they will be added as text info to the figure.
        """
        if data.has_meta('title'):
            self.plot.setFigureTitle(data.meta_val('title'))

        if data.has_meta('info'):
            self.plot.setFigureInfo(data.meta_val('info'))

        all_meta = {}
        for k, v in sorted(data.meta_items()):
            this_meta = str(v)
            if len(this_meta) > 200:
                this_meta = this_meta[:200] + "..."
            all_meta[k] = this_meta
        self.plot.setMetaInfo(all_meta)

    def addMplBarOptions(self) -> None:
        """Add options for displaying ``info`` meta data and copying the figure to the clipboard to the
        plot toolbar."""
        self.mplBar.addSeparator()
        infoAction = self.mplBar.addAction('Show Info')
        infoAction.setCheckable(True)
        infoAction.toggled.connect(self.plot.setShowInfo)

        self.mplBar.addSeparator()
        self.mplBar.addAction('Copy Figure', self.plot.toClipboard)
        self.mplBar.addAction('Copy Meta', self.plot.metaToClipboard)


def figureDialog() -> Tuple[Figure, QtWidgets.QDialog]:
    """Make a dialog window containing a :class:`.MPLPlotWidget`.

    :return: The figure object of the plot, and the dialog window object.
    """
    widget = MPLPlotWidget()
    return widget.plot.fig, widgetDialog(widget)

