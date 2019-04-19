"""
grid.py

A node and widget for placing data onto a grid (or not).
"""

# from pprint import pprint
# import copy
# from functools import wraps

# import numpy as np

# from pyqtgraph import Qt
# from pyqtgraph.Qt import QtGui, QtCore

from typing import Tuple, Dict, Any
from enum import Enum, unique

from plottr import QtCore, QtGui
from .node import Node, updateOption, emitGuiUpdate, updateGuiFromNode
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

        self._emitGuiChange = True

        #  make radio buttons and layout ##
        self.buttons = {
            GridOption.noGrid : QtGui.QRadioButton('No grid'),
            GridOption.guessShape : QtGui.QRadioButton('Guess shape'),
            GridOption.specifyShape : QtGui.QRadioButton('Specify shape'),
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
#         self.shapeSpec.confirm.clicked.connect(self.shapeSpecified)

    def getGrid(self):
        activeBtn = self.btnGroup.checkedButton()
        activeId = self.btnGroup.id(activeBtn)
        opts = {}

        if GridOption(activeId) == GridOption.specifyShape:
            opts['shape'] = self.shapeSpec.getShape()

        return GridOption(activeId), opts

    @QtCore.pyqtSlot(QtGui.QAbstractButton, bool)
    def gridButtonSelected(self, btn, checked):
        if checked:
            self.signalGridOption(self.getGrid())
#
#     @QtCore.pyqtSlot()
#     def shapeSpecified(self):
#         shape = self.shapeSpec.getShape()
#         self.signalGridOption(shape)
#
    @emitGuiUpdate('optionSelected')
    def signalGridOption(self, grid):
        return grid
#
#     ## methods for setting from the node ##
#     @updateGuiFromNode
#     def setGrid(self, val):
#         if isinstance(val, tuple):
#             self.setShape(val)
#             self.shapeSpec.enableEditing(True)
#             self.buttons[self.SPECIFYSHAPE].setChecked(True)
#         else:
#             self.shapeSpec.enableEditing(False)
#
#         if val == 'guess':
#             self.buttons[self.GUESSSHAPE].setChecked(True)
#
#         if val == False:
#             self.buttons[self.NOGRID].setChecked(True)
#
#     @QtCore.pyqtSlot(list)
#     @updateGuiFromNode
#     def setAxes(self, axes):
#         self.shapeSpec.setAxes(axes)
#         self.setGrid(self.getGrid())
#
#     @QtCore.pyqtSlot(tuple)
#     @updateGuiFromNode
#     def setShape(self, shape):
#         self.shapeSpec.setShape(shape)


class DataGridder(Node):
    """
    A node that can put data onto or off a grid.
    Has one property: grid. That can have the following values:
    * ...
    """

    nodeName = "Gridder"
    uiClass = None # DataGridderWidget

    # shapeDetermined = QtCore.pyqtSignal(tuple)
    # axesList = QtCore.pyqtSignal(list)

    def __init__(self, *arg, **kw):

        self._grid = GridOption.noGrid, {}
        self._shape = None
        self._invalid = False

        super().__init__(*arg, **kw)

        # if self.ui is not None:
        #     self.axesList.connect(self.ui.setAxes)
        #     self.shapeDetermined.connect(self.ui.setShape)

    # Properties

    @property
    def grid(self):
        return self._grid

    @grid.setter
    @updateOption('grid')
    def grid(self, val: Tuple[GridOption, Dict[str, Any]]):
        self._grid = val

        # self._invalid = False
        # if isinstance(val, tuple):
        #     try:
        #         self._grid = tuple(int(s) for s in val)
        #     except ValueError:
        #         self._invalid = True
        #         self.logger().error(f"Invalid grid option {val}")
        #         raise
        #
        # elif val in [None, False, 'guess']:
        #     self._grid = val
        #
        # else:
        #     self._invalid = True
        #     self.logger().error(f"Invalid grid option {val}")

    # Processing

    def validateOptions(self, data: Any):
        if not super().validateOptions(data):
            return False

        try:
            method, opts = self._grid
        except TypeError:
            self.logger().error(f"Invalid grid specification.")
            return False

        if not method in GridOption:
            self.logger().error(f"Invalid grid method specification.")
            return False

        if not isinstance(opts, dict):
            self.logger().error(f"Invalid grid options specification.")
            return False

        return True

    def process(self, **kw):
        data = super().process(**kw)
        if data is None:
            return None
        data = data['dataOut']

        # if self.ui is not None:
        #     self.updateUiDataIn(data)

        dout = None
        method, opts = self._grid

        if isinstance(data, DataDict):
            if method is GridOption.noGrid:
                dout = data
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
        #
        # if self.ui is not None:
        #     self.updateUiDataOut(dout)

        return dict(dataOut=dout)

    ### Setup UI

    # def setupUi(self):
    #     self.ui.setGrid(self._grid)
    #     self.ui.optionSelected.connect(self._setGrid)
    #
    # def updateUiDataOut(self, data):
    #     if isinstance(data, MeshgridDataDict):
    #         shape = data.shape()
    #     else:
    #         shape = tuple()
    #     self.shapeDetermined.emit(shape)
    #
    # def updateUiDataIn(self, data):
    #     axes = data.axes()
    #     self.axesList.emit(axes)

    # ### Receiving UI changes
    # @QtCore.pyqtSlot(object)
    # def _setGrid(self, val):
    #     self.grid = val
