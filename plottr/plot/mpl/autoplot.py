"""
plottr/plot/mpl/autoplot.py  -- tools for automatically generating matplotlib
plots from input data.
"""

import logging
from typing import Dict, List, Tuple, Union, Callable, Optional, Any, Type
from collections import OrderedDict
from enum import Enum, auto, unique

import numpy as np
from matplotlib import rc, pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
from matplotlib.image import AxesImage

from plottr import QtWidgets, QtCore, Signal, Slot
from plottr.data.datadict import DataDictBase
from plottr.icons import (get_singleTracePlotIcon, get_multiTracePlotIcon, get_imagePlotIcon,
                          get_colormeshPlotIcon, get_scatterPlot2dIcon)
from ..base import AutoFigureMaker as BaseFM, PlotDataType, \
    PlotItem, SubPlot, ComplexRepresentation, determinePlotDataType
from .widgets import MPLPlotWidget
from .utils import attachColorAx


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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


class FigureMaker(BaseFM):
    """Matplotlib implementation for :class:`.AutoFigureMaker`."""

    def __init__(self, fig: Figure):
        super().__init__()
        self.fig = fig
        self.plotType = PlotType.empty

    def __exit__(self, exc_type, exc_value, traceback):
        self.fig.clear()
        super().__exit__(exc_type, exc_value, traceback)

    # inherited methods
    def addData(self, *data: np.ndarray, join: Optional[int] = None,
                labels: Optional[List[str]] = None,
                plotDataType: PlotDataType = PlotDataType.unknown,
                **plotOptions: Any) -> int:

        if self.plotType == PlotType.multitraces and join is None:
            join = -1
        return super().addData(*data, join=join, labels=labels,
                               plotDataType=plotDataType, **plotOptions)

    def makeSubPlots(self, nSubPlots: int) -> List[Axes]:
        if nSubPlots > 0:
            nrows = int(nSubPlots ** .5 + .5)
            ncols = int(np.ceil(nSubPlots / nrows))
            gs = GridSpec(nrows, ncols, self.fig)
            axes = [self.fig.add_subplot(gs[i]) for i in range(nSubPlots)]
        else:
            axes = []
        return axes

    def formatSubPlot(self, subPlotId: int):
        labels = self.subPlotLabels(subPlotId)
        axes = self.subPlots[subPlotId].axes

        if len(axes) > 0:
            if len(labels) > 0 and len(set(labels[0])) == 1:
                axes[0].set_xlabel(labels[0][0])
            if len(labels) > 1 and len(set(labels[1])) == 1:
                axes[0].set_ylabel(labels[1][0])

        if len(labels) == 2 and len(set(labels[1])) > 1:
            axes[0].legend(loc='best', fontsize='small')

        if len(axes) > 1:
            if len(labels) > 2 and len(set(labels[2])) == 1:
                axes[1].set_ylabel(labels[2][0])

    def plot(self, plotItem: PlotItem):
        if plotItem.plotDataType in [PlotDataType.line1d, PlotDataType.scatter1d]:
            return self.plotLine(plotItem)
        if plotItem.plotDataType == PlotDataType.grid2d:
            return self.plotImage(plotItem)

    # methods specific to this class
    def plotLine(self, plotItem: PlotItem):
        ax = self.subPlots[plotItem.subPlot].axes[0]
        return ax.plot(*plotItem.data, label=plotItem.labels[-1],
                       **plotItem.plotOptions)

    def plotImage(self, plotItem: PlotItem):
        ax = self.subPlots[plotItem.subPlot].axes[0]
        return ax.imshow(plotItem.data[-1], origin='lower')

    # def _plot(self, name, **plot_kwargs):
    #     item = self.plotItems[name]
    #     pf = item['plot_func']
    #     data = list(item['data'])
    #     ax = self.subPlots[item['ax']]
    #
    #     # if we have z-values, then that means we need to have a color subPlots
    #     axlst = [ax['subPlots']]
    #     if len(data) > 2 and ax['cax'] is None:
    #         ax['cax'] = attach_color_ax(ax['subPlots'])
    #
    #     # assemble the call to the plot function
    #     args = axlst + data
    #     opts = item['plot_kwargs'].copy()
    #     opts.update(plot_kwargs)
    #
    #     ret = self.plotItems[name]['artist'] = pf(*args, **opts)
    #     if len(data) > 2 and isinstance(ret, AxesImage):
    #         if 'colorbar' not in self.plotItems[name]:
    #             cb = self.plotItems[name]['colorbar'] = \
    #                 self.fig.colorbar(ret, cax=ax['cax'])


