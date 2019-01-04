"""
grid.py

A node and widget for placing data onto a grid (or not).
"""

from pprint import pprint
import copy
from functools import wraps

import numpy as np

from pyqtgraph import Qt
from pyqtgraph.Qt import QtGui, QtCore

from .node import Node
from ..data import datadict as dd
from ..data.datadict import DataDict, MeshgridDataDict

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


# TODO: we probably should use Enums here instead of these options...

class ShapeSpecification(QtGui.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self._axes = []
        self._widgets = {}

        self.layout = QtGui.QFormLayout()
        self.confirm = QtGui.QPushButton('set')
        self.layout.addRow(self.confirm)
        self.setLayout(self.layout)

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


class DataGridderWidget(QtGui.QWidget):

    NOGRID = 1
    GUESSSHAPE = 2
    SPECIFYSHAPE = 3
    FINDGRID = 4

    optionSelected = QtCore.pyqtSignal(object)

    ## Decorators for GUI/Node communication ##
    # TODO: those should eventually go into the Node base class

    def updateGuiFromNode(func):
        # @wraps(func)
        def wrap(self, *arg, **kw):
            self._emitGuiChange = False
            ret = func(self, *arg, **kw)
            self._emitGuiChange = True
            return ret
        return wrap

    def emitGuiUpdate(signalName):
        def decorator(func):
            # @wraps(func)
            def wrap(self, *arg, **kw):
                ret = func(self, *arg, **kw)
                if self._emitGuiChange:
                    sig = getattr(self, signalName)
                    sig.emit(ret)
            return wrap
        return decorator


    def __init__(self, parent=None):
        super().__init__(parent)

        self._emitGuiChange = True

        ##  make radio buttons and layout ##
        self.buttons = {
            self.NOGRID : QtGui.QRadioButton('No grid'),
            self.GUESSSHAPE : QtGui.QRadioButton('Guess shape'),
            self.SPECIFYSHAPE : QtGui.QRadioButton('Specify shape'),
        }

        btnLayout = QtGui.QVBoxLayout()
        self.btnGroup = QtGui.QButtonGroup(self)

        for i in [self.NOGRID, self.GUESSSHAPE, self.SPECIFYSHAPE]:
            btn = self.buttons[i]
            self.btnGroup.addButton(btn, i)
            btnLayout.addWidget(btn)

        btnBox = QtGui.QGroupBox('Grid')
        btnBox.setLayout(btnLayout)

        ## make shape spec widget ##
        self.shapeSpec = ShapeSpecification()
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

        ## Connect signals/slots ##
        self.btnGroup.buttonToggled.connect(self.gridButtonSelected)
        self.shapeSpec.confirm.clicked.connect(self.shapeSpecified)

    def getGrid(self):
        activeBtn = self.btnGroup.checkedButton()
        activeId = self.btnGroup.id(activeBtn)
        if activeId == self.GUESSSHAPE:
            return 'guess'
        elif activeId == self.SPECIFYSHAPE:
            return self.shapeSpec.getShape()
        elif activeId == self.NOGRID:
            return False
        else:
            return None

    @QtCore.pyqtSlot(QtGui.QAbstractButton, bool)
    def gridButtonSelected(self, btn, checked):
        if checked:
            self.signalGridOption(self.getGrid())

    @QtCore.pyqtSlot()
    def shapeSpecified(self):
        shape = self.shapeSpec.getShape()
        self.signalGridOption(shape)

    @emitGuiUpdate('optionSelected')
    def signalGridOption(self, grid):
        return grid

    ## methods for setting from the node ##
    @updateGuiFromNode
    def setGrid(self, val):
        if isinstance(val, tuple):
            self.setShape(val)
            self.shapeSpec.enableEditing(True)
            self.buttons[self.SPECIFYSHAPE].setChecked(True)
        else:
            self.shapeSpec.enableEditing(False)

        if val == 'guess':
            self.buttons[self.GUESSSHAPE].setChecked(True)

        if val == False:
            self.buttons[self.NOGRID].setChecked(True)

    @QtCore.pyqtSlot(list)
    @updateGuiFromNode
    def setAxes(self, axes):
        self.shapeSpec.setAxes(axes)
        self.setGrid(self.getGrid())

    @QtCore.pyqtSlot(tuple)
    @updateGuiFromNode
    def setShape(self, shape):
        self.shapeSpec.setShape(shape)


class DataGridder(Node):
    """
    A node that can put data onto or off a grid.
    Has one property: grid. That can have the following values:
    * ...
    """

    nodeName = "Gridder"
    uiClass = DataGridderWidget

    guiOptions = {
        'grid' : {
            'widget' : None,
            'setFunc' : 'setGrid',
        }
    }

    shapeDetermined = QtCore.pyqtSignal(tuple)
    axesList = QtCore.pyqtSignal(list)

    def __init__(self, *arg, **kw):

        self._grid = None
        self._shape = None
        self._invalid = False

        super().__init__(*arg, **kw)

        if self.ui is not None:
            self.axesList.connect(self.ui.setAxes)
            self.shapeDetermined.connect(self.ui.setShape)


    ### Properties
    @property
    def grid(self):
        return self._grid

    @grid.setter
    @Node.updateOption('grid')
    def grid(self, val):
        self._invalid = False
        if isinstance(val, tuple):
            try:
                self._grid = tuple(int(s) for s in val)
            except ValueError:
                self._invalid = True
                self.logger().error(f"Invalid grid option {val}")
                raise

        elif val in [None, False, 'guess']:
            self._grid = val

        else:
            self._invalid = True
            self.logger().error(f"Invalid grid option {val}")


    ### Processing
    def process(self, **kw):
        data = super().process(**kw)
        if data is None:
            return None

        data = data['dataOut']
        if self.ui is not None:
            self.updateUiDataIn(data)

        dout = None
        shape = tuple()

        if self._invalid:
            return None

        if self._grid is None:
            if isinstance(data, MeshgridDataDict):
                shape = data.shape
            dout = data

        elif self._grid is False and isinstance(data, DataDict):
            dout = data

        elif self._grid is False and isinstance(data, MeshgridDataDict):
            dout = dd.meshgrid_to_datadict(data)

        elif self._grid == 'guess' and isinstance(data, DataDict):
            dout = dd.datadict_to_meshgrid(data)
            shape = dout.shape

        elif self._grid == 'guess' and isinstance(data, MeshgridDataDict):
            shape = data.shape
            dout = data

        elif isinstance(self._grid, tuple):
            shape = self._grid
            dout = dd.datadict_to_meshgrid(data, target_shape=self._grid)

        else:
            self.logger().error(f"Unknown grid option {self._grid}. Most likely a bug :/")
            return None

        if dout is None:
            return None

        if self.ui is not None:
            self.updateUiDataOut(dout)

        return dict(dataOut=dout)

    ### Setup UI

    def setupUi(self):
        self.ui.setGrid(self._grid)
        self.ui.optionSelected.connect(self._setGrid)

    def updateUiDataOut(self, data):
        if isinstance(data, MeshgridDataDict):
            shape = data.shape()
        else:
            shape = tuple()
        self.shapeDetermined.emit(shape)

    def updateUiDataIn(self, data):
        axes = data.axes()
        self.axesList.emit(axes)

    ### Receiving UI changes
    @QtCore.pyqtSlot(object)
    def _setGrid(self, val):
        self.grid = val
