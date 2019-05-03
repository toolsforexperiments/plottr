"""tools.py

helpers and tools for creating GUI elements.
"""

from typing import Type, Tuple, List

from .widgets import PlotWindow
from .. import QtGui, Flowchart
from ..node import Node
from ..node.tools import linearFlowchart
from ..plot.mpl import PlotNode

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


def widgetDialog(widget: QtGui.QWidget, title: str = '',
                 show: bool = True) -> QtGui.QDialog:
    win = QtGui.QDialog()
    win.setWindowTitle('plottr ' + title)
    layout = QtGui.QVBoxLayout()
    layout.addWidget(widget)
    win.setLayout(layout)
    if show:
        win.show()

    return win


def flowchartAutoPlot(nodes: List[Tuple[str, Type[Node]]]) \
        -> (PlotWindow, Flowchart):
    nodes.append(('plot', PlotNode))
    fc = linearFlowchart(*nodes)
    win = PlotWindow(fc=fc, plotNode='plot')
    return win, fc
