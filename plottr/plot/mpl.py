"""
plottr/plot/mpl.py : Tools for plotting with matplotlib.
"""

import logging
import io
from enum import Enum, unique, auto
from typing import Dict, List, Tuple, Union, cast, Optional
from collections import OrderedDict

# standard scientific computing imports
import numpy as np
from matplotlib.image import AxesImage
from matplotlib import rcParams, cm, colors, pyplot as plt
from matplotlib.axes import Axes
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FCanvas,
    NavigationToolbar2QT as NavBar,
)
from matplotlib.figure import Figure
from mpl_toolkits.axes_grid1 import make_axes_locatable

from .base import PlotWidget
from .. import QtGui, QtCore, Signal, Slot, QtWidgets
from ..utils import num
from ..utils.num import interp_meshgrid_2d, centers2edges_2d
from ..data.datadict import DataDictBase, DataDict, MeshgridDataDict

from plottr.icons import (get_singleTracePlotIcon, get_multiTracePlotIcon, get_imagePlotIcon,
                          get_colormeshPlotIcon, get_scatterPlot2dIcon)


__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


# TODO: might be handy to develop some form of figure manager class,
#   into which we can dump various types of data, and that figures
#   out the general layout/labeling, etc.
#   could be a context manager, where during the enter we just accumulate infos,
#   and do the plotting only at the end.


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# Types of plots and plottable data
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

@unique
class ComplexRepresentation(Enum):
    """Options for plotting complex-valued data."""

    #: only real
    real = auto()

    #: real and imaginary
    realAndImag = auto()

    #: magnitude and phase
    magAndPhase = auto()


def determinePlotDataType(data: Optional[DataDictBase]) -> PlotDataType:
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


# matplotlib tools and settings
default_prop_cycle = rcParams['axes.prop_cycle']
default_cmap = cm.get_cmap('magma')
symmetric_cmap = cm.get_cmap('bwr')


class SymmetricNorm(colors.Normalize):
    """Color norm that's symmetric and linear around a center value."""
    def __init__(self, vmin=None, vmax=None, vcenter=0, clip=False):
        super().__init__(vmin, vmax, clip)
        self.vcenter = vcenter

    def __call__(self, value, clip=None):
        vlim = max(abs(self.vmin-self.vcenter), abs(self.vmax-self.vcenter))
        self.vmax = vlim+self.vcenter
        self.vmin = -vlim+self.vcenter
        return super().__call__(value, clip)


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
    rcParams['lines.markersize'] = 3
    rcParams['lines.linestyle'] = '-'
    rcParams['savefig.transparent'] = False
    rcParams['figure.subplot.bottom'] = 0.15
    rcParams['figure.subplot.top'] = 0.85
    rcParams['figure.subplot.left'] = 0.15
    rcParams['figure.subplot.right'] = 0.9


# 2D plots
def colorplot2d(ax: Axes, x: np.ndarray, y: np.ndarray, z: np.ndarray,
                style: PlotType = PlotType.image,
                axLabels: Tuple[str, str, str] = ('', '', ''),
                **kw):
    """make a 2d colorplot. what plot is made, depends on `style`.
    Any of the 2d plot types in :class:`PlotType` works.

    :param ax: matplotlib axes to plot in
    :param x: x coordinates (meshgrid)
    :param y: y coordinates (meshgrid)
    :param z: z data
    :param style: the plot type
    :axLabels: labels for the x, y axes, and the colorbar.

    all keywords are passed to the actual plotting functions:
    - :attr:`PlotType.image` --
        :func:`plotImage`
    - :attr:`PlotType.colormesh` --
        :func:`ppcolormesh_from_meshgrid`
    - :attr:`PlotType.scatter2d` --
        matplotlib's `scatter`
    """
    cmap = kw.pop('cmap', default_cmap)

    # first we need to check if our grid can be plotted nicely.
    if style in [PlotType.image, PlotType.colormesh]:
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
            return None
        if np.any(np.isnan(x)) or np.any(np.isnan(y)):
            x, y = interp_meshgrid_2d(x, y)
        if np.any(num.is_invalid(x)) or np.any(num.is_invalid(y)):
            x, y, z = num.crop2d(x, y, z)

        # next, check if the resulting grids are even still plottable
        for g in x, y, z:
            if g.size == 0:
                return None
            elif len(g.shape) < 2:
                return None

            # special case: if we have a single line, a pcolor-type plot won't work.
            elif min(g.shape) < 2:
                style = PlotType.scatter2d

    if style is PlotType.image:
        im = plotImage(ax, x, y, z, cmap=cmap, **kw)
    elif style is PlotType.colormesh:
        im = ppcolormesh_from_meshgrid(ax, x, y, z, cmap=cmap, **kw)
    elif style is PlotType.scatter2d:
        im = ax.scatter(x, y, c=z, cmap=cmap, **kw)

    if im is None:
        return

    cax = attachColorBar(ax, im)
    ax.set_xlabel(axLabels[0])
    ax.set_ylabel(axLabels[1])
    cax.set_ylabel(axLabels[2])


