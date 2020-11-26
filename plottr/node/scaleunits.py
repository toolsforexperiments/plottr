from enum import Enum, unique
from typing import Optional, Dict

from plottr import QtWidgets
from plottr.node import Node, NodeWidget, updateOption
from plottr.data.datadict import DataDictBase

@unique
class StateOption(Enum):
    """Options for how to scale units."""

    #: do not scale units
    never = 0

    #: only simple units
    simpleunits = 1

    #: all units
    always = 2


class ScaleUnitOptionWidget(QtWidgets.QWidget):

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        self.buttons = {
            StateOption.never: QtWidgets.QRadioButton('Never'),
            StateOption.simpleunits: QtWidgets.QRadioButton('Simple Units'),
            StateOption.always: QtWidgets.QRadioButton('Always'),
        }
        btnLayout = QtWidgets.QVBoxLayout()
        self.btnGroup = QtWidgets.QButtonGroup(self)

        for opt in StateOption:
            btn = self.buttons[opt]
            self.btnGroup.addButton(btn, opt.value)
            btnLayout.addWidget(btn)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(btnLayout)
        layout.addStretch()
        self.setLayout(layout)
        self.buttons[StateOption.never].setChecked(True)


class ScaleUnitsWidget(NodeWidget):

    def __init__(self, node: Optional[Node] = None):
        super().__init__(node=node, embedWidgetClass=ScaleUnitOptionWidget)


class ScaleUnits(Node):

    useUi = True
    uiClass = ScaleUnitsWidget

    def __init__(self, name: str):
        super().__init__(name)
        self._state: Optional[str] = None

    @property
    def state(self):
        return self._state

    @state.setter  # type: ignore[misc]
    @updateOption('state')
    def state(self, value: str) -> None:
        self._state = value

    def process(self, dataIn: Optional[DataDictBase]=None) -> Optional[Dict[str, Optional[DataDictBase]]]:
        return dict(dataOut=dataIn)
