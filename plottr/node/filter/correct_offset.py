from typing import List

from plottr import QtGui, Signal, Slot
from plottr.data.datadict import DataDictBase, MeshgridDataDict
from .. import Node as Node_, NodeWidget as NodeWidget_, updateOption
from ..node import updateGuiQuietly, emitGuiUpdate


class NodeWidget(NodeWidget_):
    pass


class Node(Node_):
    #: signal emitted when available data axes change
    #: emits a the list of names of new axes
    dataAxesChanged = Signal(list)

    #: signal emitted when any available data fields change (dep. and indep.)
    #: emits a the list of names of new axes
    dataFieldsChanged = Signal(list)

    #: signal emitted when data type changes
    dataTypeChanged = Signal(object)

    #: signal emitted when data structure changes (fields, or dtype)
    dataStructureChanged = Signal(object)

    #: signal emitted when data shapes change
    dataShapesChanged = Signal(dict)

    def __init__(self, name: str):
        super().__init__(name)

        self.dataAxes = None
        self.dataDependents = None
        self.dataType = None
        self.dataShapes = None

    def process(self, dataIn: DataDictBase=None):
        if dataIn is None:
            return None

        daxes = dataIn.axes()
        ddeps = dataIn.dependents()
        dtype = type(dataIn)
        dshapes = dataIn.shapes()

        if daxes != self.dataAxes:
            self.dataAxesChanged.emit(daxes)

        if daxes != self.dataAxes or ddeps != self.dataDependents:
            self.dataFieldsChanged.emit(daxes + ddeps)

        if dtype != self.dataType:
            self.dataTypeChanged.emit(dtype)

        if dtype != self.dataType or daxes != self.dataAxes \
                or ddeps != self.dataDependents:
            self.dataStructureChanged.emit(dataIn.structure(add_shape=False))

        if dshapes != self.dataShapes:
            self.dataShapesChanged.emit(dshapes)

        self.dataAxes = daxes
        self.dataDependents = ddeps
        self.dataType = dtype
        self.dataShapes = dshapes

        return super().process(dataIn=dataIn)


class AxesCombo(QtGui.QComboBox):
    axisSelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.node = None

        self.clear()
        self.entries = ['None']
        for e in self.entries:
            self.addItem(e)

        self.currentTextChanged.connect(self.signalAxisSelection)

    def connectNode(self, node: Node = None):
        self.node = node
        self.node.dataAxesChanged.connect(self.setDimensions)

    @updateGuiQuietly
    def setDimensions(self, dims: List[str]):
        self.clear()
        allDims = self.entries + dims
        for d in allDims:
            self.addItem(d)

    @Slot(str)
    @emitGuiUpdate('axisSelected')
    def signalAxisSelection(self, val: str):
        return val


class SubtractAverageWidget(NodeWidget):

    def __init__(self, node: Node = None):
        super().__init__(node=node, embedWidgetClass=AxesCombo)

        self.optSetters = {
            'averagingAxis': self.setAvgAxis,
        }

        self.optGetters = {
            'averagingAxis': self.getAvgAxis,
        }

        self.widget.connectNode(self.node)
        self.widget.axisSelected.connect(
            lambda x: self.signalOption('averagingAxis')
        )

    def setAvgAxis(self, val):
        self.widget.setCurrentText(val)

    def getAvgAxis(self):
        return self.widget.currentText()


class SubtractAverage(Node):
    useUi = True
    uiClass = SubtractAverageWidget

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