def ppcolormesh_from_meshgrid(ax: Axes, x: np.ndarray, y: np.ndarray,
                              z: np.ndarray, **kw) -> Union[AxesImage, None]:
    r"""Plot a pcolormesh with some reasonable defaults.
    Input are the corresponding arrays from a 2D ``MeshgridDataDict``.

    Will attempt to fix missing points in the coordinates.

    :param ax: axes to plot the colormesh into.
    :param x: x component of the meshgrid coordinates
    :param y: y component of the meshgrid coordinates
    :param z: data values
    :returns: the image returned by `pcolormesh`.

    Keywords are passed on to `pcolormesh`.
    """
    # the meshgrid we have describes coordinates, but for plotting
    # with pcolormesh we need vertices.
    try:
        x = centers2edges_2d(x)
        y = centers2edges_2d(y)
    except:
        return None

    im = ax.pcolormesh(x, y, z, **kw)
    ax.set_xlim(x.min(), x.max())
    ax.set_ylim(y.min(), y.max())
    return im


def plotImage(ax: Axes, x: np.ndarray, y: np.ndarray,
              z: np.ndarray, **kw) -> AxesImage:
    """Plot 2d meshgrid data as image.

    :param ax: matplotlib axes to plot the image in.
    :param x: x coordinates (as meshgrid)
    :param y: y coordinates
    :param z: z values
    :returns: the image object returned by `imshow`

    All keywords are passed to `imshow`.
    """
    ax.grid(False)
    x0, x1 = x.min(), x.max()
    y0, y1 = y.min(), y.max()

    extentx = [x0, x1]
    if x0 > x1:
        extentx = extentx[::-1]
    if x0 == x1:
        extentx = [x0, x0+1]
    extenty = [y0, y1]
    if y0 > y1:
        extenty = extenty[::-1]
    if y0 == y1:
        extenty = [y0, y0+1]
    extent = tuple(extentx + extenty)

    if x.shape[0] > 1:
        # in image mode we have to be a little careful:
        # if the x/y axes are specified with decreasing values we need to
        # flip the image. otherwise we'll end up with an axis that has the
        # opposite ordering from the data.
        z = z if x[0, 0] < x[1, 0] else z[::-1, :]

    if y.shape[1] > 1:
        z = z if y[0, 0] < y[0, 1] else z[:, ::-1]

    im = ax.imshow(z.T, aspect='auto', origin='lower',
                   extent=extent, **kw)
    return im


def attachColorBar(ax: Axes, im: AxesImage) -> Axes:
    """Attach a colorbar to the `AxesImage` `im` that was plotted
    into `Axes` `ax`.

    :returns: the newly generated color bar axes.
    """
    div = make_axes_locatable(ax)
    cax = div.append_axes("right", size="5%", pad=0.05)
    cb = plt.colorbar(im, cax=cax)
    return cax


