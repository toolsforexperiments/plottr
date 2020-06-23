import os
import pathlib

from pyqtgraph import QtCore, QtGui
QtWidgets = QtGui
Signal = QtCore.pyqtSignal
Slot = QtCore.pyqtSlot

from pyqtgraph.flowchart import Flowchart as pgFlowchart, Node as pgNode
Flowchart = pgFlowchart
NodeBase = pgNode


plottrPath = os.path.split(os.path.abspath(__file__))[0]
configPath = os.path.join(
    os.path.split(plottrPath)[0],
    'config'
)

userConfigPath = os.path.join(
    str(pathlib.Path.home()), '.plottr'
)


def getConfigFilePath(fn, preferUser=True):
    if preferUser and os.path.exists(os.path.join(userConfigPath, fn)):
        return os.path.join(userConfigPath, fn)
    elif os.path.exists(os.path.join(configPath, fn)):
        return os.path.join(configPath, fn)
