from .. import QtGui, QtCore
from ..node.node import Node
from ..data.datadict import DataDictBase


class PlotNode(Node):
    """
    Basic Plot Node.

    ATM this doesn't do much besides passing data to the plotting widget.
    Data is at the moment just passed through.
    """
    nodeName = 'Plot'
    newPlotData = QtCore.pyqtSignal(object)

    def __init__(self, name: str):
        super().__init__(name=name)
        self.plotWidget = None

    def setPlotWidget(self, widget):
        self.plotWidget = widget
        self.newPlotData.connect(self.plotWidget.setData)

    def process(self, **kw):
        data = kw['dataIn']
        self.newPlotData.emit(data)
        return dict(dataOut=data)


class PlotWidgetWrapper(QtGui.QWidget):
    """
    This is the base widget for Plots.

    This widget does not implement any plotting. It merely is a wrapping
    widget that contains the actual plot widget in it. This actual plot
    widget can be set dynamically.
    However, PlotWidget does provide some common functionality that all
    plotting widgets in general are expected to have.
    """

    def __init__(self, parent: QtGui.QWidget = None):
        super().__init__(parent=parent)

        self.plotWidget = None
        self.data = None

        self.layout = QtGui.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

    def setPlotWidget(self, widget: QtGui.QWidget):
        """set the plot widget."""
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
        self.data = data
        if self.plotWidget is not None:
            self.plotWidget.setData(self.data)


class PlotWidget(QtGui.QWidget):
    """
    Base class for Plot Widgets.
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def setData(self, data: DataDictBase):
        # self.data = data
        pass

    def plotData(self, data: DataDictBase):
        raise NotImplementedError

