"""
node.py

Contains the base class for Nodes.
"""
import copy
from pprint import pprint

import numpy as np

from pyqtgraph.flowchart import Flowchart, Node as pgNode
from pyqtgraph.Qt import QtGui, QtCore

from ..data.datadict import togrid, DataDict, GridDataDict

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'

# things that I need to look at:
#
#

class Node(pgNode):

    optionChanged = QtCore.pyqtSignal(str, object)

    raiseExceptions = False
    nodeName = "DataDictNode"
    terminals = {
        'dataIn' : {'io' : 'in'},
        'dataOut' : {'io' : 'out'},
    }
    uiClass = None
    useUi = True
    debug = False

    guiOptions = {}

    def __init__(self, name):
        super().__init__(name, terminals=self.__class__.terminals)

        self.signalUpdate = True
        self._grid = False
        self._selectedData = None
        self.optionChanged.connect(self.processOptionUpdate)

        if self.useUi and self.__class__.uiClass is not None:
            self.ui = self.__class__.uiClass()
            self.setupUi()
        else:
            self.ui = None

    def setupUi(self):
        self.ui.debug = self.debug

    def ctrlWidget(self):
        return self.ui

    def updateOption(optName=None):
        def decorator(func):
            def wrap(self, val):
                ret = func(self, val)
                if optName is not None:
                    self.optionChanged.emit(optName, val)
                self.update(self.signalUpdate)
                return ret
            return wrap
        return decorator

    def processOptionUpdate(self, optName, value):
        if optName in self.guiOptions:
            if self.ui is not None:
                if self.guiOptions[optName]['widget'] is not None:
                    w = getattr(self.ui, self.guiOptions[optName]['widget'])
                    func = getattr(w, self.guiOptions[optName]['setFunc'])
                else:
                    func = getattr(self.ui, self.guiOptions[optName]['setFunc'])
                func(value)

    def update(self, signal=True):
        super().update(signal=signal)
        if Node.raiseExceptions and self.exception is not None:
            raise self.exception[1]

    @property
    def grid(self):
        return self._grid

    @grid.setter
    @updateOption('grid')
    def grid(self, val):
        self._grid = val

    def process(self, **kw):
        data = kw['dataIn']
        if self.grid:
            data = togrid(data)

        return dict(dataOut=data)


class NodesWidget(QtGui.QWidget):

    def __init__(self, parent=None, node=None):
        super().__init__(parent=parent)
        self.layout = QtGui.QVBoxLayout(self)

    def addNodeWidget(self, node, name):
        group = QtGui.QGroupBox(name)
        layout = QtGui.QVBoxLayout()
        group.setLayout(layout)
        layout.addWidget(node.ctrlWidget())
        self.layout.addWidget(group)