# A toolbar for setting options on the MPL autoplot
class AutoPlotToolBar(QtWidgets.QToolBar):
    """
    A toolbar that allows the user to configure AutoPlot.

    Currently, the user can select between the plots that are possible, given
    the data that AutoPlot has.
    """

    #: signal emitted when the plot type has been changed
    plotTypeSelected = Signal(PlotType)

    #: signal emitted when the complex data option has been changed
    complexPolarSelected = Signal(bool)

    def __init__(self, name: str, parent: Optional[QtWidgets.QWidget] = None):
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
        self.plotComplexPolar.triggered.connect(self._trigger_complex_mag_phase)

        self.plotTypeActions = OrderedDict({
            PlotType.multitraces: self.plotasMultiTraces,
            PlotType.singletraces: self.plotasSingleTraces,
            PlotType.image: self.plotasImage,
            PlotType.colormesh: self.plotasMesh,
            PlotType.scatter2d: self.plotasScatter2d,
        })

        self._currentPlotType = PlotType.empty
        self._currentlyAllowedPlotTypes: Tuple[PlotType, ...] = ()

    def _trigger_complex_mag_phase(self, enable: bool) -> None:
        self.complexPolarSelected.emit(enable)

    def selectPlotType(self, plotType: PlotType) -> None:
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

    def setAllowedPlotTypes(self, *args: PlotType) -> None:
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


