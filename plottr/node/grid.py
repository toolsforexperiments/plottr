"""
grid.py

A node and widget for placing data onto a grid (or not).
"""

from enum import Enum, unique

from typing import Tuple, Dict, Any

from plottr import QtCore, QtGui
from .node import Node, NodeWidget, updateOption, updateGuiFromNode
from ..data import datadict as dd
from ..data.datadict import DataDict, MeshgridDataDict

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


@unique
class GridOption(Enum):
    noGrid = 0
    guessShape = 1
    specifyShape = 2


class ShapeSpecificationWidget(QtGui.QWidget):
    #: signal that is emitted when we want to communicate a new shape
    newShapeNotification = QtCore.pyqtSignal(tuple)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._axes = []
        self._widgets = {}

        self.layout = QtGui.QFormLayout()
        self.confirm = QtGui.QPushButton('set')
        self.layout.addRow(self.confirm)
        self.setLayout(self.layout)

        self.confirm.clicked.connect(self.signalShape)

    def signalShape(self):
        self.newShapeNotification.emit(self.getShape())

    def setAxes(self, axes):
        if axes != self._axes:
            self._axes = axes
            self._widgets = {}
            for i in range(self.layout.rowCount() - 1):
                self.layout.removeRow(0)

            for i, ax in enumerate(axes):
                w = QtGui.QSpinBox()
                w.setMinimum(1)
                w.setMaximum(999999)
                self._widgets[ax] = w
                self.layout.insertRow(i, ax, w)

    def setShape(self, shape):
        if shape == tuple():
            shape = [0 for ax in self._axes]
        for s, ax in zip(shape, self._axes):
            self._widgets[ax].setValue(s)

    def getShape(self):
        return tuple(self._widgets[ax].value() for ax in self._axes)

    def enableEditing(self, enable):
        for ax, w in self._widgets.items():
            w.setEnabled(enable)
        self.confirm.setEnabled(enable)


class GridOptionWidget(QtGui.QWidget):
    optionSelected = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._emitUpdate = True

        #  make radio buttons and layout ##
        self.buttons = {
            GridOption.noGrid: QtGui.QRadioButton('No grid'),
            GridOption.guessShape: QtGui.QRadioButton('Guess shape'),
            GridOption.specifyShape: QtGui.QRadioButton('Specify shape'),
        }

        btnLayout = QtGui.QVBoxLayout()
        self.btnGroup = QtGui.QButtonGroup(self)

        for opt in GridOption:
            btn = self.buttons[opt]
            self.btnGroup.addButton(btn, opt.value)
            btnLayout.addWidget(btn)

        btnBox = QtGui.QGroupBox('Grid')
        btnBox.setLayout(btnLayout)

        # make shape spec widget
        self.shapeSpec = ShapeSpecificationWidget()
        shapeLayout = QtGui.QVBoxLayout()
        shapeLayout.addWidget(self.shapeSpec)
        shapeBox = QtGui.QGroupBox('Shape')
        shapeBox.setLayout(shapeLayout)

        # Widget layout
        layout = QtGui.QHBoxLayout()
        layout.addWidget(btnBox)
        layout.addWidget(shapeBox)
        layout.addStretch()
        self.setLayout(layout)

        # Connect signals/slots #
        self.btnGroup.buttonToggled.connect(self.gridButtonSelected)
        self.shapeSpec.confirm.clicked.connect(self.shapeSpecified)

        # Default settings
        self.buttons[GridOption.noGrid].setChecked(True)
        self.enableShapeEdit(False)

    def getGrid(self):
        activeBtn = self.btnGroup.checkedButton()
        activeId = self.btnGroup.id(activeBtn)
        opts = {}

        if GridOption(activeId) == GridOption.specifyShape:
            opts['shape'] = self.shapeSpec.getShape()

        return GridOption(activeId), opts

    def setGrid(self, grid):
        # This function should not trigger an emission for an update.
        # We only want that when the user sets the grid in the UI,
        # to avoid recursive calls
        self._emitUpdate = False

        method, opts = grid
        for k, btn in self.buttons.items():
            if k == method:
                btn.setChecked(True)

        if method == GridOption.specifyShape:
            self.setShape(opts['shape'])

    @QtCore.pyqtSlot(QtGui.QAbstractButton, bool)
    def gridButtonSelected(self, btn, checked):
        if checked:

            # only emit the signal when the update is from the UI
            if self._emitUpdate:
                self.signalGridOption(self.getGrid())

            if GridOption(self.btnGroup.id(btn)) == GridOption.specifyShape:
                self.enableShapeEdit(True)
            else:
                self.enableShapeEdit(False)

            self._emitUpdate = True

    @QtCore.pyqtSlot()
    def shapeSpecified(self):
        self.signalGridOption(self.getGrid())

    def signalGridOption(self, grid):
        self.optionSelected.emit(grid)

    def setAxes(self, axes):
        self.shapeSpec.setAxes(axes)
        if self.getGrid()[0] == GridOption.specifyShape:
            self.enableShapeEdit(True)
        else:
            self.enableShapeEdit(False)

    def setShape(self, shape):
        self.shapeSpec.setShape(shape)

    def enableShapeEdit(self, enable):
        self.shapeSpec.enableEditing(enable)


