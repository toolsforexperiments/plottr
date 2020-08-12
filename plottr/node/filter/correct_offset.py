from typing import Sequence

from plottr import Signal, Slot, QtWidgets
from plottr.node import Node, NodeWidget, updateOption
from plottr.node.node import updateGuiQuietly, emitGuiUpdate
from plottr.gui.widgets import FormLayoutWrapper
from plottr.data.datadict import DataDictBase, MeshgridDataDict


class DimensionCombo(QtWidgets.QComboBox):
    dimensionSelected = Signal(str)

    def __init__(self, parent=None, dimensionType='axes'):
        super().__init__(parent)

        self.node = None
        self.dimensionType = dimensionType

        self.clear()
        self.entries = ['None']
        for e in self.entries:
            self.addItem(e)

        self.currentTextChanged.connect(self.signalDimensionSelection)

    def connectNode(self, node: Node = None) -> None:
        if node is None:
            raise RuntimeError
        self.node = node
        if self.dimensionType == 'axes':
            self.node.dataAxesChanged.connect(self.setDimensions)
        else:
            raise NotImplementedError('Only Axes supported ATM.')

    @updateGuiQuietly
    def setDimensions(self, dims: Sequence[str]) -> None:
        self.clear()
        allDims = self.entries + dims
        for d in allDims:
            self.addItem(d)

    @Slot(str)
    @emitGuiUpdate('dimensionSelected')
    def signalDimensionSelection(self, val: str) -> str:
        return val


class AxisSelector(FormLayoutWrapper):

    def __init__(self, parent=None):
        super().__init__(
            parent=parent,
            elements=[('Axis', DimensionCombo(dimensionType='axes'))],
        )


class SubtractAverageWidget(NodeWidget):

    def __init__(self, node: Node = None):
        super().__init__(node=node, embedWidgetClass=AxisSelector)
        if self.widget is None:
            raise RuntimeError

        self.optSetters = {
            'averagingAxis': self.setAvgAxis,
        }

        self.optGetters = {
            'averagingAxis': self.getAvgAxis,
        }

        self.combo = self.widget.elements['Axis']
        self.combo.connectNode(self.node)
        self.combo.dimensionSelected.connect(
            lambda x: self.signalOption('averagingAxis')
        )

    def setAvgAxis(self, val):
        self.combo.setCurrentText(val)

    def getAvgAxis(self):
        return self.combo.currentText()


class SubtractAverage(Node):
    useUi = True
    uiClass = SubtractAverageWidget

    def __init__(self, name: str):
        super().__init__(name)
        self._averagingAxis = None

    @property
    def averagingAxis(self):
        return self._averagingAxis

    @averagingAxis.setter  # type: ignore[misc]
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