class AutoPlot(MPLPlotWidget):
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

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent=parent)

        self.plotDataType = PlotDataType.unknown
        self.plotType = PlotType.empty
        self.complexRepresentation = ComplexRepresentation.real
        self.complexPreference = ComplexRepresentation.realAndImag

        # A toolbar for configuring the plot
        self.plotOptionsToolBar = AutoPlotToolBar('Plot options', self)
        self.layout().insertWidget(1, self.plotOptionsToolBar)

        self.plotOptionsToolBar.plotTypeSelected.connect(
            self._plotTypeFromToolBar
        )
        self.plotOptionsToolBar.complexPolarSelected.connect(
            self._complexPreferenceFromToolBar
        )

        self.plotOptionsToolBar.setIconSize(QtCore.QSize(32, 32))

        self.setMinimumSize(640, 480)

    def setData(self, data: Optional[DataDictBase]) -> None:
        """Analyses data and determines whether/what to plot.

        :param data: input data
        """
        super().setData(data)
        self.plotDataType = determinePlotDataType(data)
        self._processPlotTypeOptions()
        self._plotData()

    def _processPlotTypeOptions(self) -> None:
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
            self.plotOptionsToolBar.setAllowedPlotTypes()

    @Slot(PlotType)
    def _plotTypeFromToolBar(self, plotType: PlotType) -> None:
        if plotType is not self.plotType:
            self.plotType = plotType
            self._plotData()

    @Slot(bool)
    def _complexPreferenceFromToolBar(self, magPhasePreferred: bool) -> None:
        if magPhasePreferred:
            self.complexPreference = ComplexRepresentation.magAndPhase
        else:
            self.complexPreference = ComplexRepresentation.realAndImag
        self._plotData()

    def _plotData(self) -> None:
        """Plot the data using previously determined data and plot types."""

        if self.plotDataType is PlotDataType.unknown:
            logger.debug("No plottable data.")
            return
        if self.plotType is PlotType.empty:
            logger.debug("No plot routine determined.")
            return

        assert self.data is not None

        kw = {}
        with FigureMaker(self.plot.fig) as fm:
            fm.plotType = self.plotType
            if not self.dataIsComplex():
                fm.complexRepresentation = ComplexRepresentation.real
            else:
                fm.complexRepresentation = self.complexPreference

            indeps = self.data.axes()
            for dn in self.data.dependents():
                dvals = self.data.data_vals(dn)
                plotId = fm.addData(
                    *[np.asanyarray(self.data.data_vals(n)) for n in indeps]+[dvals],
                    labels=[self.data.label(n) for n in indeps]+[self.data.label(dn)],
                    plotDataType=self.plotDataType,
                    **kw)

        self.setMeta(self.data)
        self.plot.draw()
        QtCore.QCoreApplication.processEvents()

    # def _colorplot2d(self) -> None:
    #     assert self.data is not None
    #     xname = self.data.axes()[0]
    #     yname = self.data.axes()[1]
    #     xvals = np.asanyarray(self.data.data_vals(xname))
    #     yvals = np.asanyarray(self.data.data_vals(yname))
    #     depnames = self.data.dependents()
    #     depvals = [self.data.data_vals(d) for d in depnames]
    #
    #     if self.complexRepresentation is ComplexRepresentation.real:
    #         nAxes = len(depnames)
    #     else:
    #         nAxes = 0
    #         for d in depnames:
    #             if self.dataIsComplex(d):
    #                 nAxes += 2
    #             else:
    #                 nAxes += 1
    #     axes = self._makeAxes(nAxes)
    #
    #     iax = 0
    #     for zname, zvals in zip(depnames, depvals):
    #
    #         # otherwise we sometimes raise ComplexWarning. This is basically just
    #         # cosmetic.
    #         if isinstance(zvals, np.ma.MaskedArray):
    #             zvals = zvals.filled(np.nan)
    #
    #         if self.complexRepresentation is ComplexRepresentation.real \
    #                 or not self.dataIsComplex(zname):
    #             colorplot2d(axes[iax], xvals, yvals, np.asanyarray(zvals).real,
    #                         self.plotType,
    #                         axLabels=(self.data.label(xname),
    #                                   self.data.label(yname),
    #                                   self.data.label(zname)))
    #             iax += 1
    #
    #         elif self.complexRepresentation is ComplexRepresentation.realAndImag:
    #             colorplot2d(axes[iax], xvals, yvals, np.asanyarray(zvals).real,
    #                         self.plotType,
    #                         axLabels=(self.data.label(xname),
    #                                   self.data.label(yname),
    #                                   f"Re( {self.data.label(zname)} )"))
    #             colorplot2d(axes[iax+1], xvals, yvals, np.asanyarray(zvals).imag,
    #                         self.plotType,
    #                         axLabels=(self.data.label(xname),
    #                                   self.data.label(yname),
    #                                   f"Im( {self.data.label(zname)} )"))
    #             iax += 2
    #
    #         elif self.complexRepresentation is ComplexRepresentation.magAndPhase:
    #             colorplot2d(axes[iax], xvals, yvals, np.abs(np.asanyarray(zvals)),
    #                         self.plotType,
    #                         axLabels=(self.data.label(xname),
    #                                   self.data.label(yname),
    #                                   f"Abs( {self.data.label(zname)} )"))
    #             colorplot2d(axes[iax+1], xvals, yvals, np.angle(np.asanyarray(zvals)),
    #                         self.plotType,
    #                         axLabels=(self.data.label(xname),
    #                                   self.data.label(yname),
    #                                   f"Arg( {self.data.label(zname)} )"),
    #                         norm=SymmetricNorm(), cmap=symmetric_cmap
    #                         )
    #             iax += 2
