"""A simple script that illustrates how to use the :class:`.MultiDimensionSelector` widget
in a node to select axes in a dataset.

This example does the following:
* create a flowchart with one node, that has a node widget.
* selected axes in the node widget will be deleted from the data when the
  selection is changed, and the remaining data is printed to stdout.
"""

from typing import List, Optional
from pprint import pprint

import numpy as np

from plottr import QtCore, QtWidgets, Signal, Slot
from plottr.data import DataDict
from plottr.node.node import Node, NodeWidget, updateOption, updateGuiQuietly
from plottr.node.tools import linearFlowchart
from plottr.gui.widgets import MultiDimensionSelector
from plottr.gui.tools import widgetDialog
from plottr.utils import testdata


class DummyNodeWidget(NodeWidget):
    """Node widget for this dummy node"""

    def __init__(self, node: Node):

        super().__init__(embedWidgetClass=MultiDimensionSelector)
        assert isinstance(self.widget, MultiDimensionSelector)  # this is for mypy

        # allow selection of axis dimensions. See :class:`.MultiDimensionSelector`.
        self.widget.dimensionType = 'axes'

        # specify the functions that link node property to GUI elements
        self.optSetters = {
            'selectedAxes': self.setSelected,
        }
        self.optGetters = {
            'selectedAxes': self.getSelected,
        }

        # make sure the widget is populated with the right dimensions
        self.widget.connectNode(node)

        # when the user selects an option, notify the node
        self.widget.dimensionSelectionMade.connect(lambda x: self.signalOption('selectedAxes'))

    @updateGuiQuietly
    def setSelected(self, selected: List[str]) -> None:
        self.widget.setSelected(selected)

    def getSelected(self) -> List[str]:
        return self.widget.getSelected()


class DummyNode(Node):
    useUi = True
    uiClass = DummyNodeWidget

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

    def process(self, dataIn = None) -> Dict[str, Optional[DataDict]]:
        if super().process(dataIn) is None:
            return None
        data = dataIn.copy()
        for k, v in data.items():
            for s in self.selectedAxes:
                if s in v.get('axes', []):
                    idx = v['axes'].index(s)
                    v['axes'].pop(idx)

        for a in self.selectedAxes:
            if a in data:
                del data[a]

        pprint(data)
        return dict(dataOut=data)


def main():
    fc = linearFlowchart(('dummy', DummyNode))
    node = fc.nodes()['dummy']
    dialog = widgetDialog(node.ui, title='dummy node')
    data = testdata.get_2d_scalar_cos_data(2, 2, 1)
    fc.setInput(dataIn=data)
    return dialog, fc


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    dialog, fc = main()
    dialog.show()
    app.exec_()
