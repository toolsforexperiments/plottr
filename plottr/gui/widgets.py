"""
widgets.py

Common GUI widgets that are re-used across plottr.
"""

from typing import Union, List, Tuple, Optional, Type, Sequence, Dict

from .tools import dictToTreeWidgetItems
from plottr import QtCore, Flowchart, QtWidgets, Signal, Slot
from plottr.node import Node, linearFlowchart
from ..plot import PlotNode, PlotWidgetContainer, MPLAutoPlot

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


class FormLayoutWrapper(QtWidgets.QWidget):
    """
    Simple wrapper widget for forms.
    Expects a list of tuples of the form (label, widget),
    creates a widget that contains these using a form layout.
    Labels have to be unique.
    """

    def __init__(self, elements: List[Tuple[str, QtWidgets.QWidget]],
                 parent: Union[None, QtWidgets.QWidget] = None):
        super().__init__(parent)

        self.elements = {}

        layout = QtWidgets.QFormLayout()
        for lbl, widget in elements:
            self.elements[lbl] = widget
            layout.addRow(lbl, widget)

        self.setLayout(layout)


class MonitorIntervalInput(QtWidgets.QWidget):
    """
    Simple form-like widget for entering a monitor/refresh interval.
    Only has a label and a spin-box as input.

    It's signal `intervalChanged(int)' is emitted when the value
    of the spinbox has changed.
    """

    intervalChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.spin = QtWidgets.QSpinBox()
        layout = QtWidgets.QFormLayout()
        layout.addRow('Refresh interval (s)', self.spin)
        self.setLayout(layout)

        self.spin.valueChanged.connect(self.spinValueChanged)

    @Slot(int)
    def spinValueChanged(self, val):
        self.intervalChanged.emit(val)


class PlotWindow(QtWidgets.QMainWindow):
    """
    Simple MainWindow class for embedding flowcharts and plots.

    All keyword arguments supplied will be propagated to
    :meth:`addNodeWidgetFromFlowchart`.
    """

    plotWidgetClass = MPLAutoPlot

    def __init__(self, parent=None, fc: Flowchart = None, **kw):
        super().__init__(parent)

        self.plot = PlotWidgetContainer(parent=self)
        self.setCentralWidget(self.plot)
        self.plotWidget: Optional[MPLAutoPlot] = None

        self.nodeToolBar = QtWidgets.QToolBar('Node control', self)
        self.addToolBar(self.nodeToolBar)

        self.nodeWidgets: Dict[str, QtWidgets.QDockWidget] = {}
        if fc is not None:
            self.addNodeWidgetsFromFlowchart(fc, **kw)

        self.setDefaultStyle()

    def setDefaultStyle(self):
        self.setStyleSheet(
            """
            QToolButton {
                font: 10px;
            }

            QToolBar QCheckBox {
                font: 10px;
            }
            """
        )

    def addNodeWidget(self, node: Node, **kwargs):
        """
        Add a node widget as dock.

        :param node: node for which to add the widget.

        :keyword arguments:
            * *visible* (`bool`; default: taken from widget class definition) --
              whether the widget is visible from the start
            * *dockArea* (`QtCore.Qt.DockWidgetArea`; default: taken from class) --
              where the dock widget initially sits in the window
            * *icon* (`QtCore.QIcon`; default: taken from class) --
              an icon to use for the toolbar
        """

        if node.useUi and node.ui is not None and node.uiClass is not None:
            dockArea = kwargs.get('dockArea', node.ui.preferredDockWidgetArea)
            visible = kwargs.get('visible', node.uiVisibleByDefault)
            icon = kwargs.get('icon', node.ui.icon)

            d = QtWidgets.QDockWidget(node.name(), self)
            d.setWidget(node.ui)
            self.nodeWidgets[node.name()] = d
            self.addDockWidget(dockArea, d)

            action = d.toggleViewAction()
            if icon is not None:
                action.setIcon(icon)
            self.nodeToolBar.addAction(action)

            if not visible:
                d.close()

    def addNodeWidgetsFromFlowchart(self, fc: Flowchart,
                                    exclude: Sequence[str] = (),
                                    plotNode: str = 'plot',
                                    makePlotWidget: bool = True,
                                    **kwargs):
        """
        Add all nodes for a flowchart, excluding nodes given in `exclude`.

        :param fc: flowchart object
        :param exclude: list of node names. 'Input' and 'Output' are
                        automatically appended.
        :param plotNode: specify the name of the plot node, if present
        :param makePlotWidget: if True, attach a MPL autoplot widget to the plot
                               node.
        :param kwargs: see below.

        :keyword arguments:
            * *widgetOptions* (`dictionary`) --
              each entry in the dictionary should have the form
              { nodeName : { option : value, ...}, ... }.
              the options will be passed to :meth:`addNodeWidget` as keyword
              arguments.
        """
        exclude = tuple(exclude) + ('Input', 'Output')

        opts = kwargs.get('widgetOptions', dict())

        for nodeName, node in fc.nodes().items():
            if nodeName not in exclude:
                thisOpts = opts.get(nodeName, dict())
                self.addNodeWidget(node, **thisOpts)

            if nodeName == plotNode and makePlotWidget:
                pn = fc.nodes().get(plotNode, None)
                if pn is not None and isinstance(pn, PlotNode):
                    pn.setPlotWidgetContainer(self.plot)
                    self.plotWidget = self.plotWidgetClass(parent=self.plot)
                    self.plot.setPlotWidget(self.plotWidget)


def makeFlowchartWithPlotWindow(nodes: List[Tuple[str, Type[Node]]], **kwargs) \
        -> Tuple[PlotWindow, Flowchart]:
    nodes.append(('plot', PlotNode))
    fc = linearFlowchart(*nodes)
    win = PlotWindow(fc=fc, plotNode='plot', **kwargs)
    return win, fc


class SnapshotWidget(QtWidgets.QTreeWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setHeaderLabels(['Key', 'Value'])
        self.setColumnCount(2)

    def loadSnapshot(self, snapshotDict : Optional[dict]):
        """
        Loads a qcodes DataSet snapshot in the tree view
        """
        self.clear()

        if snapshotDict is None:
            return

        items = dictToTreeWidgetItems(snapshotDict)
        for item in items:
            self.addTopLevelItem(item)
            item.setExpanded(True)

        #self.expandAll()
        for i in range(2):
            self.resizeColumnToContents(i)

