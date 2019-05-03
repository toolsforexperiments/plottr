from typing import Dict, Any

from .. import QtGui, QtCore
from .node import Node, NodeWidget, emitGuiUpdate, updateGuiFromNode


class AutoNodeGuiTemnplate(NodeWidget):
    widgetConnection = dict()


def connectIntegerSpinbox(gui: AutoNodeGuiTemnplate, specs: Dict[str, Any]):
    pass


class AutoNodeGui(AutoNodeGuiTemnplate):

    widgetConnection = {
        int: connectIntegerSpinbox,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtGui.QFormLayout()
        self.setLayout(self.layout)


    def addOption(self, name: str, specs: Dict[str, Any]):
        optionType = specs.get('type', None)
        widget = None
        func = self.widgetConnection.get(optionType, None)
        if func is not None:
            widget = func(specs)

        self.layout.addRow(name, widget)

    def addConfirm(self):
        widget = QtGui.QPushButton('Confirm')
        widget.pressed.connect(self.allOptionsWrapper)
        self.layout.addRow('', widget)



