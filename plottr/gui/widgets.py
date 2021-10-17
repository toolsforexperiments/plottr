"""
widgets.py

Common GUI widgets that are re-used across plottr.
"""
from numpy import rint
from typing import Union, List, Tuple, Optional, Type, Sequence, Dict, Any, Type

from .tools import dictToTreeWidgetItems, dpiScalingFactor
from plottr import QtGui, QtCore, Flowchart, QtWidgets, Signal, Slot
from plottr.node import Node, linearFlowchart, NodeWidget, updateOption
from plottr.node.node import updateGuiQuietly, emitGuiUpdate
from ..plot import PlotNode, PlotWidgetContainer, PlotWidget
from .. import config_entry as getcfg

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

    It's signal `intervalChanged(float)' is emitted when the value
    of the spinbox has changed.
    """

    intervalChanged = Signal(float)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        self.spin = QtWidgets.QDoubleSpinBox()
        self.spin.setSingleStep(0.1)
        self.spin.setDecimals(1)

        layout = QtWidgets.QFormLayout()
        layout.addRow('Refresh interval (s)', self.spin)
        self.setLayout(layout)

        self.spin.valueChanged.connect(self.spinValueChanged)

    @Slot(float)
    def spinValueChanged(self, val: float) -> None:
        self.intervalChanged.emit(val)


class PlotWindow(QtWidgets.QMainWindow):
    """
    Simple MainWindow class for embedding flowcharts and plots, based on
    ``QtWidgets.QMainWindow``.
    """

    #: Signal() -- emitted when the window is closed
    windowClosed = Signal()

    def __init__(self, parent: Optional[QtWidgets.QMainWindow] = None,
                 fc: Optional[Flowchart] = None,
                 plotWidgetClass: Optional[Type[PlotWidget]] = None,
                 **kw: Any):
        """
        Constructor for :class:`.PlotWindow`.

        :param parent: parent widget
        :param fc: flowchart with nodes. if given, we will generate node widgets
            in this window.
        :param plotWidgetClass: class of the plot widget to use.
            defaults to :class:`plottr.plot.mpl.AutoPlot`.
        :param kw: any keywords will be propagated to
            :meth:`addNodeWidgetFromFlowchart`.
        """
        super().__init__(parent)

        if plotWidgetClass is None:
            plotWidgetClass = getcfg('main', 'default-plotwidget')

        if plotWidgetClass is None:
            raise RuntimeError("No PlotWidget has been specified.")

        self.plotWidgetClass = plotWidgetClass
        self.plot = PlotWidgetContainer(parent=self)
        self.setCentralWidget(self.plot)
        self.plotWidget: Optional[PlotWidget] = None

        self.nodeToolBar = QtWidgets.QToolBar('Node control', self)
        self.addToolBar(self.nodeToolBar)

        self.nodeWidgets: Dict[str, QtWidgets.QDockWidget] = {}
        if fc is not None:
            self.addNodeWidgetsFromFlowchart(fc, **kw)

        self.setDefaultStyle()

    def setDefaultStyle(self) -> None:
        fontSize = 10*dpiScalingFactor(self)
        self.setStyleSheet(
            f"""
            QToolButton {{
                font: {fontSize}px;
            }}

            QToolBar QCheckBox {{
                font: {fontSize}px;
            }}
            """
        )

    def addNodeWidget(self, node: Node, **kwargs: Any) -> None:
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
                                    **kwargs: Any) -> None:
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

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """
        When closing the inspectr window, do some house keeping:
        * stop the monitor, if running
        """
        self.windowClosed.emit()
        return event.accept()


def makeFlowchartWithPlotWindow(nodes: List[Tuple[str, Type[Node]]], **kwargs: Any) \
        -> Tuple[PlotWindow, Flowchart]:
    nodes.append(('plot', PlotNode))
    fc = linearFlowchart(*nodes)
    win = PlotWindow(fc=fc, plotNode='plot', **kwargs)
    return win, fc


class SnapshotWidget(QtWidgets.QTreeWidget):

    def __init__(self, parent: Optional[QtWidgets.QTreeWidget] = None):
        super().__init__(parent)

        self.setHeaderLabels(['Key', 'Value'])
        self.setColumnCount(2)

    def loadSnapshot(self, snapshotDict : Optional[dict]) -> None:
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

        for i in range(2):
            self.resizeColumnToContents(i)


def setHExpanding(w: QtWidgets.QWidget) -> None:
    """Set the size policy of a widget such that is expands horizontally."""
    p = w.sizePolicy()
    p.setHorizontalPolicy(QtWidgets.QSizePolicy.MinimumExpanding)
    p.setHorizontalStretch(1)
    w.setSizePolicy(p)


def setVExpanding(w: QtWidgets.QWidget) -> None:
    """Set the size policy of a widget such that is expands vertically."""
    p = w.sizePolicy()
    p.setVerticalPolicy(QtWidgets.QSizePolicy.MinimumExpanding)
    p.setVerticalStretch(1)
    w.setSizePolicy(p)


class Collapsible(QtWidgets.QWidget):
    """A wrapper that allow collapsing a widget."""

    def __init__(self, widget: QtWidgets.QWidget, title: str = '',
                 parent: Optional[QtWidgets.QWidget] = None,
                 expanding: bool = True) -> None:
        """Constructor.

        :param widget: the widget we'd like to collapse.
        :param title: title of the widget. will appear on the toolbutton that
            we use to trigger collapse/expansion.
        :param parent: parent widget.
        """
        super().__init__(parent=parent)

        self.widget = widget
        self.widget.setParent(self)
        if expanding:
            setVExpanding(self.widget)

        self.expandedTitle = "[-] " + title
        self.collapsedTitle = "[+] " + title

        self.btn = QtWidgets.QPushButton(self.expandedTitle, parent=self)
        self.btn.setStyleSheet("""background: white; 
                                  color: black; 
                                  border: 2px solid white;
                                  text-align: left;""")
        self.btn.setFlat(True)
        self.btn.setCheckable(True)
        self.btn.setChecked(True)
        setHExpanding(self.btn)
        self.btn.clicked.connect(self._onButton)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.btn)
        layout.addWidget(self.widget)

    def _onButton(self) -> None:
        if self.btn.isChecked():
            self.widget.setVisible(True)
            self.btn.setText(self.expandedTitle)
        else:
            self.widget.setVisible(False)
            self.btn.setText(self.collapsedTitle)


class DimensionCombo(QtWidgets.QComboBox):
    """A Combo Box that allows selection of a single data dimension.
    This widget is designed to be used in a node widget.

    Which type of dimensions are available for selection is set through the
    ``dimensionType`` option when creating the instance.

    The widget can be linked to a node using the :meth:`.connectNode` method.
    After linking, the available options will be populated whenever the data in
    the node changes.
    """

    #: Signal(str)
    #: emitted when the user selects a dimension.
    dimensionSelected = Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None,
                 dimensionType: str = 'axes') -> None:
        """Constructor.

        :param parent: parent widget
        :param dimensionType: one of `axes`, `dependents` or `all`.
        """
        super().__init__(parent)

        self.node: Optional[Node] = None
        self.dimensionType = dimensionType

        self.clear()
        self.entries = ['None']
        for e in self.entries:
            self.addItem(e)

        self.currentTextChanged.connect(self.signalDimensionSelection)

    def connectNode(self, node: Optional[Node] = None) -> None:
        """Connect a node. will result in populating the combo box options
        based on dimensions available in the node data.

        :param node: instance of :class:`.Node`
        """
        if node is None:
            raise RuntimeError
        self.node = node
        if self.dimensionType == 'axes':
            self.node.dataAxesChanged.connect(self.setDimensions)
        elif self.dimensionType == 'dependents':
            self.node.dataDependentsChanged.connect(self.setDimensions)
        else:
            self.node.dataFieldsChanged.connect(self.setDimensions)

    @updateGuiQuietly
    def setDimensions(self, dims: Sequence[str]) -> None:
        """Set the dimensions that are available for selection.

        :param dims: list of dimensions, as strings.
        :return: ``None``
        """
        self.clear()
        allDims = self.entries + list(dims)
        for d in allDims:
            self.addItem(d)

    @Slot(str)
    @emitGuiUpdate('dimensionSelected')
    def signalDimensionSelection(self, val: str) -> str:
        return val


class DimensionSelector(FormLayoutWrapper):
    """A widget that allows the user to select a dimension from a dataset
    via a combobox.

    Contains a label and a :class:`.DimensionCombo`."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(
            parent=parent,
            elements=[('Dimension', DimensionCombo(dimensionType='all'))],
        )
        self.combo = self.elements['Dimension']


