"""
node.py

Contains the base class for Nodes.
"""
import copy
from pprint import pprint
import logging

import numpy as np

from pyqtgraph.flowchart import Flowchart, Node as pgNode
from pyqtgraph.Qt import QtGui, QtCore

from ..data import datadict as dd
from ..data.datadict import DataDict
from .. import log

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'

# TODO: implement a threaded version of Node
# TODO: needed: an order widget for filters
# TODO: formalize/abstract updating the gui better.
# TODO: add a 'fresh' flag that allows to set nice defaults on first data-input

class Node(pgNode):
    """
    The node base class used in plottr, derived from pyqtgraph's `Node'.
    More thorough documentation is still an outstanding task...
    """

    optionChanged = QtCore.pyqtSignal(str, object)

    raiseExceptions = True
    nodeName = "DataDictNode"
    terminals = {
        'dataIn' : {'io' : 'in'},
        'dataOut' : {'io' : 'out'},
    }
    uiClass = None
    useUi = True
    guiOptions = {}

    def __init__(self, name):
        super().__init__(name, terminals=self.__class__.terminals)

        self.signalUpdate = True
        self.optionChanged.connect(self.processOptionUpdate)

        if self.useUi and self.__class__.uiClass is not None:
            self.ui = self.__class__.uiClass()
            self.setupUi()
        else:
            self.ui = None

    def setupUi(self):
        return

    def ctrlWidget(self):
        return self.ui

    def updateOption(optName=None):
        def decorator(func):
            def wrap(self, val):
                ret = func(self, val)
                if optName is not None:
                    self.optionChanged.emit(optName, val)
                self.update(self.signalUpdate)
                return ret
            return wrap
        return decorator

    def processOptionUpdate(self, optName, value):
        if optName in self.guiOptions:
            if self.ui is not None and optName in self.guiOptions:
                if self.guiOptions[optName]['widget'] is not None:
                    w = getattr(self.ui, self.guiOptions[optName]['widget'])
                    func = getattr(w, self.guiOptions[optName]['setFunc'])
                else:
                    func = getattr(self.ui, self.guiOptions[optName]['setFunc'])
                func(value)

    def update(self, signal=True):
        super().update(signal=signal)
        if Node.raiseExceptions and self.exception is not None:
            raise self.exception[1]

    def logger(self):
        logger = log.getLogger(self.__module__ + '.' + self.__class__.__name__)
        logger.setLevel(log.LEVEL)
        return logger

    def validateOptions(self, data):
        return True

    def process(self, **kw):
        data = kw['dataIn']

        if not self.validateOptions(data):
            self.logger().debug("Option validation not passed")
            return None

        if data is None:
            return None

        return dict(dataOut=data)


class NodeWidget(QtGui.QWidget):
    """
    Base class for Node control widgets.

    Provides convenience tools for interacting with Nodes:

    * `updateGuiFromNode`: Use this decorator on methods that update a GUI property
      prompted by an option change in the node. It will set an internal flag that can
      be used to prevent signaling the node in turn that the GUI has changed (which
      could result in infinite signal/slot loops if we're not careful).

    * `emitGuiUpdate(signalName)`: Functions with this decorator will emit the signal
      `signalName` with the function return as argument. This can be used to communicate
      GUI changes to the node. Note: The signal still has to be declared manually,
      and the connection to the node has to be made as well (typically from the node
      side).
      Importantly, this method will **not** emit the signal if the internal flag
      mentioned above is not True; thus we only send the signal to the Node if the
      Node is **not** the origin of the change to start with.
    """

    def updateGuiFromNode(func):
        """
        Decorator to set an internal flag to False during execution of the wrapped
        function.
        """
        def wrap(self, *arg, **kw):
            self._emitGuiChange = False
            ret = func(self, *arg, **kw)
            self._emitGuiChange = True
            return ret
        return wrap

    def emitGuiUpdate(signalName):
        """
        Decorator to emit signalName with the return of the wrapped function after
        execution. Signal is only emitted if the flag controlled by `updateGuiFromNode`
        is not True, i.e., if the option change was not caused by a function
        decorated with `updateGuiFromNode`.
        """
        def decorator(func):
            def wrap(self, *arg, **kw):
                ret = func(self, *arg, **kw)
                if self._emitGuiChange:
                    sig = getattr(self, signalName)
                    sig.emit(ret)
            return wrap
        return decorator

    def __init__(self, parent: QtGui.QWidget = None):
        super().__init__(parent)

        self._emitGuiChange = True
