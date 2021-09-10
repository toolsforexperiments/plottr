from typing import List

import numpy as np

from plottr import QtCore, QtWidgets, Signal, Slot
from plottr.data import DataDict
from plottr.node import Node, NodeWidget, updateOption
from plottr.node.tools import linearFlowchart


class TestNodeWidget(NodeWidget):
    pass


class TestNode(Node):
    useUi = False
    uiClass = TestNodeWidget

    def __init__(self, name: str):
        super().__init__(name)
        self._selectedAxes: List[str] = []

    @property
    def selectedAxes(self):
        return self._selectedAxes

    @selectedAxes.setter
    @updateOption('selectedAxes')
    def selectedAxes(self, value: List[str]):
        self._selectedAxes = value

    def process(self, dataIn = None):
        dataIn = super().process(dataIn)
        if dataIn is None:
            return None

        for k, v in dataIn.items():
            if k in v.get('axes', []):
                idx = v['axes'].index(k)
                v['axes'].pop(idx)

        for a in self.selectedAxes:
            if a in dataIn:
                del dataIn[a]

        return dict(dataOut=dataIn)


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    fc = linearFlowchart(('test', TestNode))
    node = fc.nodes()['test']
    app.exec_()



