"""
plottr/plot/mpl.py : Tools for plotting with matplotlib.
"""

import logging
import io
from enum import Enum, unique, auto
from typing import Dict, List
from collections import OrderedDict

# standard scientific computing imports
import numpy as np
from matplotlib.image import AxesImage
from matplotlib import rcParams, cm
from matplotlib.axes import Axes
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FCanvas,
    NavigationToolbar2QT as NavBar,
)
from matplotlib.figure import Figure
from mpl_toolkits.axes_grid1 import make_axes_locatable

from .base import PlotWidget
from .. import QtGui, QtCore, Signal, Slot
from ..utils import num
from ..utils.num import interp_meshgrid_2d, centers2edges_2d
from ..data.datadict import DataDictBase, DataDict, MeshgridDataDict

from plottr.icons import (singleTracePlotIcon, multiTracePlotIcon, imagePlotIcon,
                          colormeshPlotIcon, scatterPlot2dIcon)


__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@unique
class PlotDataType(Enum):
    """Types of (plotable) data"""

    #: unplottable data
    unknown = auto()

    #: scatter-type data with 1 dependent (data is not on a grid)
    scatter1d = auto()

    #: line data with 1 dependent (data is on a grid)
    line1d = auto()

    #: scatter data with 2 dependents (data is not on a grid)
    scatter2d = auto()

    #: grid data with 2 dependents
    grid2d = auto()

@unique
class PlotType(Enum):
    """Plot types"""

    #: no plot defined
    empty = auto()

    #: a single 1D line/scatter plot per panel
    singletraces = auto()

    #: multiple 1D lines/scatter plots per panel
    multitraces = auto()

    #: image plot of 2D data
    image = auto()

    #: colormesh plot of 2D data
    colormesh = auto()

    #: 2D scatter plot
    scatter2d = auto()


def determinePlotDataType(data: DataDictBase) -> PlotDataType:
    """
    Analyze input data and determine most likely :class:`PlotDataType`.

    Analysis is simply based on number of dependents and data type.

    :param data: data to analyze.
    """
    # TODO:
    #   there's probably ways to be more liberal about what can be plotted.
    #   like i can always make a 1d scatter...

    # a few things will result in unplottable data:
    # * wrong data format
    if not isinstance(data, DataDictBase):
        return PlotDataType.unknown

    # * incompatible independents
    if not data.axes_are_compatible():
        return PlotDataType.unknown

    # * too few or too many independents
    if len(data.axes()) < 1 or len(data.axes()) > 2:
        return PlotDataType.unknown

    # * no data to plot
    if len(data.dependents()) == 0:
        return PlotDataType.unknown

    if isinstance(data, MeshgridDataDict):
        shape = data.shapes()[data.dependents()[0]]

        if len(data.axes()) == 2:
            return PlotDataType.grid2d
        else:
            return PlotDataType.line1d

    elif isinstance(data, DataDict):
        if len(data.axes()) == 2:
            return PlotDataType.scatter2d
        else:
            return PlotDataType.scatter1d

    return PlotDataType.unknown


def setMplDefaults():
    """Set some reasonable matplotlib defaults for appearance."""

    rcParams['figure.dpi'] = 300
    rcParams['figure.figsize'] = (4.5, 3)
    rcParams['savefig.dpi'] = 300
    rcParams['axes.grid'] = True
    rcParams['grid.linewidth'] = 0.5
    rcParams['grid.linestyle'] = ':'
    rcParams['font.family'] = 'Arial', 'Helvetica', 'DejaVu Sans'
    rcParams['font.size'] = 6
    rcParams['lines.markersize'] = 4
    rcParams['lines.linestyle'] = '-'
    rcParams['savefig.transparent'] = False
    rcParams['figure.subplot.bottom'] = 0.15
    rcParams['figure.subplot.top'] = 0.85
    rcParams['figure.subplot.left'] = 0.15
    rcParams['figure.subplot.right'] = 0.9


