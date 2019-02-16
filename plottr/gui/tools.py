"""tools.py

helpers and tools for creating GUI elements.
"""

from .. import QtGui

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
