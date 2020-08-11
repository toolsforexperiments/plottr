import os
from enum import Enum
from typing import List, Any, Optional, Dict, Sequence
from pprint import pprint

from plottr import QtCore, QtGui, QtWidgets, Slot, Signal
from plottr.data.datadict import DataDict


def findFilesByExtension(path: str, extensions: Sequence[str]) -> List[str]:
    ret: List[str] = []
    contents = os.listdir(path)
    for c in sorted(contents):
        abspath = os.path.abspath(os.path.join(path, c))
        if os.path.isdir(abspath):
            ret_ = findFilesByExtension(abspath, extensions)
            if len(ret_) > 0:
                ret += ret_
        else:
            if os.path.splitext(c)[-1] in extensions:
                ret += [abspath]
    return ret


class DataFileContent(QtWidgets.QTreeWidget):

    #: Signal(str) -- Emitted when the user requests a plot for datadict
    #: Arguments:
    #:   - name of the group within the currently selected file
    plotRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.data = {}
        self.groupItems = []
        self.selectedGroup = None

        self.dataPopup = QtWidgets.QMenu('Data actions', self)
        self.plotAction = self.dataPopup.addAction("Plot")
        self.plotAction.triggered.connect(self.onPlotActionTriggered)


    @Slot(object)
    def setData(self, data: Dict[str, DataDict]):
        """Set the data to display."""
        self.clear()
        self.data = {}
        self.groupItems = []

        for grpName, grpData in data.items():
            self.data[grpName] = data[grpName]
            grpItem = QtWidgets.QTreeWidgetItem(self, [grpName])
            self.groupItems.append(grpItem)
            self.addTopLevelItem(grpItem)
            dataParent = QtWidgets.QTreeWidgetItem(grpItem, ['[DATA]'])
            metaParent = QtWidgets.QTreeWidgetItem(grpItem, ['[META]'])

            for dn, dv in grpData.data_items():
                vals = [grpData.label(dn), str(grpData.meta_val('shape', dn))]
                if dn in grpData.dependents():
                    vals.append(f'Data (depends on {str(tuple(grpData.axes(dn)))[1:]}')
                else:
                    vals.append('Data (independent)')
                ditem = QtWidgets.QTreeWidgetItem(dataParent, vals)

                for mn, mv in grpData.meta_items(dn):
                    vals = [mn, str(mv)]
                    _ = QtWidgets.QTreeWidgetItem(ditem, vals)

            for mn, mv in grpData.meta_items():
                vals = [mn, str(mv)]
                _ = QtWidgets.QTreeWidgetItem(metaParent, vals)

            grpItem.setExpanded(True)
            dataParent.setExpanded(True)

        for i in range(self.columnCount()-1):
            self.resizeColumnToContents(i)

    @Slot(QtCore.QPoint)
    def onCustomContextMenuRequested(self, pos):
        item = self.itemAt(pos)
        if item not in self.groupItems:
            return

        self.selectedGroup = item.text(0)
        self.plotAction.setText(f"Plot '{item.text(0)}'")
        self.dataPopup.exec(self.mapToGlobal(pos))

    @Slot()
    def onPlotActionTriggered(self):
        self.plotRequested.emit(self.selectedGroup)


class DataFileList(QtWidgets.QTreeWidget):
    """A Tree Widget that displays all data files that are in a certain
    base directory. All subfolders are monitored.
    """

    fileExtensions = ['.ddh5']

    #: Signal(str) -- emitted when a data file is selected
    #: Arguments:
    #:   - the absolute path of the data file
    dataFileSelected = Signal(str)

    #: Signal(list) -- emitted when new files have been found
    newDataFilesFound = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.files = []
        self.path = None

    @staticmethod
    def find(parent, name):
        if isinstance(parent, DataFileList):
            existingItems = [parent.topLevelItem(i) for i in
                             range(parent.topLevelItemCount())]
        else:
            existingItems = [parent.child(i) for i in
                             range(parent.childCount())]

        item = None
        for item_ in existingItems:
            if item_.text(0) == name:
                item = item_
                break
        return item

    def itemPath(self, item):
        def buildPath(i, suffix=''):
            if i is None:
                return suffix
            newSuffix = i.text(0)
            if suffix != '':
                newSuffix += os.path.sep+suffix
            return buildPath(i.parent(), suffix=newSuffix)
        return os.path.join(self.path, buildPath(item))

    def findItemByPath(self, path: str):
        path = path[len(self.path) + len(os.path.sep):]
        pathList = path.split(os.path.sep)
        parent = self
        for p in pathList:
            parent = self.find(parent, p)
            if parent is None:
                return None
        return parent

    def addItemByPath(self, path: str):
        path = path[len(self.path)+len(os.path.sep):]
        pathList = path.split(os.path.sep)

        def add(parent, name):
            item = self.find(parent, name)
            if item is None:
                item = QtWidgets.QTreeWidgetItem(parent, [name])
                if os.path.splitext(name)[-1] in self.fileExtensions:
                    fnt = QtGui.QFont()
                    item.setFont(0, fnt)
                else:
                    pass
                if isinstance(parent, DataFileList):
                    parent.addTopLevelItem(item)
                else:
                    parent.addChild(item)
            return item

        parent = self
        for p in pathList:
            parent = add(parent, p)

    def removeItemByPath(self, path: str):

        def remove(i):
            parent = i.parent()
            if isinstance(parent, DataFileList):
                idx = parent.indexOfTopLevelItem(i)
                parent.takeTopLevelItem(idx)
            elif isinstance(parent, QtWidgets.QTreeWidgetItem):
                parent.removeChild(i)
                if parent.childCount() == 0:
                    remove(parent)

        item = self.findItemByPath(path)
        if item is None:
            return
        remove(item)

    def loadFromPath(self, path: str, emitNew: bool = False):
        self.path = path
        files = findFilesByExtension(path, self.fileExtensions)
        newFiles = [f for f in files if f not in self.files]
        removedFiles = [f for f in self.files if f not in files]

        for f in newFiles:
            self.addItemByPath(f)

        for f in removedFiles:
            self.removeItemByPath(f)

        self.files = files
        if len(newFiles) > 0 and emitNew:
            self.newDataFilesFound.emit(newFiles)

    @Slot()
    def processSelection(self):
        selected = self.selectedItems()
        if len(selected) == 0:
            return
        nameAndExt = os.path.splitext(selected[0].text(0))
        if nameAndExt[-1] in self.fileExtensions:
            path = self.itemPath(selected[0])
            self.dataFileSelected.emit(path)


class MonitorToolBar(QtWidgets.QToolBar):
    pass
