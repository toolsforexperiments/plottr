"""
plottr/plot/base.py : Contains the base classes for plotting nodes and widgets.

Most things that are independent of plotting backend are in here.
"""

from enum import Enum, unique, auto
from typing import Dict, List, Type, Tuple, Optional, Any, \
    OrderedDict as OrderedDictType
from collections import OrderedDict
from dataclasses import dataclass
from copy import copy, deepcopy

import numpy as np

from .. import Signal, Flowchart, QtWidgets
from ..data.datadict import DataDictBase, DataDict, MeshgridDataDict
from ..node import Node, linearFlowchart


__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


class PlotNode(Node):
    """
    Basic Plot Node, derived from :class:`plottr.node.node.Node`.

    At the moment this doesn't do much besides passing data to the plotting widget.
    Data is just passed through.
    On receipt of new data, :attr:`newPlotData` is emitted.
    """
    nodeName = 'Plot'

    #: Signal emitted when :meth:`process` is called, with the data passed to
    #: it as argument.
    newPlotData = Signal(object)

    def __init__(self, name: str):
        """Constructor for :class:`PlotNode`. """
        super().__init__(name=name)
        self.plotWidgetContainer: Optional['PlotWidgetContainer'] = None

    def setPlotWidgetContainer(self, w: 'PlotWidgetContainer') -> None:
        """Set the plot widget container.

        Makes sure that newly arriving data is sent to plot GUI elements.

        :param w: container to connect the node to.
        """
        self.plotWidgetContainer = w
        self.newPlotData.connect(self.plotWidgetContainer.setData)

    def process(self, dataIn: Optional[DataDictBase] = None) -> Dict[str, Optional[DataDictBase]]:
        """Emits the :attr:`newPlotData` signal when called.
        Note: does not call the parent method :meth:`plottr.node.node.Node.process`.

        :param dataIn: input data
        :returns: input data as is: ``{dataOut: dataIn}``
        """
        self.newPlotData.emit(dataIn)
        return dict(dataOut=dataIn)


class PlotWidgetContainer(QtWidgets.QWidget):
    """
    This is the base widget for Plots, derived from `QWidget`.

    This widget does not implement any plotting. It merely is a wrapping
    widget that contains the actual plot widget in it. This actual plot
    widget can be set dynamically.

    Use :class:`PlotWidget` as base for implementing widgets that can be
    added to this container.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Constructor for :class:`PlotWidgetContainer`. """
        super().__init__(parent=parent)

        self.plotWidget: Optional["PlotWidget"] = None
        self.data: Optional[DataDictBase] = None

        layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def setPlotWidget(self, widget: "PlotWidget") -> None:
        """Set the plot widget.

        Makes sure that the added widget receives new data.

        :param widget: plot widget
        """

        # TODO: disconnect everything, make sure old widget is garbage collected

        if widget is self.plotWidget:
            return

        if self.plotWidget is not None:
            self.layout().removeWidget(self.plotWidget)
            self.plotWidget.deleteLater()

        self.plotWidget = widget
        if self.plotWidget is not None:
            self.layout().addWidget(widget)
            self.plotWidget.setData(self.data)

    def setData(self, data: DataDictBase) -> None:
        """set Data. If a plot widget is defined, call the widget's
        :meth:`PlotWidget.setData` method.

        :param data: input data to be plotted.
        """
        self.data = data
        if self.plotWidget is not None:
            self.plotWidget.setData(self.data)