# 1D plot
def plot1dTrace(ax: Axes, x: np.ndarray, y: np.ndarray,
                axLabels: Tuple[Union[None, str], Union[None, str]] = (None, None),
                curveLabel: Union[None, str] = None,
                addLegend: bool = False, **kw) -> None:
    """Plot 1D data.

    :param ax: Axes to plot into
    :param x: x values
    :param y: y values
    :param axLabels: labels to set on x and y axes.
        will not be set if `None`
    :param curveLabel: legend label
    :param addLegend: if True, add a legend to `ax`.

    All keywords are passed to matplotlib's `plot` function.
    """

    if isinstance(x, np.ma.MaskedArray):
        x = x.filled(np.nan)
    if isinstance(y, np.ma.MaskedArray):
        y = y.filled(np.nan)

    plot_kw = dict(lw=1, mew=1, mfc='w')
    plot_kw.update(kw)
    fmt = cast(str, plot_kw.pop('fmt', 'o-'))

    # if we're plotting real and imaginary parts, modify the label
    lbl = None
    lbl_imag = None
    if np.issubsctype(y, np.complexfloating):
        if curveLabel is None:
            lbl = 'Re'
            lbl_imag = 'Im'
        else:
            lbl = f"Re({curveLabel})"
            lbl_imag = f"Im({curveLabel})"
    if lbl is None:
        lbl = curveLabel

    line, = ax.plot(x, y.real, fmt, label=lbl, **plot_kw)
    if np.issubsctype(y, np.complexfloating):
        plot_kw['dashes'] = [2, 2]
        plot_kw['color'] = line.get_color()
        fmt = 's' + fmt[1:]
        ax.plot(x, y.imag, fmt, label=lbl_imag, **plot_kw)

    if axLabels[0] is not None:
        ax.set_xlabel(axLabels[0])
    if axLabels[1] is not None:
        ax.set_ylabel(axLabels[1])
    if addLegend:
        ax.legend(loc=1, fontsize='small')


