"""data_display_widgets.py

UI elements for inspecting data structure and content.
"""

from typing import Union, List, Tuple, Dict, Any, Optional

from .. import QtCore, QtWidgets, Signal, Slot
from ..data.datadict import DataDictBase


class DataSelectionWidget(QtWidgets.QTreeWidget):
    """A simple tree widget to show data fields and dependencies."""

    #: signal (List[str]) that is emitted when the selection is modified.
    dataSelectionMade = Signal(list)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None,
                 readonly: bool = False):
        super().__init__(parent)

        self.setColumnCount(3)
        self.setHeaderLabels(['Name', 'Dependencies', 'Size'])
        self.dataItems: Dict[str, Any] = {}

        self._dataStructure = DataDictBase()
        self._dataShapes: Dict[str, Tuple[int, ...]] = {}
        self._readonly = readonly

        self.setSelectionMode(self.MultiSelection)
        self.itemSelectionChanged.connect(self.emitSelection)

    def _makeItem(self, name: str) -> QtWidgets.QTreeWidgetItem:
        shape = self._dataShapes.get(name, tuple())
        label = f"{self._dataStructure.label(name)}"
        axlabels = [str(self._dataStructure.label(d)) for d in
                    self._dataStructure.axes(name)]
        deps = ", ".join(axlabels)

        return QtWidgets.QTreeWidgetItem([
            label, deps, str(shape)
        ])

    @Slot(int)
    def _processCbChange(self, _: int) -> None:
        self.emitSelection()

    def _populate(self) -> None:
        for n in self._dataStructure.dependents():
            item = self._makeItem(n)
            # for ax in self._dataStructure.axes(n):
            #     child = self._makeItem(ax)
            #     item.addChild(child)
            self.addTopLevelItem(item)
            self.dataItems[n] = item

        for i in range(3):
            self.resizeColumnToContents(i)

    def setData(self, structure: DataDictBase, shapes: dict) -> None:
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

    def setShape(self, shape: Dict[str, Tuple[int, ...]]) -> None:
        """Set shapes of given elements"""
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            name = item.text(0)
            if name in shape:
                item.setText(2, str(shape[name]))

    def clear(self) -> None:
        """Clear the tree, and make sure all selections are cleared."""
        self.dataItems = {}
        super().clear()

    def setItemEnabled(self, name: str, enable: bool = True) -> None:
        """Enable/Disable a tree item by name"""
        # item = self.findItems(name, QtCore.Qt.MatchExactly, 1)[0]
        item = self.dataItems[name]
        item.setDisabled(not enable)
        if not enable:
            item.setSelected(False)

    def nameFromItem(self, item: QtWidgets.QTreeWidgetItem) -> str:
        for k, v in self.dataItems.items():
            if item is v:
                return k

        raise RuntimeError(f'Item {item} not registered.')

    def getSelectedData(self) -> List[str]:
        """Return a list of currently selected items (by name)"""
        ret = []
        for w in self.selectedItems():
            ret.append(self.nameFromItem(w))
        return ret

    def setSelectedData(self, vals: List[str]) -> None:
        """select all given items, uncheck all others."""
        for n, w in self.dataItems.items():
            w.setSelected(n in vals)

    def emitSelection(self) -> None:
        """emit the signal ``selectionChanged`` with the current selection"""
        self.dataSelectionMade.emit(self.getSelectedData())
