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
from ..data.datadict import togrid, DataDict, GridDataDict

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


class DataSelectorWidget(QtGui.QWidget):

    dataSelected = QtCore.pyqtSignal(list)

    def __init__(self, parent=None, **kw):
        super().__init__(parent=parent, **kw)

        self._triggerUpdateSelectables = True
        self._dataOptions = {}
        self._selectedData = []
        self._dataStructure = None

        self.dataLayout = QtGui.QFormLayout()
        dataGroup = QtGui.QGroupBox('Data selection')
        dataGroup.setLayout(self.dataLayout)

        gridLayout = QtGui.QFormLayout()
        self.gridchk = QtGui.QCheckBox()
        gridLayout.addRow('Make grid', self.gridchk)

        layout = QtGui.QVBoxLayout(self)
        layout.addLayout(gridLayout)
        layout.addWidget(dataGroup)


    def _deleteDataOptions(self, names):
        for name in names:
            v = self._dataOptions[name]
            self.dataLayout.removeWidget(v['widget'])
            self.dataLayout.removeWidget(v['label'])
            v['widget'].deleteLater()
            v['label'].deleteLater()
            del self._dataOptions[name]

    def getSelected(self):
        ret = []
        for n, v in self._dataOptions.items():
            if v['widget'].isChecked():
                ret.append(n)
        return ret

    def setSelected(self, names):
        for n, v in self._dataOptions.items():
            if n in names:
                v['widget'].setChecked(True)
            else:
                v['widget'].setChecked(False)


    @QtCore.pyqtSlot(object)
    def setDataStructure(self, structure):
        self._dataStructure = structure

        delete = []
        for k, v in self._dataOptions.items():
            delete.append(k)
        self._deleteDataOptions(delete)

        if structure is not None:
            for n in structure.dependents():
                if n not in self._dataOptions:
                    lbl = QtGui.QLabel(n)
                    chk = QtGui.QCheckBox()
                    self._dataOptions[n] = dict(label=lbl, widget=chk)
                    self.dataLayout.addRow(lbl, chk)
                    chk.stateChanged.connect(lambda x: self.updateDataSelection())

    @QtCore.pyqtSlot()
    def updateDataSelection(self):
        selected = []

        for k, v in self._dataOptions.items():
            if v['widget'].isChecked():
                selected.append(k)

        ds = self._dataStructure
        for k, v in self._dataOptions.items():
            if selected != [] and ds.axes_list(k) != ds.axes_list(selected[0]):
                    self._dataOptions[k]['widget'].setDisabled(True)
            else:
                self._dataOptions[k]['widget'].setDisabled(False)

        self.dataSelected.emit(selected)


class DataSelector(Node):

    nodeName = "DataSelector"
    uiClass = DataSelectorWidget

    guiOptions = {
        'grid' : {
            'widget' : 'gridchk',
            'setFunc' : 'setChecked',
        },
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

        self.grid = True

    def setupUi(self):
        self.newDataStructure.connect(self.ui.setDataStructure)
        self.ui.gridchk.setChecked(self._grid)
        self.ui.gridchk.stateChanged.connect(self._setGrid)
        self.ui.dataSelected.connect(self._setSelected)

    @QtCore.pyqtSlot(int)
    def _setGrid(self, val):
        self.grid = bool(val)

    @QtCore.pyqtSlot(list)
    def _setSelected(self, vals):
        self.selectedData = vals

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
            allowed_axes = self._dataStructure.axes_list(val[0])
            for v in val:
                axes = self._dataStructure.axes_list(v)
                if axes == allowed_axes:
                    vals.append(v)
                else:
                    raise ValueError(f'Datasets {vals[0]}(with axes {allowed_axes})'
                                     f'and {v}(with axes {axes}) are not compatible'
                                     f'and cannot be selected simultanously.')

        self._selectedData = vals

    def _reduceData(self, data):
        if isinstance(self.selectedData, str):
            dnames = [self.selectedData]
        else:
            dnames = self.selectedData

        if self.grid or isinstance(data, GridDataDict):
            _data = togrid(data, names=dnames)
        else:
            _data = DataDict()
            for n in dnames:
                _data[n] = data[n]
                for k, v in data.items():
                    if k in data[n].get('axes', []):
                        _data[k] = v
        return _data

    def process(self, **kw):
        data = kw['dataIn']

        if data is None:
            struct = None
        else:
            struct = data.structure(meta=False)

        if struct != self._dataStructure:
            self._dataStructure = struct
            self.newDataStructure.emit(struct)

        if isinstance(data, GridDataDict) and self.ui is not None:
            self.ui.gridchk.setDisabled(True)
        elif not isinstance(data, GridDataDict) and self.ui is not None:
            self.ui.gridchk.setDisabled(False)

        data = self._reduceData(data)
        return dict(dataOut=data)
