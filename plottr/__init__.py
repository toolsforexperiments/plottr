import os

from pyqtgraph import QtCore, QtGui
QtWidgets = QtGui
Signal = QtCore.pyqtSignal
Slot = QtCore.pyqtSlot

from pyqtgraph.flowchart import Flowchart as pgFlowchart, Node as pgNode
Flowchart = pgFlowchart
NodeBase = pgNode

plottrPath = os.path.split(os.path.abspath(__file__))[0]

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
