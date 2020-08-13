import os

from pyqtgraph.Qt import QtCore, QtGui, QtWidgets, QT_LIB

if QT_LIB == 'PyQt5':
    Signal = QtCore.pyqtSignal
    Slot = QtCore.pyqtSlot
elif QT_LIB == 'PySide2':
    Signal = QtCore.Signal
    Slot = QtCore.Slot
else:
    raise RuntimeError("Unsupported Qt backend. "
                       "Plottr supports PyQt5 and PySide2. Got: "
                       f"{QT_LIB} which is not supported.")

from pyqtgraph.flowchart import Flowchart as pgFlowchart, Node as pgNode
Flowchart = pgFlowchart
NodeBase = pgNode

plottrPath = os.path.split(os.path.abspath(__file__))[0]

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
