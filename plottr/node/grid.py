"""
grid.py

A node and widget for placing data onto a grid (or not).
"""

from pprint import pprint
import copy

import numpy as np

from pyqtgraph import Qt
from pyqtgraph.Qt import QtGui, QtCore

from .node import Node
from ..data import datadict as dd
from ..data.datadict import DataDict, MeshgridDataDict

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


class ShapeSpecification(QtGui.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)




class DataGridderWidget(QtGui.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.buttons = [
            QtGui.QRadioButton('No grid'),
            QtGui.QRadioButton('Guess shape'),
            QtGui.QRadioButton('Specify shape'),
        ]

        layout = QtGui.QVBoxLayout()
        self.btnGroup = QtGui.QButtonGroup(self)

        for btn in self.buttons:
            self.btnGroup.addButton(btn)
            layout.addWidget(btn)

        layout.addStretch()
        self.setLayout(layout)

        self.btnGroup.buttonToggled.connect(self.printToggle)


    @QtCore.pyqtSlot(QtGui.QAbstractButton, bool)
    def printToggle(self, btn, checked):
        if checked:
            print(btn.text())




class DataGridder(Node):
    """
    A node that can put data onto or off a grid.
    Has one property: grid. That can have the following values:
    * ...
    """

    nodeName = "Gridder"
    uiClass = DataGridderWidget

    guiOptions = {

    }

    shapeDetermined = QtCore.pyqtSignal(tuple)

    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)

        self._grid = None
        self._shape = None
        self._invalid = False

        self.shapeDetermined.connect(self.printShape)

    @QtCore.pyqtSlot(tuple)
    def printShape(self, shape):
        print('got the shape:', shape)

    ### Properties
    @property
    def grid(self):
        return self._grid

    @grid.setter
    @Node.updateOption()
    def grid(self, val):

        self._invalid = False
        if isinstance(val, tuple):
            try:
                self._grid = tuple(int(s) for s in val)
            except ValueError:
                self._invalid = True
                self.logger().error(f"Invalid grid option {val}")

        elif val in [None, False, 'guess']:
            self._grid = val

        else:
            self._invalid = True
            self.logger().error(f"Invalid grid option {val}")

    ### Processing
    def process(self, **kw):
        data = kw['dataIn']

        if self._invalid:
            return None

        if self._grid is None:
            if isinstance(data, MeshgridDataDict):
                self.shapeDetermined.emit(data.shape())
            else:
                self.shapeDetermined.emit(tuple())
            return dict(dataOut=data)

        elif self._grid is False and isinstance(data, DataDict):
            self.shapeDetermined.emit(tuple())
            return dict(dataOut=data)

        elif self._grid is False and isinstance(data, MeshgridDataDict):
            self.shapeDetermined.emit(tuple())
            return dict(dataOut=dd.meshgrid_to_datadict(data))

        elif self._grid == 'guess' and isinstance(data, DataDict):
            dout = dd.datadict_to_meshgrid(data)
            self.shapeDetermined.emit(dout.shape())
            return dict(dataOut=dout)

        elif self._grid == 'guess' and isinstance(data, MeshgridDataDict):
            self.shapeDetermined.emit(data.shape())
            return dict(dataOut=data)

        elif isinstance(self._grid, tuple):
            self.shapeDetermined.emit(self._grid)
            return dict(dataOut=dd.datadict_to_meshgrid(data, target_shape=self._grid))

        else:
            self.logger().error(f"Unknown grid option {self._grid}. Most likely a bug :/")
            return None
