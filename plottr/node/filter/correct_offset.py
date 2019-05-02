import numpy as np

from plottr import QtCore, QtGui
from plottr.data.datadict import DataDictBase, MeshgridDataDict
from .. import Node, NodeWidget, updateOption


class DimensionCombo(QtGui.QComboBox):

    def __init__(self, node, parent=None):
        super().__init__(self, parent)
        self.node = node

    def setDimensions(self, *dims: str):
        pass


class NodeExt(Node):

    def __init__(self, name: str):
        super().__init__(name)

        self.dataAxes = None
        self.dataFields = None
        self.dataType = None
        self.dataShapes = None

    def process(self, dataIn: DataDictBase=None):
        if dataIn is None:
            return None

        daxes = dataIn.axes()
        dfields = dataIn.dependents()
        dtype = type(dataIn)
        dshapes = dataIn.shapes()

        # if dataIn.axes() != self._dataAxes:

        self.dataAxes = daxes
        self.dataFields = dfields
        self.dataType = dtype
        self.dataShapes = dshapes

        return dict(dataOut=dataIn)



class SubtractAverage(NodeExt):

    def __init__(self, name: str):
        super().__init__(name)
        self._averagingAxis = None

    @property
    def averagingAxis(self):
        return self._averagingAxis

    @averagingAxis.setter
    @updateOption('averagingAxis')
    def averagingAxis(self, value):
        self._averagingAxis = value

    def process(self, dataIn=None):
        if super().process(dataIn=dataIn) is None:
            return None

        data = dataIn.copy()
        if self._averagingAxis in self.dataAxes and \
                self.dataType == MeshgridDataDict:
            axidx = self.dataAxes.index(self._averagingAxis)
            for dep in dataIn.dependents():
                avg = data.data_vals(dep).mean(axis=axidx, keepdims=True)
                data[dep]['values'] -= avg

        return dict(dataOut=data)


