from typing import Sequence, Optional, Dict

import numpy as np

from plottr import Signal, Slot, QtWidgets
from plottr.node import Node, NodeWidget, updateOption
from plottr.node.node import updateGuiQuietly, emitGuiUpdate
from plottr.gui.widgets import FormLayoutWrapper
from plottr.data.datadict import DataDictBase, MeshgridDataDict


class DimensionCombo(QtWidgets.QComboBox):
    dimensionSelected = Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None,
                 dimensionType: str = 'axes'):
        super().__init__(parent)

        self.node: Optional[Node] = None
        self.dimensionType = dimensionType

        self.clear()
        self.entries = ['None']
        for e in self.entries:
            self.addItem(e)

        self.currentTextChanged.connect(self.signalDimensionSelection)

    def connectNode(self, node: Optional[Node] = None) -> None:
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
        allDims = self.entries + list(dims)
        for d in allDims:
            self.addItem(d)

    @Slot(str)
    @emitGuiUpdate('dimensionSelected')
    def signalDimensionSelection(self, val: str) -> str:
        return val


class AxisSelector(FormLayoutWrapper):

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(
            parent=parent,
            elements=[('Axis', DimensionCombo(dimensionType='axes'))],
        )


class SubtractAverageWidget(NodeWidget):

    def __init__(self, node: Optional[Node] = None):
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

    def setAvgAxis(self, val: str) -> None:
        self.combo.setCurrentText(val)

    def getAvgAxis(self) -> str:
        return self.combo.currentText()


class SubtractAverage(Node):
    useUi = True
    uiClass = SubtractAverageWidget

    def __init__(self, name: str):
        super().__init__(name)
        self._averagingAxis: Optional[str] = None

    @property
    def averagingAxis(self) -> Optional[str]:
        return self._averagingAxis

    @averagingAxis.setter  # type: ignore[misc]
    @updateOption('averagingAxis')
    def averagingAxis(self, value: str) -> None:
        self._averagingAxis = value

    def process(self, dataIn: Optional[DataDictBase] = None) -> Optional[Dict[str, Optional[DataDictBase]]]:
        if super().process(dataIn=dataIn) is None:
            return None
        assert dataIn is not None
        assert self.dataAxes is not None
        data = dataIn.copy()
        if self._averagingAxis in self.dataAxes and \
                self.dataType == MeshgridDataDict:
            axidx = self.dataAxes.index(self._averagingAxis)
            for dep in dataIn.dependents():
                data_vals = np.asanyarray(data.data_vals(dep))
                avg = data_vals.mean(axis=axidx, keepdims=True)
                data[dep]['values'] -= avg

        return dict(dataOut=data)


