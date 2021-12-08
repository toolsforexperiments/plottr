"""
node.py

Contains the base class for Nodes.
"""
import traceback
from logging import Logger

from functools import wraps
from typing import Any, Union, Tuple, Dict, Optional, Type, List, Callable, TypeVar

from .. import NodeBase
from .. import QtGui, QtCore, Signal, Slot, QtWidgets
from ..data.datadict import DataDictBase, MeshgridDataDict
from .. import log

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


R = TypeVar('R', bound="Node")
S = TypeVar('S')
T = TypeVar('T')


def updateOption(optName: Optional[str] = None) -> Callable[[Callable[[R, S], T]], Callable[[R, S], T]]:
    """Decorator for property setters that are handy for user options.

    Property setters in nodes that are decorated with this will do two things:
    * call ``Node.update``, in order to update the flowchart.
    * if there is a UI, we call the matching ``optSetter`` function.

    :param optName: name of the property.
    """

    def decorator(func: Callable[[R, S], T]) -> Callable[[R, S], T]:
        @wraps(func)
        def wrap(self: R, val: S) -> T:
            ret = func(self, val)
            if optName is not None and self.ui is not None and \
                    optName in self.ui.optSetters:
                self.ui.optSetters[optName](val)
            self.update(self.signalUpdate)
            return ret

        return wrap

    return decorator


U = TypeVar('U', bound="NodeWidget")
V = TypeVar('V',)


def updateGuiFromNode(func: Callable[..., V]) -> Callable[..., V]:
    """
    Decorator for the UI to set an internal flag to during execution of
    the wrapped function. Prevents recursive updating (i.e., if
    the node sends a new option value to the UI for updating, the UI
    will then `not` notify the node back after making the update).
    """

    @wraps(func)
    def wrap(self: U, *arg: Any, **kw: Any) -> V:
        self._emitGuiChange = False
        ret = func(self, *arg, **kw)
        self._emitGuiChange = True
        return ret

    return wrap


updateGuiQuietly = updateGuiFromNode

W = TypeVar('W')


