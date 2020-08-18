import os

from qtpy import QtCore, QtGui, QtWidgets

Signal = QtCore.Signal
Slot = QtCore.Slot

from pyqtgraph.flowchart import Flowchart as pgFlowchart, Node as pgNode
Flowchart = pgFlowchart
NodeBase = pgNode

plottrPath = os.path.split(os.path.abspath(__file__))[0]

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