class DataGridderNodeWidget(NodeWidget):

    def __init__(self, node: Node = None):
        super().__init__(embedWidgetClass=GridOptionWidget)

        self.optSetters = {
            'grid': self.setGrid,
        }
        self.optGetters = {
            'grid': self.getGrid,
        }
        self.widget.optionSelected.connect(
            lambda x: self.signalOption('grid')
        )

    def getGrid(self):
        return self.widget.getGrid()

    def setGrid(self, grid):
        self.widget.setGrid(grid)

    @updateGuiFromNode
    def setAxes(self, axes):
        self.widget.setAxes(axes)

    @updateGuiFromNode
    def setShape(self, shape):
        self.widget.setShape(shape)


class DataGridder(Node):
    """
    A node that can put data onto or off a grid.
    Has one property: grid. That can have the following values:
    * ...
    """

    nodeName = "Gridder"
    uiClass = DataGridderNodeWidget

    shapeDetermined = QtCore.pyqtSignal(tuple)
    axesList = QtCore.pyqtSignal(list)

    def __init__(self, *arg, **kw):

        self._grid = GridOption.noGrid, {}
        self._shape = None
        self._invalid = False

        super().__init__(*arg, **kw)

    # Properties

    @property
    def grid(self):
        return self._grid

    @grid.setter
    @updateOption('grid')
    def grid(self, val: Tuple[GridOption, Dict[str, Any]]):
        try:
            method, opts = val
        except TypeError:
            raise ValueError(f"Invalid grid specification.")

        if not method in GridOption:
            raise ValueError(f"Invalid grid method specification.")

        if not isinstance(opts, dict):
            raise ValueError(f"Invalid grid options specification.")

        self._grid = val

    # Processing

    def validateOptions(self, data: Any):
        if not super().validateOptions(data):
            return False

        return True

    def process(self, **kw):
        data = kw['dataIn']
        if data is None:
            return None

        data = super().process(**kw)
        if data is None:
            return None
        data = data['dataOut'].copy()
        self.axesList.emit(data.axes())

        dout = None
        method, opts = self._grid

        if isinstance(data, DataDict):
            if method is GridOption.noGrid:
                dout = data.expand()
            elif method is GridOption.guessShape:
                dout = dd.datadict_to_meshgrid(data)
            elif method is GridOption.specifyShape:
                dout = dd.datadict_to_meshgrid(data, target_shape=opts['shape'])

        elif isinstance(data, MeshgridDataDict):
            if method is GridOption.noGrid:
                dout = dd.meshgrid_to_datadict(data)
            elif method is GridOption.guessShape:
                dout = data
            elif method is GridOption.specifyShape:
                self.logger().warning(
                    f"Data is already on grid. Ignore shape.")
                dout = data

        else:
            self.logger().error(
                f"Unknown data type {type(data)}.")
            return None

        if dout is None:
            return None

        if hasattr(dout, 'shape'):
            self.shapeDetermined.emit(dout.shape())
        else:
            self.shapeDetermined.emit(tuple())

        return dict(dataOut=dout)

    ### Setup UI

    def setupUi(self):
        super().setupUi()
        self.axesList.connect(self.ui.setAxes)
        self.shapeDetermined.connect(self.ui.setShape)
