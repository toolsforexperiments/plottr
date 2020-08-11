"""tools.py

helpers and tools for creating GUI elements.
"""

from .. import QtWidgets

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


def widgetDialog(widget: QtWidgets.QWidget, title: str = '',
                 show: bool = True) -> QtWidgets.QDialog:
    win = QtWidgets.QDialog()
    win.setWindowTitle('plottr ' + title)
    layout = QtWidgets.QVBoxLayout()
    layout.addWidget(widget)
    win.setLayout(layout)
    if show:
        win.show()

    return win


def dictToTreeWidgetItems(d):
    items = []
    for k, v in d.items():
        if not isinstance(v, dict):
            item = QtWidgets.QTreeWidgetItem([str(k), str(v)])
        else:
            item = QtWidgets.QTreeWidgetItem([k, ''])
            for child in dictToTreeWidgetItems(v):
                item.addChild(child)
        items.append(item)
    return items


def flowchartAutoPlot():
    pass
