"""data_display_widgets.py

UI elements for inspecting data structure and content.
"""

from typing import Union, List, Tuple, Dict

from .. import QtGui, QtCore
from ..data.datadict import DataDictBase


class DataSelectionWidget(QtGui.QTreeWidget):
    """A simple tree widget to show data fields and dependencies."""

    #: signal (List[str]) that is emitted when the selection is modified.
    dataSelectionMade = QtCore.pyqtSignal(list)

    def __init__(self, parent: QtGui.QWidget = None, readonly: bool = False):
        super().__init__(parent)

        self.setColumnCount(4)
        self.setHeaderLabels(['', 'Name', 'Shape', 'Unit'])
        self.checkBoxes = {}

        self._dataStructure = DataDictBase()
        self._dataShapes = {}
        self._readonly = readonly

    def _makeItem(self, name):
        shape = self._dataShapes.get(name, tuple())
        return QtGui.QTreeWidgetItem([
            '', name, str(shape), self._dataStructure[name].get('unit', '')
        ])

    @QtCore.pyqtSlot(int)
    def _processCbChange(self, _):
        self.emitSelection()

    def _populate(self):
        for n in self._dataStructure.dependents():
            item = self._makeItem(n)
            for ax in self._dataStructure.axes(n):
                child = self._makeItem(ax)
                item.addChild(child)
            self.addTopLevelItem(item)

            if not self._readonly:
                cb = QtGui.QCheckBox()
                self.setItemWidget(item, 0, cb)
                cb.stateChanged.connect(self._processCbChange)
                self.checkBoxes[n] = cb

        for i in range(4):
            self.resizeColumnToContents(i)

    def setData(self, structure: DataDictBase, shapes: dict):
        """Set data; populates the tree."""
        if structure is not None:
            self._dataShapes = shapes
            self._dataStructure = structure
        else:
            self._dataShapes = {}
            self._dataStructure = DataDictBase()

        self.clear()
        if structure is not None:
            self._populate()

    def setShape(self, shape: Dict[str, Tuple[int, ...]]):
        """Set shapes of given elements"""
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            name = item.text(1)
            if name in shape:
                item.setText(2, str(shape[name]))

            for j in range(item.childCount()):
                child = item.child(j)
                childName = child.text(1)
                if childName in shape:
                    child.setText(2, str(shape[childName]))

    def clear(self):
        """Clear the tree, and make sure all selections are cleared."""
        for n, w in self.checkBoxes.items():
            w.setChecked(False)

        self.checkBoxes = {}
        super().clear()

    def setItemEnabled(self, name: str, enable: bool = True):
        """Enable/Disable a tree item by name"""
        item = self.findItems(name, QtCore.Qt.MatchExactly, 1)[0]
        item.setDisabled(not enable)
        self.checkBoxes[name].setDisabled(not enable)

    def getSelectedData(self) -> List[str]:
        """Return a list of currently selected items (by name)"""
        ret = []
        for n, w in self.checkBoxes.items():
            if w.isChecked():
                ret.append(n)
        return ret

    def setSelectedData(self, vals: List[str]):
        """Check all boxes for given items, uncheck all others."""
        for n, w in self.checkBoxes.items():
            if n in vals:
                w.setChecked(True)
            else:
                w.setChecked(False)

    def emitSelection(self):
        """emit the signal ``selectionChanged`` with the current selection"""
        self.dataSelectionMade.emit(self.getSelectedData())
