"""
data_selector.py

A node and widget for subselecting from a dataset.
"""
from pprint import pprint
import copy

import numpy as np

from pyqtgraph import Qt
from pyqtgraph.Qt import QtGui, QtCore

from .node import Node
from ..data import datadict as dd
from ..data.datadict import DataDict

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'

# TODO: only display lenght of respective axis in shape (if data on grid)

class DataTable(QtGui.QTreeWidget):

    selectionChanged = QtCore.pyqtSignal(list)

    def __init__(self, parent=None, readonly=True):
        super().__init__(parent)

        self.setColumnCount(4)
        self.setHeaderLabels(['', 'Name', 'Shape', 'Unit'])
        self.checkBoxes = {}
        self._emitSelection = True

    def setData(self, struct, readonly):
        for n in struct.dependents():
            item = self._makeItem(struct, n)
            axes = struct[n]['axes']
            for ax in axes:
                child = self._makeItem(struct, ax)
                item.addChild(child)
            self.addTopLevelItem(item)

            if not readonly:
                chk = QtGui.QCheckBox()
                self.setItemWidget(item, 0, chk)
                self.checkBoxes[n] = chk
                chk.stateChanged.connect(self.signalSelection)

        for i in range(4):
            self.resizeColumnToContents(i)

    def _makeItem(self, struct, name):
        return QtGui.QTreeWidgetItem([
            '', name, str(struct[name].get('__shape__', '')),
                struct[name]['unit']
            ])

    def setItemEnabled(self, name, enable=True):
        item = self.findItems(name, QtCore.Qt.MatchExactly, 1)[0]
        item.setDisabled(not enable)
        self.checkBoxes[name].setDisabled(not enable)

    def getSelected(self):
        ret = []
        for n, w in self.checkBoxes.items():
            if w.isChecked():
                ret.append(n)
        return ret

    def clear(self):
        for n, w in self.checkBoxes.items():
            w.setChecked(False)
        super().clear()

    def clearSelected(self, emit=True):
        if not emit:
            self._emitSelection = False
        for n, w in self.checkBoxes.items():
            w.setChecked(False)

        self._emitSelection = True

    def setSelected(self, names):
        self._emitSelection = False
        for n, w in self.checkBoxes.items():
            if n in names:
                w.setChecked(True)
            else:
                w.setChecked(False)
        self._emitSelection = True

    def signalSelection(self):
        if self._emitSelection:
            selected = self.getSelected()
            # print('emit', selected)
            self.selectionChanged.emit(selected)


class DataDisplayWidget(QtGui.QWidget):

    dataSelected = QtCore.pyqtSignal(list)

    def __init__(self, parent=None, readonly=False, **kw):
        super().__init__(parent=parent, **kw)

        self._readonly = readonly
        self._selectedData = []
        self._dataStructure = None

        self.tbl = DataTable(self, readonly=readonly)
        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.tbl)

        # if not readonly:
        #     self.gridchk = QtGui.QCheckBox()
        #     self.gridlbl = QtGui.QLabel('Place data on grid')
        #     gridlayout = QtGui.QFormLayout()
        #     gridlayout.addRow(self.gridlbl, self.gridchk)
        #     layout.addLayout(gridlayout)

        layout.addStretch()
        self.setLayout(layout)

    @QtCore.pyqtSlot(object)
    def setDataStructure(self, structure):
        self._dataStructure = structure
        self.tbl.clear()

        if structure is not None:
            self.tbl.setData(structure, self._readonly)
            self.tbl.selectionChanged.connect(self.emitDataSelection)

    @QtCore.pyqtSlot(list)
    def emitDataSelection(self, selected):
        self.dataSelected.emit(selected)

    @QtCore.pyqtSlot(list)
    def updateOptions(self, selected):
        ds = self._dataStructure
        for n, w in self.tbl.checkBoxes.items():
            if selected != [] and ds[n]['axes'] != ds[selected[0]]['axes']:
                self.tbl.setItemEnabled(n, False)
            else:
                self.tbl.setItemEnabled(n, True)

    def setSelected(self, selected):
        self.tbl.setSelected(selected)
        self.updateOptions(selected)


class DataSelector(Node):

    nodeName = "DataSelector"
    uiClass = DataDisplayWidget

    guiOptions = {
        # 'grid' : {
        #     'widget' : 'gridchk',
        #     'setFunc' : 'setChecked',
        # },
        'selectedData' : {
            'widget' : None,
            'setFunc' : 'setSelected',
        },
    }

    newDataStructure = QtCore.pyqtSignal(object)

    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)

        self._selectedData = []
        self._dataStructure = None

    ### Properties

    @property
    def selectedData(self):
        return self._selectedData

    @selectedData.setter
    @Node.updateOption('selectedData')
    def selectedData(self, val):
        """
        Set the selected data fields to val, which is a list of names of the fields.
        Checks if the datafields are compatible in axes and will raise ValueError
        if not (selection is not possible then).
        """
        if isinstance(val, str):
            val = [val]

        vals = []
        if len(val) > 0:
            allowed_axes = self._dataStructure[val[0]]['axes']
            for v in val:
                axes = self._dataStructure[v]['axes']
                if axes == allowed_axes:
                    vals.append(v)
                else:
                    raise ValueError(f'Datasets {vals[0]}(with axes {allowed_axes}) '
                                     f'and {v}(with axes {axes}) are not compatible '
                                     f'and cannot be selected simultanously.')

        self._selectedData = vals

    ### Data processing

    def _reduceData(self, data):
        if isinstance(self.selectedData, str):
            dnames = [self.selectedData]
        else:
            dnames = self.selectedData

        # if self.grid or isinstance(data, GridDataDict):
        #     _data = togrid(data, names=dnames)
        # else:
        # _data = DataDict()
        # for n in dnames:
        #     _data[n] = data[n]
        #     for k, v in data.items():
        #         if k in data[n].get('axes', []):
        #             _data[k] = v
        # return _data

        return data.extract(dnames)

    def process(self, **kw):
        data = kw['dataIn']

        if data is None:
            struct = None
        else:
            struct = data.structure()

        if not DataDict.same_structure(struct, self._dataStructure):
            self._dataStructure = struct
            self.newDataStructure.emit(struct)

        # if isinstance(data, GridDataDict) and self.ui is not None:
        #     self.ui.gridchk.setDisabled(True)
        # elif not isinstance(data, GridDataDict) and self.ui is not None:
        #     self.ui.gridchk.setDisabled(False)

        data = self._reduceData(data)
        return dict(dataOut=data)


    ### Methods for GUI interaction

    def setupUi(self):
        self.newDataStructure.connect(self.ui.setDataStructure)
        # self.ui.gridchk.setChecked(self._grid)
        # self.ui.gridchk.stateChanged.connect(self._setGrid)
        self.ui.dataSelected.connect(self._setSelected)

    # @QtCore.pyqtSlot(int)
    # def _setGrid(self, val):
    #     self.grid = bool(val)

    @QtCore.pyqtSlot(list)
    def _setSelected(self, vals):
        self.selectedData = vals
