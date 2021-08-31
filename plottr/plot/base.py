"""
``plottr.plot.base`` -- Contains the base classes for plotting nodes and widgets.
Everything in here is independent of actual plotting backend, and does not contain plotting commands.
"""

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum, unique, auto
from types import TracebackType
from typing import Dict, List, Type, Tuple, Optional, Any, \
    OrderedDict as OrderedDictType, Union

import numpy as np

from .. import Signal, Flowchart, QtWidgets
from ..data.datadict import DataDictBase, DataDict, MeshgridDataDict
from ..node import Node, linearFlowchart
from ..utils import LabeledOptions

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

    def __init__(self, parent: Optional[PlotWidgetContainer] = None) -> None:
        super().__init__(parent=parent)

        self.data: Optional[DataDictBase] = None
        self.dataType: Optional[Type[DataDictBase]] = None
        self.dataStructure: Optional[DataDictBase] = None
        self.dataShapes: Optional[Dict[str, Tuple[int, ...]]] = None
        self.dataLimits: Optional[Dict[str, Tuple[float, float]]] = None
        self.dataChanges: Dict[str, bool] = {
            'dataTypeChanged': False,
            'dataStructureChanged': False,
            'dataShapesChanged': False,
            'dataLimitsChanged': False,
        }

    def updatePlot(self) -> None:
        return None

    def setData(self, data: Optional[DataDictBase]) -> None:
        """Set data. Use this to trigger plotting.

        :param data: data to be plotted.
        """
        self.data = data
        self.dataChanges = self.analyzeData(data)

    def analyzeData(self, data: Optional[DataDictBase]) -> Dict[str, bool]:
        """checks data and compares with previous properties.

        :param data: incoming data to compare to already existing data in the object.
        :return: dictionary with information on what has changed from previous to new data.
            contains key/value pairs where the key is the property analyzed, and the value is True of False. Keys are:

            * `dataTypeChanged` -- has the data class changed?
            * `dataStructureChanged` -- has the internal structure (data fields, etc) changed?
            * `dataShapesChanged` -- have the data fields changed shape?
            * `dataLimitsChanged` -- have the maxima/minima of the data fields changed?

        """
        if data is not None:
            dataType: Optional[Type[DataDictBase]] = type(data)
        else:
            dataType = None

        if data is None:
            dataStructure: Optional[DataDictBase] = None
            dataShapes: Optional[Dict[str, Tuple[int, ...]]] = None
            dataLimits: Optional[Dict[str, Tuple[Any, Any]]] = None
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

    def dataIsComplex(self, dependentName: Optional[str] = None) -> bool:
        """Determine whether our data is complex.

        :param dependentName: name of the dependent to check. if `None`, check all.
        :return: `True` if data is complex, `False` if not.
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


def makeFlowchartWithPlot(nodes: List[Tuple[str, Type[Node]]],
                          plotNodeName: str = 'plot') -> Flowchart:
    """create a linear FlowChart terminated with a plot node.

    :param nodes: List of Node classes, in the order they are to be arranged.
    :param plotNodeName: name of the plot node that will be appended.
    :return: the resulting FlowChart instance
    """
    nodes.append((plotNodeName, PlotNode))
    fc = linearFlowchart(*nodes)
    return fc


# Types of plots and plottable data
@unique
class PlotDataType(Enum):
    """Types of (plottable) data"""

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


class ComplexRepresentation(LabeledOptions):
    """Options for plotting complex-valued data."""

    #: only real
    real = "Real"

    #: real and imaginary
    realAndImag = "Real/Imag"

    #: real and imaginary, separated
    realAndImagSeparate = "Real/Imag (split)"

    #: magnitude and phase
    magAndPhase = "Mag/Phase"


def determinePlotDataType(data: Optional[DataDictBase]) -> PlotDataType:
    """
    Analyze input data and determine most likely :class:`PlotDataType`.

    Analysis is simply based on number of dependents and data type.

    :param data: data to analyze.
    :return: type of plot data inferred
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
    """Data class describing a plot item in :class:`.AutoFigureMaker`."""
    #: List of data arrays (independents and one dependent)
    data: List[Union[np.ndarray, np.ma.MaskedArray]]
    #: unique ID of the plot item
    id: int
    #: ID of the subplot the item will be plotted in
    subPlot: int
    #: type of plot data (unknown is typically OK)
    plotDataType: PlotDataType = PlotDataType.unknown
    #: labels of the data arrays
    labels: Optional[List[str]] = None
    #: options to be passed to plotting functions (depends on backend). Could be formatting options, for example.
    plotOptions: Optional[Dict[str, Any]] = None
    #: return value from the plot command (like matplotlib Artists)
    plotReturn: Optional[Any] = None