def ppcolormesh_from_meshgrid(ax: Axes, x: np.ndarray, y: np.ndarray,
                              z: np.ndarray, **kw) -> AxesImage:
    r"""Plot a pcolormesh with some reasonable defaults.
    Input are the corresponding arrays from a 2D ``MeshgridDataDict``.

    Will attempt to fix missing points in the coordinates.

    :param ax: axes to plot the colormesh into.
    :param x: x component of the meshgrid coordinates
    :param y: y component of the meshgrid coordinates
    :param z: data values

    :keyword arguments:
        * *cmap* (matplotlib colormap) --
          colormap to use. Default is ``viridis``.
    """
    cmap = kw.get('cmap', cm.viridis)

    x = x.astype(float)
    y = y.astype(float)
    z = z.astype(float)

    # first check if we need to fill some masked values in
    if np.ma.is_masked(x):
        x = x.filled(np.nan)
    if np.ma.is_masked(y):
        y = y.filled(np.nan)
    if np.ma.is_masked(z):
        z = z.filled(np.nan)

    # next: try some surgery, if possible
    if np.all(num.is_invalid(x)) or np.all(num.is_invalid(y)):
        return
    if np.any(np.isnan(x)) or np.any(np.isnan(y)):
        x, y = interp_meshgrid_2d(x, y)
    if np.any(num.is_invalid(x)) or np.any(num.is_invalid(y)):
        x, y, z = num.crop2d(x, y, z)

    # next, check if the resulting grids are even still plotable
    for g in x, y, z:
        if g.size == 0:
            return
        elif len(g.shape) < 2:
            return

        # special case: if we have a single line, a pcolor-type plot won't work.
        elif min(g.shape) < 2:
            im = ax.scatter(x, y, c=z)
            return im

    # and finally: the meshgrid we have describes coordinates, but for plotting
    # with pcolormesh we need vertices.
    try:
        x = centers2edges_2d(x)
        y = centers2edges_2d(y)
    except:
        return

    im = ax.pcolormesh(x, y, z, cmap=cmap, **kw)
    ax.set_xlim(x.min(), x.max())
    ax.set_ylim(y.min(), y.max())
    return im


class MPLPlot(FCanvas):
    """
    This is the basic matplotlib canvas widget we are using for matplotlib
    plots. This canvas only provides a few convenience tools for automatic
    sizing and creating subfigures, but is otherwise not very different
    from the class ``FCanvas`` that comes with matplotlib (and which we inherit).
    It can be used as any QT widget.
    """

    def __init__(self, parent: QtGui.QWidget = None, width: float = 4.0,
                 height: float = 3.0, dpi: int = 150, nrows: int = 1,
                 ncols: int = 1):
        """
        Create the canvas.

        :param parent: the parent widget
        :param width: canvas width (inches)
        :param height: canvas height (inches)
        :param dpi: figure dpi
        :param nrows: number of subplot rows
        :param ncols: number of subplot columns
        """

        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)

        self.axes = []
        self._tightLayout = False
        self._showInfo = False
        self._infoArtist = None
        self._info = ''

        self.clearFig(nrows, ncols)
        self.setParent(parent)

    def autosize(self):
        """
        Sets some default spacings/margins.
        :return:
        """
        if not self._tightLayout:
            self.fig.subplots_adjust(left=0.125, bottom=0.125, top=0.9,
                                     right=0.875,
                                     wspace=0.35, hspace=0.2)
        else:
            self.fig.tight_layout(rect=[0, 0.03, 1, 0.95])

        self.draw()

    def clearFig(self, nrows: int = 1, ncols: int = 1,
                 naxes: int = 1) -> List[Axes]:
        """
        Clear and reset the canvas.

        :param nrows: number of subplot/axes rows to prepare
        :param ncols: number of subplot/axes column to prepare
        :param naxes: number of axes in total
        :returns: the created axes in the grid
        """
        self.fig.clear()
        setMplDefaults()

        self.axes = []
        iax = 1
        if naxes > nrows * ncols:
            raise ValueError(
                f'Number of axes ({naxes}) larger than rows ({nrows}) x '
                f'columns ({ncols}).')

        for i in range(1, naxes + 1):
            kw = {}
            if iax > 1:
                kw['sharex'] = self.axes[0]
                kw['sharey'] = self.axes[0]

            self.axes.append(self.fig.add_subplot(nrows, ncols, i))
            iax += 1

        self.autosize()
        return self.axes

    def resizeEvent(self, event):
        """
        Re-implementation of the widget resizeEvent method.
        Makes sure we resize the plots appropriately.
        """
        self.autosize()
        super().resizeEvent(event)

    def setTightLayout(self, tight: bool):
        """
        Set tight layout mode.
        :param tight: if true, use tight layout for autosizing.
        """
        self._tightLayout = tight
        self.autosize()

    def setShowInfo(self, show: bool):
        """Whether to show additional info in the plot"""
        self._showInfo = show
        self.updateInfo()

    def updateInfo(self):
        if self._infoArtist is not None:
            self._infoArtist.remove()
            self._infoArtist = None

        if self._showInfo:
            self._infoArtist = self.fig.text(
                0, 0, self._info,
                fontsize='x-small',
                verticalalignment='bottom',
            )
        self.draw()

    def toClipboard(self):
        """
        Copy the current canvas to the clipboard.
        """
        buf = io.BytesIO()
        self.fig.savefig(buf, dpi=300, facecolor='w', format='png',
                         transparent=True)
        QtGui.QApplication.clipboard().setImage(
            QtGui.QImage.fromData(buf.getvalue()))
        buf.close()

    def setFigureTitle(self, title: str):
        """Add a title to the figure."""
        self.fig.text(0.5, 0.99, title,
                      horizontalalignment='center',
                      verticalalignment='top',
                      fontsize='small')
        self.draw()

    def setFigureInfo(self, info: str):
        """Display an info string in the figure"""
        self._info = info
        self.updateInfo()


