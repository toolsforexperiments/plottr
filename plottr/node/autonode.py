from typing import Dict, Any, Callable, Optional, Type

from .. import QtGui, QtWidgets
from .node import Node, NodeWidget, updateOption

connectCallableType = Callable[['AutoNodeGuiTemplate', str, Dict[str, Any], bool], QtWidgets.QWidget]


class AutoNodeGuiTemplate(NodeWidget):
    widgetConnection: Dict[type, connectCallableType] = dict()


def connectIntegerSpinbox(
        gui: AutoNodeGuiTemplate,
        optionName: str,
        specs: Dict[str, Any],
        confirm: bool) -> QtWidgets.QSpinBox:

    widget = QtWidgets.QSpinBox()
    widget.setValue(specs.get('initialValue', 1))
    if not confirm:
        widget.valueChanged.connect(lambda x: gui.signalOption(optionName))

    gui.optGetters[optionName] = widget.value
    gui.optSetters[optionName] = widget.setValue

    return widget

def connectFloatSpinbox(
        gui: AutoNodeGuiTemplate,
        optionName: str,
        specs: Dict[str, Any],
        confirm: bool) -> QtWidgets.QDoubleSpinBox:

    widget = QtWidgets.QDoubleSpinBox()
    widget.setValue(specs.get('initialValue', 1))
    if not confirm:
        widget.valueChanged.connect(lambda x: gui.signalOption(optionName))

    gui.optGetters[optionName] = widget.value
    gui.optSetters[optionName] = widget.setValue

    return widget


class AutoNodeGui(AutoNodeGuiTemplate):

    widgetConnection = {
        int: connectIntegerSpinbox,
        float: connectFloatSpinbox,
    }

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None,
                 node: Optional[Node] = None):
        super().__init__(parent)
        layout = QtWidgets.QFormLayout()
        self.setLayout(layout)

    def addOption(self, name: str, specs: Dict[str, Any], confirm: bool) -> None:
        optionType = specs.get('type', None)
        widget = None
        func = self.widgetConnection.get(optionType, None)
        if func is not None:
            widget = func(self, name, specs, confirm)

        self.layout().addRow(name, widget)

    def addConfirm(self) -> None:
        widget = QtWidgets.QPushButton('Confirm')
        widget.pressed.connect(self.signalAllOptions)
        self.layout().addRow('', widget)


class AutoNode(Node):

    def addOption(self, name: str, specs: Dict[str, Any]) -> None:
        varname = '_' + name
        setattr(self, varname, specs.get("initialValue", None))

        def getter(self: AutoNode) -> Any:
            return getattr(self, varname)

        @updateOption(name)
        def setter(self: AutoNode, val: str) -> None:
            setattr(self, varname, val)

        setattr(self.__class__, name, property(getter, setter))


def autonode(nodeName: str, confirm: bool = True, **options: Any) -> Callable:

    def decorator(func: Callable) -> Type["AutoNode"]:

        class AutoNodeGui_(AutoNodeGui):
            def __init__(self, parent: Optional[QtWidgets.QWidget] = None,
                         node: Optional[Node] = None):
                super().__init__(parent)
                for optName, optSpecs in options.items():
                    self.addOption(optName, optSpecs, confirm=confirm)
                if confirm:
                    self.addConfirm()

        class AutoNode_(AutoNode):
            def __init__(self, name: str):
                super().__init__(name)
                for optName, optSpecs in options.items():
                    self.addOption(optName, optSpecs)

        AutoNode_.__name__ = nodeName
        AutoNode_.nodeName = nodeName
        AutoNode_.nodeOptions = options
        AutoNode_.process = func  # type: ignore[assignment]
        AutoNode_.useUi = True
        AutoNode_.uiClass = AutoNodeGui_

        return AutoNode_

    return decorator