def emitGuiUpdate(signalName: str) -> Callable[[Callable[..., Any]], Callable[..., None]]:
    """
    Decorator for UI functions to emit the signal ``signalName``
    (given as argument the decorator), with the return of the wrapped function.

    Signal is only emitted if the flag controlled by ``updateGuiFromNode``
    is not ``True``, i.e., if the option change was `not` caused by a
    function decorated with ``updateGuiFromNode``.

    :param signalName: name of the signal to emit.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., None]:
        @wraps(func)
        def wrap(self: W, *arg: Any, **kw: Any) -> None:
            ret = func(self, *arg, **kw)
            emit = getattr(self, '_emitGuiChange', True)
            if emit:
                sig = getattr(self, signalName)
                sig.emit(ret)

        return wrap

    return decorator


# TODO: should we add a list of options to the class?
#   that would allow programmatic syncing from node to widget, for instance.
class Node(NodeBase):
    """Base class of the Node we use for plotter.

    This class inherits from ``pyqtgraph``'s Node, and adds a few additional
    tools, and some defaults.
    """

    #: Name of the node. used in the flowchart node library.
    nodeName = 'Node'

    #: Default terminals: one input and one output.
    terminals = {
        'dataIn': {'io': 'in'},
        'dataOut': {'io': 'out'},
    }

    #: UI node widget class. If not None, and ``useUi`` is ``True``, an
    #: instance of the widget is created, and signal/slots are connected.
    uiClass: Optional[Type["NodeWidget"]] = None

    #: Whether or not to automatically set up a UI widget.
    useUi = True

    #: Whether the ui should be visible by default
    uiVisibleByDefault = False

    #: A signal to notify the UI of option changes
    #: arguments is a dictionary of options and new values.
    optionChangeNotification = Signal(dict)

    #: signal emitted when available data axes change
    #: emits a the list of names of new axes
    dataAxesChanged = Signal(list)

    #: signal emitted when available dependents change
    #: emits a the list of names of new dependents
    dataDependentsChanged = Signal(list)

    #: signal emitted when any available data fields change (dep. and indep.)
    #: emits a the list of names of new axes
    dataFieldsChanged = Signal(list)

    #: signal emitted when data type changes
    dataTypeChanged = Signal(object)

    #: signal emitted when data structure changes (fields, or dtype)
    dataStructureChanged = Signal(object)

    #: signal emitted when data shapes change
    dataShapesChanged = Signal(dict)

    #: when data structure changes, emits (structure, shapes, type)
    newDataStructure = Signal(object, object, object)

    #: developer flag for whether we actually want to raise of use the logging
    #: system
    _raiseExceptions = False

    def __init__(self, name: str):
        """Create a new instance of the Node.

        :param name: name of the instance.
        """
        super().__init__(name, terminals=self.__class__.terminals)

        self.signalUpdate = True
        self.dataAxes: Optional[List[str]] = None
        self.dataDependents: Optional[List[str]] = None
        self.dataType: Optional[Type[DataDictBase]] = None
        self.dataShapes: Optional[Dict[str, Tuple[int, ...]]] = None
        self.dataStructure: Optional[DataDictBase] = None

        if self.useUi and self.__class__.uiClass is not None:
            self.ui: Optional["NodeWidget"] = self.__class__.uiClass(node=self)
            self.setupUi()
        else:
            self.ui = None

    def setupUi(self) -> None:
        """ setting up the UI widget.

        Gets called automatically in the node initialization.
        Automatically connect the UIs methods to signal option values.

        Inheriting classes can use this method to do additional setup of the
        UI widget (like connecting additional signals/slots between node and
        node widget).
        """
        assert self.ui is not None
        self.ui.optionToNode.connect(self.setOption)
        self.ui.allOptionsToNode.connect(self.setOptions)
        self.optionChangeNotification.connect(self.ui.setOptionsFromNode)

    def ctrlWidget(self) -> Union[QtWidgets.QWidget, None]:
        """Returns the node widget, if it exists.
        """
        return self.ui

    def setOption(self, nameAndVal: Tuple[str, Any]) -> None:
        """Set an option.

        name is the name of the property, not the string used for referencing
        (which could in principle be different).

        :param nameAndVal: tuple of option name and new value
        """
        name, val = nameAndVal
        setattr(self, name, val)

    def setOptions(self, opts: Dict[str, Any]) -> None:
        """Set multiple options.

        :param opts: a dictionary of property name : value pairs.
        """
        for opt, val in opts.items():
            setattr(self, opt, val)

    def update(self, signal: bool = True) -> None:
        super().update(signal=signal)
        if Node._raiseExceptions and self.exception is not None:
            raise self.exception[1]
        elif self.exception is not None:
            e = self.exception
            err = f'EXCEPTION RAISED: {e[0]}: {e[1]}\n'
            for t in traceback.format_tb(e[2]):
                err += f' -> {t}\n'
            self.logger().error(err)

    def logger(self) -> Logger:
        """Get a logger for this node

        :return: logger with a name that can be traced back easily to this node.
        """
        name = f"{self.__module__}.{self.__class__.__name__}.{self.name()}"
        logger = log.getLogger(name)
        logger.setLevel(log.LEVEL)
        return logger

    def validateOptions(self, data: DataDictBase) -> bool:
        """Validate the user options

        Does nothing in this base implementation. Can be reimplemented by any
        inheriting class.

        :param data: the data to verify the options against.
        """
        return True

    # TODO: should think about nodes with multiple inputs -- how would this look then?
    # FIXME: return should only be Optional[Dict[str, DataDictBase]]
    def process(self, dataIn: Optional[DataDictBase]=None) -> Optional[Dict[str, Optional[DataDictBase]]]:
        if dataIn is None:
            return None

        if not isinstance(dataIn, DataDictBase):
            raise ValueError('Unsupported data format provided.')

        _axesChanged = False
        _fieldsChanged = False
        _typeChanged = False
        _structChanged = False
        _shapesChanged = False
        _depsChanged = False

        dtype = type(dataIn)
        daxes = dataIn.axes()
        ddeps = dataIn.dependents()
        dshapes = dataIn.shapes()
        dstruct = dataIn.structure(add_shape=False)

        if None in [self.dataAxes, self.dataDependents, self.dataType, self.dataShapes]:
            _axesChanged = True
            _fieldsChanged = True
            _typeChanged = True
            _structChanged = True
            _shapesChanged = True
            _depsChanged = True

        else:
            if daxes != self.dataAxes:
                _fieldsChanged = True
                _structChanged = True
                _axesChanged = True

            if ddeps != self.dataDependents:
                _fieldsChanged = True
                _structChanged = True
                _depsChanged = True

            if dtype != self.dataType:
                _typeChanged = True
                _structChanged = True

            if dshapes != self.dataShapes:
                _shapesChanged = True

        self.dataAxes = daxes
        self.dataDependents = ddeps
        self.dataType = dtype
        self.dataShapes = dshapes
        self.dataStructure = dstruct

        if _axesChanged:
            self.dataAxesChanged.emit(daxes)

        if _depsChanged:
            self.dataDependentsChanged.emit(ddeps)

        if _fieldsChanged:
            self.dataFieldsChanged.emit(daxes + ddeps)

        if _typeChanged:
            self.dataTypeChanged.emit(dtype)

        if _structChanged:
            self.dataStructureChanged.emit(self.dataStructure)
            self.newDataStructure.emit(
                self.dataStructure, self.dataShapes, self.dataType)

        if _shapesChanged and not _structChanged:
            self.dataShapesChanged.emit(dshapes)

        if not self.validateOptions(dataIn):
            self.logger().debug("Option validation not passed")
            return None

        return dict(dataOut=dataIn)


class NodeWidget(QtWidgets.QWidget):
    """
    Base class for Node control widgets.

    For the widget class to set up communication with the Node automatically,
    make sure to set :attr:`plottr.node.node.NodeWidget.optGetters` and
    :attr:`plottr.node.node.NodeWidget.optSetters` for a widget class.
    """

    #: icon for this node
    icon: Optional[QtGui.QIcon] = None

    #: preferred location of the widget when used as dock widget
    preferredDockWidgetArea = QtCore.Qt.LeftDockWidgetArea

    #: signal (args: object)) to emit to notify the node of a (changed)
    #: user option.
    optionToNode = Signal(object)

    #: signal (args: (object)) all options to the node.
    allOptionsToNode = Signal(object)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None,
                 embedWidgetClass: Optional[Type[QtWidgets.QWidget]] = None,
                 node: Optional[Node] = None):
        super().__init__(parent)

        self.optGetters: Dict[str, Callable[[], Any]] = {}
        self.optSetters: Dict[str, Callable[[Any], None]] = {}
        self.node = node

        self._emitGuiChange = True

        self.widget: Optional[QtWidgets.QWidget] = None

        if embedWidgetClass is not None:
            layout = QtWidgets.QVBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            self.widget = embedWidgetClass()
            layout.addWidget(self.widget)
            self.setLayout(layout)

    def getAllOptions(self) -> Dict[str, Any]:
        """Return all options as a dictionary"""
        ret = {}
        for n, f in self.optGetters.items():
            ret[n] = f()

        return ret

    @updateGuiFromNode
    def setOptionFromNode(self, opt: str, value: Any) -> None:
        """Set an option from the node

        Calls the set function specified in the class' ``optSetters``.
        Decorated with ``@updateGuiFromNode``.

        :param opt: name of the option
        :param value: value to set
        """
        self.optSetters[opt](value)

    @Slot(dict)
    def setOptionsFromNode(self, opts: Dict[str, Any]) -> None:
        """Set all options without triggering updates back to the node."""
        for opt, val in opts.items():
            self.setOptionFromNode(opt, val)

    @emitGuiUpdate('optionToNode')
    def signalOption(self, name: str) -> Tuple[str, Any]:
        """Returns name and value of an option.

        Value is determined from the optGetters.
        Decorated with ``@emitGuiUpdate('optionToNode')``.

        :param name: name of the option
        """
        return name, self.optGetters[name]()

    @emitGuiUpdate('allOptionsToNode')
    def signalAllOptions(self) -> Dict[str, Any]:
        """Return all options as a dictionary

        Decorated with ``@emitGuiUpdate('optionToNode')``.
        """
        return self.getAllOptions()
