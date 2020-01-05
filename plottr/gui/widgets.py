"""
widgets.py

Common GUI widgets that are re-used across plottr.
"""

from typing import Union, List, Tuple

from plottr import QtGui, QtCore, Flowchart
from plottr.node import Node
from plottr.plot.mpl import PlotNode, AutoPlot

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


class FormLayoutWrapper(QtGui.QWidget):
    """
    Simple wrapper widget for forms.
    Expects a list of tuples of the form (label, widget),
    creates a widget that contains these using a form layout.
    Labels have to be unique.
    """

    def __init__(self, elements: List[Tuple[str, QtGui.QWidget]],
                 parent: Union[None, QtGui.QWidget] = None):
        super().__init__(parent)

        self.elements = {}

        layout = QtGui.QFormLayout()
        for lbl, widget in elements:
            self.elements[lbl] = widget
            layout.addRow(lbl, widget)

        self.setLayout(layout)


class MonitorIntervalInput(QtGui.QWidget):
    """
    Simple form-like widget for entering a monitor/refresh interval.
    Only has a label and a spin-box as input.

    It's signal `intervalChanged(int)' is emitted when the value
    of the spinbox has changed.
    """

    intervalChanged = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.spin = QtGui.QSpinBox()
        layout = QtGui.QFormLayout()
        layout.addRow('Refresh interval (s)', self.spin)
        self.setLayout(layout)

        self.spin.valueChanged.connect(self.spinValueChanged)

    @QtCore.pyqtSlot(int)
    def spinValueChanged(self, val):
        self.intervalChanged.emit(val)


class PlotWindow(QtGui.QMainWindow):
    """
    Simple MainWindow class for embedding flowcharts and plots.
    """

    def __init__(self, parent=None, fc: Flowchart = None, **kw):
        super().__init__(parent)

        self.nodeWidgets = {}
        self.plotWidget = None

        if fc is not None:
            self.addNodeWidgetsFromFlowchart(fc, **kw)

        self.setDefaultStyle()

    def addNodeWidget(self, node: Node):
        """
        Add a node widget as dock.

        :param node: node for which to add the widget.
        :return:
        """
        if node.useUi and node.uiClass is not None:
            d = QtGui.QDockWidget(node.name(), self)
            d.setWidget(node.ui)
            self.nodeWidgets[node.name()] = d
            self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, d)

    def addNodeWidgetsFromFlowchart(self, fc: Flowchart,
                                    exclude: List[str] = [],
                                    plotNode: str = 'plot',
                                    makePlotWidget: bool = True):
        """
        Add all nodes for a flowchart, excluding nodes given in `exclude`.

        :param fc: flowchart object
        :param exclude: list of node names. 'Input' and 'Output' are
                        automatically appended.
        :param plotNode: specify the name of the plot node, if present
        :param makePlotWidget: if True, attach a MPL autoplot widget to the plot
                               node.
        :return:
        """
        exclude += ['Input', 'Output']

        for nodeName, node in fc.nodes().items():
            if nodeName not in exclude:
                self.addNodeWidget(node)

            if nodeName == plotNode and makePlotWidget:
                pn = fc.nodes().get(plotNode, None)
                if pn is not None and isinstance(pn, PlotNode):
                    self.plotWidget = AutoPlot()
                    pn.setPlotWidget(self.plotWidget)
                    self.setCentralWidget(self.plotWidget)

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


class SnapshotWidget(QtGui.QTreeWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setHeaderLabels(['Key', 'Value'])
        self.setColumnCount(2)

    
    def loadSnapshot(self, snapshotDict : dict):
        """
        Loads a qcodes DataSet snapshot in the tree view
        """
        self.clear()
        items = dictToTreeWidgetItems(snapshotDict)
        for item in items:
            self.addTopLevelItem(item)
            item.setExpanded(True)

        #self.expandAll()
        for i in range(2):
            self.resizeColumnToContents(i)



def dictToTreeWidgetItems(d):
    items = []
    for k, v in d.items():
        if not isinstance(v, dict):
            item = QtGui.QTreeWidgetItem([str(k), str(v)])
        else:
            item = QtGui.QTreeWidgetItem([k, ''])
            for child in dictToTreeWidgetItems(v):
                item.addChild(child)
        items.append(item)
    return items