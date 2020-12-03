from typing import TYPE_CHECKING, List, Tuple
import os

if TYPE_CHECKING:
    from PyQt5 import QtCore, QtGui, QtWidgets
    Signal = QtCore.pyqtSignal
    Slot = QtCore.pyqtSlot
else:
    from qtpy import QtCore, QtGui, QtWidgets
    Signal = QtCore.Signal
    Slot = QtCore.Slot

from pyqtgraph.flowchart import Flowchart as pgFlowchart, Node as pgNode
Flowchart = pgFlowchart
NodeBase = pgNode

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

plottrPath = os.path.split(os.path.abspath(__file__))[0]


def configPaths() -> Tuple[str, str, str]:
    """Get the folders where plottr looks for config files.

    :return: List of absolute paths, in order of priority:
        (1) current working directory
        (2) ~/.plottr
        (3) config directory in the package.
    """
    builtIn = os.path.join(plottrPath, 'config')
    user = os.path.join(os.path.expanduser("~"), '.plottr')
    cwd = os.getcwd()
    return cwd, user, builtIn


def configFiles(fileName: str) -> List[str]:
    """Get available config files with the given file name.

    :param fileName: file name, without path
    :return: List of found config files with the provided name, in order
        or priority.
    """
    ret = []
    for path in configPaths():
        fp = os.path.join(path, fileName)
        if os.path.exists(fp):
            ret.append(fp)
    return ret
