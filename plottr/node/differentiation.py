from typing import Optional, Dict
import numpy as np
from plottr.data.datadict import DataDictBase, MeshgridDataDict
from plottr.node.node import Node, NodeWidget, updateOption
from plottr.gui.widgets import AxisSelector

class DifferentiationWidget(NodeWidget):

    def __init__(self, node: Optional[Node] = None):
        super().__init__(node=node, embedWidgetClass=AxisSelector)
        if self.widget is None:
            raise RuntimeError

        self.optSetters = {
            'diffAxis': self.setDiffAxis,
        }

        self.optGetters = {
            'diffAxis': self.getDiffAxis,
        }

        self.combo = self.widget.elements['Axis']
        self.combo.connectNode(self.node)
        self.combo.dimensionSelected.connect(
            lambda x: self.signalOption('diffAxis')
        )

    def setDiffAxis(self, val: str) -> None:
        self.combo.setCurrentText(val)

    def getDiffAxis(self) -> str:
        return self.combo.currentText()

class Differentiation(Node):
    nodeName = 'Differentiation'

    useUi = True
    uiClass = DifferentiationWidget

    def __init__(self, name: str):
        super().__init__(name)
        self._diffAxis: Optional[str] = None

    @property
    def diffAxis(self) -> Optional[str]:
        return self._diffAxis

    @diffAxis.setter
    @updateOption('diffAxis')
    def diffAxis(self, value: str) -> None:
        self._diffAxis = value

    def process(self, dataIn: Optional[DataDictBase] = None) -> Optional[Dict[str, Optional[DataDictBase]]]:
        if super().process(dataIn=dataIn) is None:
            return None
        assert dataIn is not None
        assert self.dataAxes is not None
        data = dataIn.copy()
        if self._diffAxis in self.dataAxes and \
                self.dataType == MeshgridDataDict:
            axidx = self.dataAxes.index(self._diffAxis)
            for dep in dataIn.dependents():
                data_vals = np.asanyarray(data.data_vals(dep))
                data[dep]['values'] = np.diff(data_vals, axis=axidx)
                data[dep]['label'] = 'diff_{}'.format(data[dep]['label'])
            # Align array shapes
            for axs in self.dataAxes:
                data_vals = np.asanyarray(data.data_vals(axs))
                data[axs]['values'] = self.remove_last_element(arr=data_vals, axis=axidx)

        return dict(dataOut=data)

    def remove_last_element(self, arr: np.ndarray, axis: int) -> np.ndarray:
        """
        remove last element of specified axes

        Parameters:
        arr (np.ndarray): target array
        axis (int): specified axes

        Returns:
        np.ndarray: array removed last element of specified axes
        """

        slicer = [slice(None)] * arr.ndim
        slicer[axis] = slice(0, -1)
        
        return arr[tuple(slicer)]