@dataclass
class SubPlot:
    """Data class describing a subplot in a :class:`.AutoFigureMaker`."""
    #: ID of the subplot (unique per figure)
    id: int
    #: list of subplot objects (type depends on backend)
    axes: Optional[List[Any]] = None


class AutoFigureMaker:
    """A class for semi-automatic creation of plot figures.
    It must be inherited to tie it to a specific plotting backend.

    The main purpose of this class is to (a) implement actual plotting of
    plot items, and (b) distribute plot items correctly among subpanels of
    a figure.

    FigureMaker is a context manager. The user should eventually only need to
    add data and specify what kind of data it is. FigureMaker will then
    generate plots from that.

    In the simplest form, usage looks something like this::

        >>> with AutoFigureMaker() as fm:
        >>>     fm.addData(x, y, [...])
        >>>     [...]

    See :meth:`addData` for details on how to specify data and how to pass
    plot options to it.
    """

    # TODO: implement feature for always plotting certain traces with other
    #   other ones ('children'). This is mainly used for models/fits.
    #   needs a system to copy certain style aspects from the parents.
    # TODO: similar, but with siblings (imagine Re/Im parts)

    def __init__(self) -> None:

        #: subplots to create
        self.subPlots: OrderedDictType[int, SubPlot] = OrderedDict()

        #: items that will be plotted
        self.plotItems: OrderedDictType[int, PlotItem] = OrderedDict()

        #: ids of all main plot items (does not contain derived/secondary plot items)
        self.plotIds: List = []

        #: ids of all plot items, incl those who are 'joined' with 'main' plot items.
        self.allPlotIds: List = []

        #: how to represent complex data.
        #: must be set before adding data to the plot to have an effect.
        self.complexRepresentation: ComplexRepresentation = ComplexRepresentation.realAndImag

        #: whether to combine 1D traces into one plot
        self.combineTraces: bool = False

    def __enter__(self) -> "AutoFigureMaker":
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]) -> None:

        self._makeAxes()
        for id in self.subPlots.keys():
            self._makeSubPlot(id)

    # private methods
    def _makeAxes(self) -> None:
        n = self.nSubPlots()
        for id, axes in zip(range(n), self.makeSubPlots(n)):
            if not isinstance(axes, list):
                axes = [axes]
            self.subPlots[id] = SubPlot(id, axes)
        return None

    def _makeSubPlot(self, id: int) -> None:
        items = self.subPlotItems(id)
        for name, item in items.items():
            item.plotReturn = self.plot(item)
        self.formatSubPlot(id)
        return None

    def _splitComplexData(self, plotItem: PlotItem) -> List[PlotItem]:
        if plotItem.labels is None:
            plotItem.labels = [''] * len(plotItem.data)
        label = plotItem.labels[-1]

        if not np.issubsctype(plotItem.data[-1], np.complexfloating):
            return [plotItem]

        elif self.complexRepresentation is ComplexRepresentation.real:
            plotItem.data[-1] = plotItem.data[-1].real
            assert isinstance(plotItem.labels, list)
            if label == '':
                plotItem.labels[-1] = 'Real'
            else:
                plotItem.labels[-1] = label + ' (Real)'
            return [plotItem]

        elif self.complexRepresentation in \
                [ComplexRepresentation.realAndImag, ComplexRepresentation.realAndImagSeparate]:

            re_data = plotItem.data[-1].real
            im_data = plotItem.data[-1].imag

            if label == '':
                re_label, im_label = 'Real', 'Imag'
            else:
                re_label, im_label = label + ' (Real)', label + ' (Imag)'

            re_plotItem = plotItem
            im_plotItem = deepcopy(re_plotItem)

            re_plotItem.data[-1] = re_data
            im_plotItem.data[-1] = im_data
            im_plotItem.id = re_plotItem.id + 1

            if self.complexRepresentation == ComplexRepresentation.realAndImagSeparate \
                    or len(plotItem.data) > 2:
                im_plotItem.subPlot = re_plotItem.subPlot + 1

            # this is a bit of a silly check (see top of the function -- should certainly be True!).
            # but it keeps mypy happy.
            assert isinstance(re_plotItem.labels, list)
            re_plotItem.labels[-1] = re_label
            assert isinstance(im_plotItem.labels, list)
            im_plotItem.labels[-1] = im_label

            return [re_plotItem, im_plotItem]

        else:  # means that self.complexRepresentation is ComplexRepresentation.magAndPhase:
            data = plotItem.data[-1]

            # this check avoids a numpy ComplexWarning when we're working with MaskedArray (almost always)
            mag_data = np.ma.abs(data).real if isinstance(data, np.ma.MaskedArray) else np.abs(data)
            phase_data = np.angle(data)

            if label == '':
                mag_label, phase_label = 'Mag', 'Phase'
            else:
                mag_label, phase_label = label + ' (Mag)', label + ' (Phase)'

            mag_plotItem = plotItem
            phase_plotItem = deepcopy(mag_plotItem)

            mag_plotItem.data[-1] = mag_data
            phase_plotItem.data[-1] = phase_data
            phase_plotItem.id = mag_plotItem.id + 1
            phase_plotItem.subPlot = mag_plotItem.subPlot + 1

            # this is a bit of a silly check (see top of the function -- should certainly be True!).
            # but it keeps mypy happy.
            assert isinstance(mag_plotItem.labels, list)
            mag_plotItem.labels[-1] = mag_label
            assert isinstance(phase_plotItem.labels, list)
            phase_plotItem.labels[-1] = phase_label

            return [mag_plotItem, phase_plotItem]

    # public methods
    def addSubPlot(self) -> int:
        """Add a new subplot.

        :return: ID of the new subplot.
        """
        id = _generate_auto_dict_key(self.subPlots)
        self.subPlots[id] = SubPlot(id, [])
        return id

    def nSubPlots(self) -> int:
        """Count the subplots in the figure.

        :return: number of subplots
        """
        ids = []
        for id, item in self.plotItems.items():
            ids.append(item.subPlot)
        return len(set(ids))

    def subPlotItems(self, subPlotId: int) -> OrderedDictType[int, PlotItem]:
        """Get items in a given subplot.

        :param subPlotId: ID of the subplot
        :return: Dictionary with all plot items and their ids.
        """
        items = OrderedDict()
        for id, item in self.plotItems.items():
            if item.subPlot == subPlotId:
                items[id] = item
        return items

    def subPlotLabels(self, subPlotId: int) -> List[List[str]]:
        """Get the data labels for a given subplot.

        :param subPlotId: ID of the subplot.
        :return: a list with one element per plot item in the subplot.
            Each element contains a list of the labels for that item.
        """
        ret: List[List[str]] = []
        items = self.subPlotItems(subPlotId)
        for id, item in items.items():
            if item.labels is not None:
                for i, l in enumerate(item.labels):
                    while (len(ret)) <= i:
                        ret.append([])
                    ret[i].append(l)
        return ret

    def addData(self, *data: Union[np.ndarray, np.ma.MaskedArray],
                join: Optional[int] = None,
                labels: Optional[List[str]] = None,
                plotDataType: PlotDataType = PlotDataType.unknown,
                **plotOptions: Any) -> int:
        """Add data to the figure.

        :param data: data arrays describing the plot (one or more independents, one dependent)
        :param join: ID of a plot item the new item should be shown together with in the same subplot
        :param labels: list of labels for the data arrays
        :param plotDataType: what kind of plot data the supplied data contains.
        :param plotOptions: options (as kwargs) to be passed to the actual plot functions (depends on the backend)
        :return: ID of the new plot item.
        """

        if self.combineTraces and join is None:
            prev = self.previousPlotId()
            if prev is not None:
                if len(data) == 2 and len(self.plotItems[prev].data) == 2:
                    join = prev

        id = _generate_auto_dict_key(self.plotItems)

        # TODO: allow any negative number
        if join == -1:
            if len(self.plotItems) > 0:
                join = self.previousPlotId()
            else:
                join = None
        if join is None:
            subPlotId = self.nSubPlots()
        else:
            subPlotId = self.plotItems[join].subPlot

        if labels is None:
            labels = [''] * len(data)
        elif len(labels) < len(data):
            labels += [''] * (len(data) - len(labels))

        plotItem = PlotItem(list(data), id, subPlotId,
                            plotDataType, labels, plotOptions)

        for p in self._splitComplexData(plotItem):
            self.plotItems[p.id] = p
            self.allPlotIds.append(p.id)
        self.plotIds.append(id)
        return id

    def previousPlotId(self) -> Optional[int]:
        """Get the ID of the most recently added plot item.
        :return: the ID.
        """
        if not len(self.plotIds) > 0:
            return None

        if len(self.plotIds) > 0:
            return self.plotIds[-1]
        else:
            return None

    def findPlotIndexInSubPlot(self, plotId: int) -> int:
        """find the index of a plot in its subplot

        :param plotId: plot ID to check
        :return: index at which the plot is located in its subplot.
        """
        if plotId not in self.allPlotIds:
            raise ValueError("Plot ID not found.")

        subPlotId = self.plotItems[plotId].subPlot
        itemsInSubPlot = [i for i in self.allPlotIds if self.plotItems[i].subPlot == subPlotId]
        return itemsInSubPlot.index(plotId)

    def plotIdsInSubPlot(self, subPlotId: int) -> List[int]:
        """return all plot IDs in a given subplot

        :param subPlotId: ID of the subplot
        :return: list of plot IDs
        """
        itemsInSubPlot = [i for i in self.allPlotIds if self.plotItems[i].subPlot == subPlotId]
        return itemsInSubPlot

    def dataDimensionsInSubPlot(self, subPlotId: int) -> Dict[int, int]:
        """Determine what the data dimensions are in a subplot.

        :param subPlotId: ID of the subplot
        :return: dictionary with plot id as key, data dimension (i.e., number of independents) as value.
        """
        ret: Dict[int, int] = {}
        for plotId in self.plotIdsInSubPlot(subPlotId):
            ret[plotId] = len(self.plotItems[plotId].data) - 1
        return ret

    # Methods to be implemented by inheriting classes
    def makeSubPlots(self, nSubPlots: int) -> List[Any]:
        """Generate the subplots. Called after all data has been added.
        Must be implemented by an inheriting class.

        :param nSubPlots: number of subplots
        :return: return values of the subplot generation methods.
        """
        raise NotImplementedError

    def formatSubPlot(self, subPlotId: int) -> Any:
        """Format a subplot.
        May be implemented by an inheriting class.
        By default, does nothing.

        :param subPlotId: ID of the subplot.
        :return: Depends on inheriting class.
        """
        return None

    def plot(self, plotItem: PlotItem) -> Any:
        """Plot an item.
        Must be implemented by an inheriting class.

        :param plotItem: the item to plot.
        :return: Depends on the inheriting class.
        """
        raise NotImplementedError


def _generate_auto_dict_key(d: Dict) -> int:
    guess = 0
    while guess in d.keys():
        guess += 1
    return guess
