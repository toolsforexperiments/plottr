"""
plottr/plot/base.py : Contains the base classes for plotting nodes and widgets.
"""

from typing import Dict, List, Type, Tuple, Optional

from .. import Signal, Flowchart, QtWidgets
from ..data.datadict import DataDictBase
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

    def setPlotWidgetContainer(self, w: 'PlotWidgetContainer'):
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

    def __init__(self, parent: QtWidgets.QWidget = None):
        """Constructor for :class:`PlotWidgetContainer`. """
        super().__init__(parent=parent)

        self.plotWidget: Optional["PlotWidget"] = None
        self.data: Optional[DataDictBase] = None

        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

    def setPlotWidget(self, widget: "PlotWidget"):
        """Set the plot widget.

        Makes sure that the added widget receives new data.

        :param widget: plot widget
        """

        # TODO: disconnect everything, make sure old widget is garbage collected

        if widget is self.plotWidget:
            return

        if self.plotWidget is not None:
            self.layout.removeWidget(self.plotWidget)
            self.plotWidget.deleteLater()

        self.plotWidget = widget
        if self.plotWidget is not None:
            self.layout.addWidget(widget)
            self.plotWidget.setData(self.data)

    def setData(self, data: DataDictBase):
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

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.data = None

    def setData(self, data: Optional[DataDictBase]):
        """Set data. Use this to trigger plotting.

        :param data: data to be plotted.
        """
        self.data = data


def makeFlowchartWithPlot(nodes: List[Tuple[str, Type[Node]]],
                          plotNodeName: str = 'plot') -> Flowchart:
    nodes.append((plotNodeName, PlotNode))
    fc = linearFlowchart(*nodes)
    return fc