class DependentSelector(FormLayoutWrapper):
    """A widget that allows the user to select a dependent dimension from a dataset
    via a combobox.

    Contains a label and a :class:`.DimensionCombo`."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(
            parent=parent,
            elements=[('Dependent', DimensionCombo(dimensionType='dependents'))],
        )
        self.combo = self.elements['Dependent']


class AxisSelector(FormLayoutWrapper):
    """A widget that allows the user to select an axis dimension from a dataset
    via a combobox.

    Contains a label and a :class:`.DimensionCombo`."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(
            parent=parent,
            elements=[('Axis', DimensionCombo(dimensionType='axes'))],
        )
        self.combo = self.elements['Axis']


class MultiDimensionSelector(QtWidgets.QListWidget):
    """A simple list widget that allows selection of multiple data dimensions."""

    #: signal (List[str]) that is emitted when the selection is modified.
    dimensionSelectionMade = Signal(list)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None,
                 dimensionType: str = 'all') -> None:
        """Constructor.

        :param parent: parent widget.
        :param dimensionType: one of ``all``, ``axes``, or ``dependents``.
        """
        super().__init__(parent)

        self.node: Optional[Node] = None
        self.dimensionType = dimensionType

        self.setSelectionMode(self.MultiSelection)
        self.itemSelectionChanged.connect(self.emitSelection)

    def setDimensions(self, dimensions: List[str]) -> None:
        """set the available dimensions.

        :param dimensions: list of dimension names.
        """
        self.clear()
        self.addItems(dimensions)

    def getSelected(self) -> List[str]:
        """Get selected dimensions.

        :return: List of dimensions (as strings).
        """
        selectedItems = self.selectedItems()
        return [s.text() for s in selectedItems]

    def setSelected(self, selected: List[str]) -> None:
        """Set dimension selection.

        :param selected: List of dimensions to be selected.
        """
        for i in range(self.count()):
            item = self.item(i)
            if item.text() in selected:
                item.setSelected(True)
            else:
                item.setSelected(False)

    def emitSelection(self) -> None:
        self.dimensionSelectionMade.emit(self.getSelected())

    def connectNode(self, node: Optional[Node] = None) -> None:
        """Connect a node. Will result in populating the available options
        based on dimensions available in the node data.

        :param node: instance of :class:`.Node`
        """
        if node is None:
            raise RuntimeError
        self.node = node
        if self.dimensionType == 'axes':
            self.node.dataAxesChanged.connect(self.setDimensions)
        elif self.dimensionType == 'dependents':
            self.node.dataDependentsChanged.connect(self.setDimensions)
        else:
            self.node.dataFieldsChanged.connect(self.setDimensions)