class MPLPlot(FCanvas):
    """
    This is the basic matplotlib canvas widget we are using for matplotlib
    plots. This canvas only provides a few convenience tools for automatic
    sizing and creating subfigures, but is otherwise not very different
    from the class ``FCanvas`` that comes with matplotlib (and which we inherit).
    It can be used as any QT widget.
    """

    def __init__(self, parent: QtWidgets.QWidget = None, width: float = 4.0,
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

        self.axes: List[Axes] = []
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
        QtWidgets.QApplication.clipboard().setImage(
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

        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.addWidget(self.plot)
        self.layout.addWidget(self.mplBar)

    def setMeta(self, data: DataDictBase):
        if data.has_meta('title'):
            self.plot.setFigureTitle(data.meta_val('title'))

        if data.has_meta('info'):
            self.plot.setFigureInfo(data.meta_val('info'))

    def addMplBarOptions(self):
        tlCheck = QtWidgets.QCheckBox('Tight layout')
        tlCheck.toggled.connect(self.plot.setTightLayout)

        infoCheck = QtWidgets.QCheckBox('Info')
        infoCheck.toggled.connect(self.plot.setShowInfo)

        self.mplBar.addSeparator()
        self.mplBar.addWidget(tlCheck)
        self.mplBar.addSeparator()
        self.mplBar.addWidget(infoCheck)
        self.mplBar.addSeparator()
        self.mplBar.addAction('Copy', self.plot.toClipboard)


# A toolbar for setting options on the MPL autoplot
class _AutoPlotToolBar(QtWidgets.QToolBar):
    """
    A toolbar that allows the user to configure AutoPlot.

    Currently, the user can select between the plots that are possible, given
    the data that AutoPlot has
    """

    #: signal emitted when the plot type has been changed
    plotTypeSelected = Signal(PlotType)

    #: signal emitted when the complex data option has been changed
    complexPolarSelected = Signal(bool)


    def __init__(self, name: str, parent: QtWidgets.QWidget = None):
        """Constructor for :class:`AutoPlotToolBar`"""

        super().__init__(name, parent=parent)

        self.plotasMultiTraces = self.addAction(get_multiTracePlotIcon(),
                                                'Multiple traces')
        self.plotasMultiTraces.setCheckable(True)
        self.plotasMultiTraces.triggered.connect(
            lambda: self.selectPlotType(PlotType.multitraces))

        self.plotasSingleTraces = self.addAction(get_singleTracePlotIcon(),
                                                 'Individual traces')
        self.plotasSingleTraces.setCheckable(True)
        self.plotasSingleTraces.triggered.connect(
            lambda: self.selectPlotType(PlotType.singletraces))

        self.addSeparator()

        self.plotasImage = self.addAction(get_imagePlotIcon(),
                                          'Image')
        self.plotasImage.setCheckable(True)
        self.plotasImage.triggered.connect(
            lambda: self.selectPlotType(PlotType.image))

        self.plotasMesh = self.addAction(get_colormeshPlotIcon(),
                                         'Color mesh')
        self.plotasMesh.setCheckable(True)
        self.plotasMesh.triggered.connect(
            lambda: self.selectPlotType(PlotType.colormesh))

        self.plotasScatter2d = self.addAction(get_scatterPlot2dIcon(),
                                              'Scatter 2D')
        self.plotasScatter2d.setCheckable(True)
        self.plotasScatter2d.triggered.connect(
            lambda: self.selectPlotType(PlotType.scatter2d))

        # other options
        self.addSeparator()

        self.plotComplexPolar = self.addAction('Mag/Phase')
        self.plotComplexPolar.setCheckable(True)
        self.plotComplexPolar.triggered.connect(self.complexPolarSelected)

        self.plotTypeActions = OrderedDict({
            PlotType.multitraces: self.plotasMultiTraces,
            PlotType.singletraces: self.plotasSingleTraces,
            PlotType.image: self.plotasImage,
            PlotType.colormesh: self.plotasMesh,
            PlotType.scatter2d: self.plotasScatter2d,
        })

        self._currentPlotType = PlotType.empty
        self._currentlyAllowedPlotTypes: Tuple[PlotType, ...] = ()

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

    * 1D data (of type ``DataDict``) --
      Plot will be a simple scatter plot with markers, connected by lines.

    For 1D plots the user has the option of plotting all data in the same panel,
    or each dataset in its own panel.

    *2D data* --

    * 2D scatter data --
      2D scatter plot with color bar.

    * 2D grid data --
      Either display as image, or as pcolormesh, with colorbar.

    For 2D plots, we always create one panel per dataset.

    If the input data is complex, the user has the option to plot real/imaginary
    parts, or magnitude and phase. Real/Imaginary are plotted in the same panel,
    whereas magnitude and phase are separated into two panels.
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.plotDataType = PlotDataType.unknown
        self.plotType = PlotType.empty
        self.complexRepresentation = ComplexRepresentation.real
        self.complexPreference = ComplexRepresentation.realAndImag

        self.dataType = type(None)
        self.dataStructure = None
        self.dataShapes = None
        self.dataLimits = None

        # A toolbar for configuring the plot
        self.plotOptionsToolBar = _AutoPlotToolBar('Plot options', self)
        self.layout.insertWidget(1, self.plotOptionsToolBar)

        self.plotOptionsToolBar.plotTypeSelected.connect(
            self._plotTypeFromToolBar
        )
        self.plotOptionsToolBar.complexPolarSelected.connect(
            self._complexPreferenceFromToolBar
        )

        self.plotOptionsToolBar.setIconSize(QtCore.QSize(32, 32))

        self.setMinimumSize(640, 480)

    def _analyzeData(self, data: Optional[DataDictBase]) -> Dict[str, bool]:
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

    def dataIsComplex(self, dependentName=None):
        """Determine whether our data is complex.
        If dependent_name is not given, check all dependents, return True if any
        of them is complex.
        """
        if self.data is None:
            return False

        if dependentName is None:
            for d in self.data.dependents():
                if np.issubsctype(self.data.data_vals(d), np.complexfloating):
                    return True
        else:
            if np.issubsctype(self.data.data_vals(dependentName), np.complexfloating):
                return True

        return False

    def setData(self, data: Optional[DataDictBase]):
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

    @Slot(bool)
    def _complexPreferenceFromToolBar(self, magPhasePreferred):
        if magPhasePreferred:
            self.complexPreference = ComplexRepresentation.magAndPhase
        else:
            self.complexPreference = ComplexRepresentation.realAndImag

        self._plotData(adjustSize=True)

    def _makeAxes(self, nAxes: int) -> List[Axes]:
        """Create a grid of axes.
        We try to keep the grid as square as possible.
        """
        nrows = int(nAxes ** .5 + .5)
        ncols = int(np.ceil(nAxes / nrows))
        axes = self.plot.clearFig(nrows, ncols, nAxes)
        return axes

    def _plotData(self, adjustSize: bool = False):
        """Plot the data using previously determined data and plot types."""

        if self.plotDataType is PlotDataType.unknown:
            logger.debug("No plotable data.")

        if self.plotType is PlotType.empty:
            logger.debug("No plot routine determined.")
            return

        if not self.dataIsComplex():
            self.complexRepresentation = ComplexRepresentation.real
        else:
            self.complexRepresentation = self.complexPreference

        if self.plotType is PlotType.multitraces:
            logger.debug(f"Plotting lines in a single panel")
            self._plot1dSinglepanel()

        elif self.plotType is PlotType.singletraces:
            logger.debug(f"Plotting one line per panel")
            self._plot1dSeparatePanels()

        elif self.plotType in [PlotType.image,
                               PlotType.colormesh,
                               PlotType.scatter2d]:
            logger.debug(f"Plot 2D data.")
            self._colorplot2d()

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
    def _plot1dSinglepanel(self):
        xname = self.data.axes()[0]
        xvals = self.data.data_vals(xname)
        depnames = self.data.dependents()
        depvals = [self.data.data_vals(d) for d in depnames]

        # count the number of panels we need.
        if self.complexRepresentation is ComplexRepresentation.magAndPhase:
            nAxes = 2
        else:
            nAxes = 1
        axes = self._makeAxes(nAxes)

        if len(depvals) > 1:
            ylbl = self.data.label(depnames[0])
            phlbl = f"Arg({depnames[0]})"
        else:
            ylbl = None
            phlbl = None

        for yname, yvals in zip(depnames, depvals):
            # otherwise we sometimes raise ComplexWarning. This is basically just
            # cosmetic.
            if isinstance(yvals, np.ma.MaskedArray):
                yvals = yvals.filled(np.nan)

            if self.complexRepresentation in [ComplexRepresentation.real,
                                              ComplexRepresentation.realAndImag]:
                plot1dTrace(axes[0], xvals, yvals,
                            axLabels=(self.data.label(xname), ylbl),
                            curveLabel=self.data.label(yname),
                            addLegend=(yname == depnames[-1]))

            elif self.complexRepresentation is ComplexRepresentation.magAndPhase:
                if self.dataIsComplex(yname):
                    plot1dTrace(axes[0], xvals, np.real(np.abs(yvals)),
                                axLabels=(self.data.label(xname), ylbl),
                                curveLabel=f"Abs({self.data.label(yname)})",
                                addLegend=(yname == depnames[-1]))
                    plot1dTrace(axes[1], xvals, np.angle(yvals),
                                axLabels=(self.data.label(xname), phlbl),
                                curveLabel=f"Arg({yname})",
                                addLegend=(yname == depnames[-1]))
                else:
                    plot1dTrace(axes[0], xvals, yvals,
                                axLabels=(self.data.label(xname), ylbl),
                                curveLabel=self.data.label(yname),
                                addLegend=(yname == depnames[-1]))

    def _plot1dSeparatePanels(self):
        xname = self.data.axes()[0]
        xvals = self.data.data_vals(xname)
        depnames = self.data.dependents()
        depvals = [self.data.data_vals(d) for d in depnames]

        if self.complexRepresentation in [ComplexRepresentation.real,
                                          ComplexRepresentation.realAndImag]:
            nAxes = len(depnames)
        else:
            nAxes = 0
            for d in depnames:
                if self.dataIsComplex(d):
                    nAxes += 2
                else:
                    nAxes += 1
        axes = self._makeAxes(nAxes)
        hasLegend = [False for ax in axes]

        iax = 0
        for yname, yvals in zip(depnames, depvals):

            # otherwise we sometimes raise ComplexWarning. This is basically just
            # cosmetic.
            if isinstance(yvals, np.ma.MaskedArray):
                yvals = yvals.filled(np.nan)

            if self.complexRepresentation in [ComplexRepresentation.real,
                                              ComplexRepresentation.realAndImag]:
                plot1dTrace(axes[iax], xvals, yvals,
                            axLabels=(self.data.label(xname), self.data.label(yname)),
                            addLegend=self.dataIsComplex(yname))
                iax += 1

            elif self.complexRepresentation is ComplexRepresentation.magAndPhase:
                if self.dataIsComplex(yname):
                    plot1dTrace(axes[iax], xvals, np.real(np.abs(yvals)),
                                axLabels=(self.data.label(xname),
                                          f"Abs({self.data.label(yname)})"))
                    plot1dTrace(axes[iax+1], xvals, np.angle(yvals),
                                axLabels=(self.data.label(xname),
                                          f"Arg({yname})"))
                    iax += 2
                else:
                    plot1dTrace(axes[iax], xvals, yvals,
                                axLabels=(self.data.label(xname),
                                          self.data.label(yname)))
                    iax += 1

    def _colorplot2d(self):
        xname = self.data.axes()[0]
        yname = self.data.axes()[1]
        xvals = self.data.data_vals(xname)
        yvals = self.data.data_vals(yname)
        depnames = self.data.dependents()
        depvals = [self.data.data_vals(d) for d in depnames]

        if self.complexRepresentation is ComplexRepresentation.real:
            nAxes = len(depnames)
        else:
            nAxes = 0
            for d in depnames:
                if self.dataIsComplex(d):
                    nAxes += 2
                else:
                    nAxes += 1
        axes = self._makeAxes(nAxes)

        iax = 0
        for zname, zvals in zip(depnames, depvals):

            # otherwise we sometimes raise ComplexWarning. This is basically just
            # cosmetic.
            if isinstance(zvals, np.ma.MaskedArray):
                zvals = zvals.filled(np.nan)

            if self.complexRepresentation is ComplexRepresentation.real \
                    or not self.dataIsComplex(zname):
                colorplot2d(axes[iax], xvals, yvals, zvals.real,
                            self.plotType,
                            axLabels=(self.data.label(xname),
                                      self.data.label(yname),
                                      self.data.label(zname)))
                iax += 1

            elif self.complexRepresentation is ComplexRepresentation.realAndImag:
                colorplot2d(axes[iax], xvals, yvals, zvals.real,
                            self.plotType,
                            axLabels=(self.data.label(xname),
                                      self.data.label(yname),
                                      f"Re( {self.data.label(zname)} )"))
                colorplot2d(axes[iax+1], xvals, yvals, zvals.imag,
                            self.plotType,
                            axLabels=(self.data.label(xname),
                                      self.data.label(yname),
                                      f"Im( {self.data.label(zname)} )"))
                iax += 2

            elif self.complexRepresentation is ComplexRepresentation.magAndPhase:
                colorplot2d(axes[iax], xvals, yvals, np.abs(zvals),
                            self.plotType,
                            axLabels=(self.data.label(xname),
                                      self.data.label(yname),
                                      f"Abs( {self.data.label(zname)} )"))
                colorplot2d(axes[iax+1], xvals, yvals, np.angle(zvals),
                            self.plotType,
                            axLabels=(self.data.label(xname),
                                      self.data.label(yname),
                                      f"Arg( {self.data.label(zname)} )"),
                            norm=SymmetricNorm(), cmap=symmetric_cmap
                            )
                iax += 2