class PlotWidget(QtWidgets.QWidget):
    """
    Base class for Plot Widgets, this just defines the API. Derived from
    `QWidget`.

    Implement a child class for actual plotting.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent=parent)

        self.data: Optional[DataDictBase] = None

    def setData(self, data: Optional[DataDictBase]) -> None:
        """Set data. Use this to trigger plotting.

        :param data: data to be plotted.
        """
        self.data = data


def makeFlowchartWithPlot(nodes: List[Tuple[str, Type[Node]]],
                          plotNodeName: str = 'plot') -> Flowchart:
    nodes.append((plotNodeName, PlotNode))
    fc = linearFlowchart(*nodes)
    return fc


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


@dataclass
class PlotItem:
    data: List[np.ndarray]
    id: int
    subPlot: int
    labels: Optional[List[str]] = None
    style: Optional[str] = None
    plotOptions: Optional[Dict[str, Any]] = None
    plotReturn: Optional[Any] = None


@dataclass
class SubPlot:
    id: int
    axes: Optional[List[Any]] = None


class AutoFigureMaker(object):
    """A class for semi-automatic creation of plot figures.
    It must be inherited to tie it to a specific plotting backend.

    The main purpose of this class is to (a) implement actual plotting of
    plot items, and (b) distribute plot items correctly among subpanels of
    a figure.

    FigureMaker is a context manager. The user should eventually only need to
    add data and specify what kind of data it is. FigureMaker will then
    generate plots from that.

    In the simplest form, usage looks something like this::

        >>> with FigureMaker() as fm:
        >>>     fm.addData(x, y, [...])
        >>>     [...]

    See :method:`addData` for details on how to specify data and how to pass
    plot options to it.
    """

    # TODO: implement feature for always plotting certain traces with other
    #   other ones ('children'). This is mainly used for models/fits.
    #   needs a system to copy certain style aspects from the parents.
    # TODO: similar, but with siblings (imagine Re/Im parts)

    def __init__(self):
        self.subPlots: OrderedDictType[int, SubPlot] = OrderedDict()
        self.plotItems: OrderedDictType[int, PlotItem] = OrderedDict()

        #: how to represent complex data.
        #: must be set before adding data to the plot to have an effect.
        self.complex_representation = ComplexRepresentation.realAndImag

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._makeAxes()
        for id in self.subPlots.keys():
            self._makeSubPlot(id)

    # private methods
    def _makeAxes(self) -> None:
        n = self.nSubPlots()
        for id, axes in zip(range(n), self.makeAxes(n)):
            if not isinstance(axes, list):
                axes = [axes]
            self.subPlots[id] = SubPlot(id, axes)

    def addPanel(self) -> int:
        id = _generate_auto_dict_key(self.subPlots)
        self.subPlots[id] = SubPlot(id, [])
        return id

    def _makeSubPlot(self, id: int):
        items = self.subPlotItems(id)
        for name, item in items.items():
            self._plot(item)
        self.formatSubPlot(id)

    def _plot(self, plotItem: PlotItem):
        if plotItem.style is None:
            if len(plotItem.data) == 2:
                style = 'line'
            elif len(plotItem.data) == 3:
                style = 'image'
            else:
                raise ValueError("Cannot automatically determine plot style.")
        else:
            style = plotItem.style

        if hasattr(self, f'plot_{style}'):
            plotFunc = getattr(self, f'plot_{style}')
        else:
            raise ValueError(f"No plot function for style '{style}'.")
        plotItem.plotReturn = plotFunc(plotItem)

    def _splitComplexData(self, plotItem: PlotItem) -> List[PlotItem]:
        if not np.issubsctype(plotItem.data[-1], np.complexfloating):
            return [plotItem]

        label = plotItem.labels[-1]
        if self.complex_representation is ComplexRepresentation.realAndImag:
            re_data = plotItem.data[-1].real
            im_data = plotItem.data[-1].imag

            if label == '':
                re_label, im_label = 'Real', 'Imag'
            else:
                re_label, im_label = label + ' (Real)', label + ' (Imag)'

            re_plotItem = plotItem
            im_plotItem = deepcopy(re_plotItem)

            # FIXME: for > 1d data we should have separate panels!
            re_plotItem.data[-1] = re_data
            re_plotItem.labels[-1] = re_label
            im_plotItem.data[-1] = im_data
            im_plotItem.labels[-1] = im_label
            im_plotItem.id = re_plotItem.id + 1
            return [re_plotItem, im_plotItem]

        if self.complex_representation is ComplexRepresentation.magAndPhase:
            mag_data = np.abs(plotItem.data[-1])
            phase_data = np.angle(plotItem.data[-1])

            if label == '':
                mag_label, phase_label = 'Mag', 'Phase'
            else:
                mag_label, phase_label = label + ' (Mag)', label + ' (Phase)'

            mag_plotItem = plotItem
            phase_plotItem = deepcopy(mag_plotItem)

            mag_plotItem.data[-1] = mag_data
            mag_plotItem.labels[-1] = mag_label
            phase_plotItem.data[-1] = phase_data
            phase_plotItem.labels[-1] = phase_label
            phase_plotItem.id = mag_plotItem.id + 1
            phase_plotItem.subPlot = mag_plotItem.subPlot + 1
            return [mag_plotItem, phase_plotItem]

    # public methods
    def nSubPlots(self):
        ids = []
        for id, item in self.plotItems.items():
            ids.append(item.subPlot)
        return len(set(ids))

    def subPlotItems(self, subPlotId: int) -> OrderedDictType[int, PlotItem]:
        items = OrderedDict()
        for id, item in self.plotItems.items():
            if item.subPlot == subPlotId:
                items[id] = item
        return items

    def subPlotLabels(self, subPlotId: int) -> List[List[str]]:
        ret = []
        items = self.subPlotItems(subPlotId)
        for id, item in items.items():
            if item.labels is not None:
                for i, l in enumerate(item.labels):
                    while(len(ret)) <= i:
                        ret.append([])
                    ret[i].append(l)
        return ret

    def addData(self, *data: np.ndarray, join: Optional[int] = None,
                labels: Optional[List[str]] = None, style: Optional[str] = None,
                **plotOptions: Any) -> int:

        id = _generate_auto_dict_key(self.plotItems)
        if join is None:
            subPlotId = self.nSubPlots()
        else:
            subPlotId = self.plotItems[join].subPlot

        if labels is None:
            labels = [''] * len(data)

        plotItem = PlotItem(list(data), id, subPlotId,
                            labels, style, plotOptions)

        for p in self._splitComplexData(plotItem):
            self.plotItems[p.id] = p

        return id

    # Methods to be implemented by inheriting classes
    def makeAxes(self, nSubPlots: int) -> List[Any]:
        raise NotImplementedError

    def formatSubPlot(self, subPlotId: int):
        pass

    def plot_line(self, plotItem: PlotItem):
        raise NotImplementedError

    def plot_image(self, plotItem: PlotItem):
        raise NotImplementedError


def _generate_auto_dict_key(d: Dict):
    guess = 0
    while guess in d.keys():
        guess += 1
    return guess