# class MPLPlotContainer(QtGui.QWidget):
#     """
#     A widget that contains multiple MPL plots (each with their own tools).
#
#     TODO: implement. this would allow very flexible apps i think.
#         But might be worth exploring if that shouldn't mean also attaching
#         reducers to each plot. in that case this would be rather complex.
#         Need to think a bit if that's worth it.
#     """
#     pass


class _MPLPlotWidget(PlotWidget):
    """
    Base class for matplotlib-based plot widgets.
    Per default, add a canvas and the matplotlib NavBar.
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        setMplDefaults()

        self.plot = MPLPlot()
        self.mplBar = NavBar(self.plot, self)
        self.addMplBarOptions()
        self.mplBar.setIconSize(QtCore.QSize(16,16))

        self.layout = QtGui.QVBoxLayout(self)
        self.layout.addWidget(self.plot)
        self.layout.addWidget(self.mplBar)

    def setMeta(self, data: DataDictBase):
        if data.has_meta('title'):
            self.plot.setFigureTitle(data.meta_val('title'))

        if data.has_meta('info'):
            self.plot.setFigureInfo(data.meta_val('info'))

    def addMplBarOptions(self):
        tlCheck = QtGui.QCheckBox('Tight layout')
        tlCheck.toggled.connect(self.plot.setTightLayout)

        infoCheck = QtGui.QCheckBox('Info')
        infoCheck.toggled.connect(self.plot.setShowInfo)

        self.mplBar.addSeparator()
        self.mplBar.addWidget(tlCheck)
        self.mplBar.addSeparator()
        self.mplBar.addWidget(infoCheck)
        self.mplBar.addSeparator()
        self.mplBar.addAction('Copy', self.plot.toClipboard)


# A toolbar for setting options on the MPL autoplot
class _AutoPlotToolBar(QtGui.QToolBar):
    """
    A toolbar that allows the user to configure AutoPlot.

    Currently, the user can select between the plots that are possible, given
    the data that AutoPlot has
    """

    #: signal emitted when the plot type has been changed
    plotTypeSelected = Signal(PlotType)

    def __init__(self, name: str, parent: QtGui.QWidget = None):
        """Constructor for :class:`AutoPlotToolBar`"""

        super().__init__(name, parent=parent)

        self.plotasMultiTraces = self.addAction(multiTracePlotIcon,
                                                'Multiple traces')
        self.plotasMultiTraces.setCheckable(True)
        self.plotasMultiTraces.triggered.connect(
            lambda: self.selectPlotType(PlotType.multitraces))

        self.plotasSingleTraces = self.addAction(singleTracePlotIcon,
                                                 'Individual traces')
        self.plotasSingleTraces.setCheckable(True)
        self.plotasSingleTraces.triggered.connect(
            lambda: self.selectPlotType(PlotType.singletraces))

        self.addSeparator()

        self.plotasImage = self.addAction(imagePlotIcon,
                                          'Image')
        self.plotasImage.setCheckable(True)
        self.plotasImage.triggered.connect(
            lambda: self.selectPlotType(PlotType.image))

        self.plotasMesh = self.addAction(colormeshPlotIcon,
                                         'Color mesh')
        self.plotasMesh.setCheckable(True)
        self.plotasMesh.triggered.connect(
            lambda: self.selectPlotType(PlotType.colormesh))

        self.plotasScatter2d = self.addAction(scatterPlot2dIcon,
                                              'Scatter 2D')
        self.plotasScatter2d.setCheckable(True)
        self.plotasScatter2d.triggered.connect(
            lambda: self.selectPlotType(PlotType.scatter2d))

        self.plotTypeActions = OrderedDict({
            PlotType.multitraces: self.plotasMultiTraces,
            PlotType.singletraces: self.plotasSingleTraces,
            PlotType.image: self.plotasImage,
            PlotType.colormesh: self.plotasMesh,
            PlotType.scatter2d: self.plotasScatter2d,
        })

        self._currentPlotType = PlotType.empty
        self._currentlyAllowedPlotTypes = []

    def selectPlotType(self, plotType: PlotType):
        """makes sure that the selected `plotType` is active (checked), all
        others are not active.

        This method should be used to catch a trigger from the UI.

        If the active plot type has been changed by using this method,
        we emit `plotTypeSelected`.
        """

        # deselect all other types
        for k, v in self.plotTypeActions.items():
            if k is not plotType and v is not None:
                v.setChecked(False)

        # don't want un-toggling - can only be done by selecting another type
        self.plotTypeActions[plotType].setChecked(True)

        if plotType is not self._currentPlotType:
            self._currentPlotType = plotType
            self.plotTypeSelected.emit(plotType)

    def setAllowedPlotTypes(self, *args: PlotType):
        """Disable all choices that are not allowed.
        If the current selection is now disabled, instead select the first
        enabled one.
        """

        if args == self._currentlyAllowedPlotTypes:
            return

        for k, v in self.plotTypeActions.items():
            if k not in args:
                v.setChecked(False)
                v.setEnabled(False)
            else:
                v.setEnabled(True)

        if self._currentPlotType not in args:
            self._currentPlotType = PlotType.empty
            for k, v in self.plotTypeActions.items():
                if k in args:
                    v.setChecked(True)
                    self._currentPlotType = k
                    break

            self.plotTypeSelected.emit(self._currentPlotType)

        self._currentlyAllowedPlotTypes = args


class AutoPlot(_MPLPlotWidget):
    """A widget for plotting with matplotlib.

    When data is set using :meth:`setData` the class will automatically try
    to determine what good plot options are from the structure of the data.

    User options (for different types of plots, styling, etc) are
    presented through a toolbar.

    **Plot types:**

    The following types of data allow for different types of plots:

    *1D data* --

    * 1D scatter data (of type ``DataDict``) --
      Plot will be a simple scatter plot.

    * 1D grid data (of type ``MeshgridDataDict``) --
      same, but lines connecting the markers.

    For 1D plots the user has the option of plotting all data in the same panel,
    or each dataset in its own panel.

    *2D data* --

    * 2D scatter data --
      2D scatter plot with color bar.

    * 2D grid data --
      Either display as image, or as pcolormesh, with colorbar.

    For 2D plots, we always create one panel per dataset.
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.plotDataType = PlotDataType.unknown
        self.plotType = PlotType.empty

        self.dataType = type(None)
        self.dataStructure = None
        self.dataShapes = None
        self.dataLimits = None

        # A toolbar for configuring the plot
        self.plotOptionsToolBar = _AutoPlotToolBar('Plot options', self)
        self.layout.insertWidget(1, self.plotOptionsToolBar)
        self.plotOptionsToolBar.plotTypeSelected.connect(
            self._plotTypeFromToolBar)
        self.plotOptionsToolBar.setIconSize(QtCore.QSize(32, 32))

        self.setMinimumSize(640, 480)

    def _analyzeData(self, data: DataDictBase) -> Dict[str, bool]:
        """checks data and compares with previous properties."""
        dataType = type(data)

        if data is None:
            dataStructure = None
            dataShapes = None
            dataLimits = None
        else:
            dataStructure = data.structure(include_meta=False)
            dataShapes = data.shapes()
            dataLimits = {}
            for n in data.axes() + data.dependents():
                vals = data.data_vals(n)
                dataLimits[n] = vals.min(), vals.max()

        result = {
            'dataTypeChanged': dataType != self.dataType,
            'dataStructureChanged': dataStructure != self.dataStructure,
            'dataShapesChanged': dataShapes != self.dataShapes,
            'dataLimitsChanged': dataLimits != self.dataLimits,
        }

        self.dataType = dataType
        self.dataStructure = dataStructure
        self.dataShapes = dataShapes
        self.dataLimits = dataLimits

        return result

    def setData(self, data: DataDictBase):
        """Analyses data and determines whether/what to plot.

        :param data: input data
        """
        super().setData(data)

        changes = self._analyzeData(data)
        self.plotDataType = determinePlotDataType(data)

        self._processPlotTypeOptions()
        self._plotData(adjustSize=True)

    def _processPlotTypeOptions(self):
        """Given the current data type, figure out what the plot options are."""
        if self.plotDataType == PlotDataType.grid2d:
            self.plotOptionsToolBar.setAllowedPlotTypes(
                PlotType.image, PlotType.colormesh, PlotType.scatter2d
            )

        elif self.plotDataType == PlotDataType.scatter2d:
            self.plotOptionsToolBar.setAllowedPlotTypes(
                PlotType.scatter2d,
            )

        elif self.plotDataType in [PlotDataType.scatter1d,
                                   PlotDataType.line1d]:
            self.plotOptionsToolBar.setAllowedPlotTypes(
                PlotType.multitraces, PlotType.singletraces,
            )

        else:
            self.plotOptionsToolBar.setAllowedPlotTypes([])

    @Slot(PlotType)
    def _plotTypeFromToolBar(self, plotType: PlotType):
        if plotType is not self.plotType:
            self.plotType = plotType
            self._plotData(adjustSize=True)

    def _makeAxes(self, nAxes: int) -> Axes:
        """Create a grid of axes.
        We try to keep the grid as square as possible.
        """
        nrows = int(nAxes ** .5 + .5)
        ncols = np.ceil(nAxes / nrows)
        axes = self.plot.clearFig(nrows, ncols, nAxes)
        return axes

    def _plotData(self, adjustSize: bool = False):
        """Plot the data using previously determined data and plot types."""

        if self.plotDataType is PlotDataType.unknown:
            logger.debug("No plotable data.")

        if self.plotType is PlotType.empty:
            logger.debug("No plot routine determined.")
            return

        # only in combined 1D plots we need always only 1 panel.
        # most plots require as many panels as datasets
        if self.plotType is PlotType.multitraces:
            axes = self._makeAxes(1)
        else:
            axes = self._makeAxes(len(self.data.dependents()))

        if self.plotType is PlotType.multitraces:
            logger.debug(f"Plotting lines in a single panel")
            self._plot1d(axes, self.data, style='singlepanel')

        elif self.plotType is PlotType.singletraces:
            logger.debug(f"Plotting one line per panel")
            self._plot1d(axes, self.data, style='separatepanels')

        elif self.plotType is PlotType.image:
            logger.debug(f"Plot 2D data as image.")
            self._plot2d(axes, self.data, style='image')

        elif self.plotType is PlotType.colormesh:
            logger.debug(f"Plot 2D data as colormesh.")
            self._plot2d(axes, self.data, style='mesh')

        elif self.plotType is PlotType.scatter2d:
            logger.debug(f"Plot 2D data as scatter plot.")
            self._plot2d(axes, self.data, style='scatter')

        else:
            logger.info(f"No plot routine defined for {self.plotType}")
            return

        self.setMeta(self.data)
        if adjustSize:
            self.plot.autosize()
        else:
            self.plot.draw()
        QtCore.QCoreApplication.processEvents()

    # Plotting functions
    def _plot1d(self, axes: List[Axes], data: DataDict, style: str):
        """Plot 1D data.

        Expects a list of axes objects and matching data.

        * if style is 'singlepanel':
            will only use the first axes. all datasets will be plotted into that
            axes.
        * if style is 'separatepanels':
            will plot one dependent per panel.
        """
        xname = data.axes()[0]
        x = data.data_vals(xname)
        depnames = data.dependents()
        deps = [data.data_vals(d) for d in depnames]
        hasLabels = False

        for i, d in enumerate(depnames):
            if style == 'singlepanel' and len(depnames) > 1:
                ax = axes[0]
                lbl = data.label(d)
                ylbl = None
                hasLabels = True
            else:
                ax = axes[i]
                lbl = None
                ylbl = data.label(d)

            if self.plotDataType is PlotDataType.scatter1d:
                fmt = 'o'
            else:
                fmt = 'o-'

            ax.plot(x, deps[i], fmt, mfc='None', mew=1, lw=0.5, label=lbl)
            ax.set_xlabel(xname)
            ax.set_ylabel(ylbl)

        if style == 'singlepanel' and hasLabels:
            ax.legend(fontsize='small', loc=1)

    def _plot2d(self, axes: List[Axes], data: DataDict, style: str):
        """Plot 2D data.

        Expects a list of axes objects into which the dependents of the data
        are plotted (one dataset per axes).

        How data is plotted depends on style:
        'image': use `imshow`.
        'mesh': use `pcolormesh`.
        'scatter': make a 2d scatter plot with color as z.

        Logger will show an error if a bad style is given.
        """

        xname = data.axes()[0]
        yname = data.axes()[1]
        x = data.data_vals(xname)
        y = data.data_vals(yname)

        # expect that list of axes matches the dependents.
        for ax, zname in zip(axes, data.dependents()):
            z = data.data_vals(zname)

            if style == 'image':
                ax.grid(False)
                extent = [None, None, None, None]
                x0, x1 = x.min(), x.max()
                y0, y1 = y.min(), y.max()
                extent = [x0, x1, y0, y1]

                if x.shape[0] > 1:
                    # in image mode we have to be a little careful:
                    # if the x/y axes are specified with decreasing values we need to
                    # flip the image. otherwise we'll end up with an axis that has the
                    # opposite ordering from the data.
                    z = z if x[0, 0] < x[1, 0] else z[::-1, :]

                if y.shape[1] > 1:
                    z = z if y[0, 0] < y[0, 1] else z[:, ::-1]

                if x0 == x1:
                    extent[1] = x0+1
                if y0 == y1:
                    extent[3] = y0+1

                im = ax.imshow(z.T, aspect='auto', origin='lower',
                               extent=tuple(extent))

            elif style == 'mesh':
                ax.grid(False)
                im = ppcolormesh_from_meshgrid(ax, x, y, z)

            elif style == 'scatter':
                im = ax.scatter(x, y, c=z)

            else:
                logger.error(f"unknown style '{style}'")

            # this seems to be a reasonable way to get good-looking color bars
            # for all panels.
            div = make_axes_locatable(ax)
            cax = div.append_axes("right", size="5%", pad=0.05)
            cb = self.plot.fig.colorbar(im, cax=cax)

            ax.set_xlabel(data.label(xname))
            ax.set_ylabel(data.label(yname))
            cax.set_ylabel(data.label(zname))
