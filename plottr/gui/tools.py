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


def dictToTreeWidgetItems(d):
    items = []
    for k, v in d.items():
        if not isinstance(v, dict):
            item = QtGui.QTreeWidgetItem([str(k), str(v)])
        else:
            item = QtGui.QTreeWidgetItem([k, ''])
            for child in dictToTreeWidgetItems(v):
                item.addChild(child)
        items.append(item)
    return items


def flowchartAutoPlot():
    pass
