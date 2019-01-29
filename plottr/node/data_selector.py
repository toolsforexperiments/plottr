"""
data_selector.py

A node and widget for subselecting from a dataset.
"""
from pprint import pprint
import copy
from typing import Union, List, Tuple, Dict

import numpy as np

from pyqtgraph import Qt
from pyqtgraph.Qt import QtGui, QtCore

from .node import Node, NodeWidget
from ..data import datadict as dd
from ..data.datadict import DataDict
from ..utils import num

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'

class DataDisplayWidget(QtGui.QTreeWidget, NodeWidget):
    """
    Simple Tree widget to show data and their dependencies in the node data.
    """

    dataSelected = QtCore.pyqtSignal(list)
    selectionChanged = QtCore.pyqtSignal(list)

    def __init__(self, parent: QtGui.QWidget = None, readonly: bool = False):
        super().__init__(parent)

        self.setColumnCount(4)
        self.setHeaderLabels(['', 'Name', 'Shape', 'Unit'])
        self.checkBoxes = {}
        self._emitSelection = True
        self._readonly = readonly

    def setData(self, struct):
        self._dataStructure = struct
        self.clear()

        if struct is not None:
            for n in struct.dependents():
                item = self._makeItem(struct, n)
                axes = struct[n]['axes']
                for ax in axes:
                    child = self._makeItem(struct, ax)
                    item.addChild(child)
                self.addTopLevelItem(item)

                if not self._readonly:
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

    def setShape(self, shape: Dict[str, Tuple[int, ...]]):
        for n, s in shape.items():
            items = self.findItems(n, QtCore.Qt.MatchExactly, 1)
            if len(items) > 0:
                items[0].setText(2, str(s))

    @NodeWidget.emitGuiUpdate('selectionChanged')
    def signalSelection(self, _val):
        return self.getSelected()

    @NodeWidget.updateGuiFromNode
    def setSelected(self, names):
        for n, w in self.checkBoxes.items():
            if n in names:
                w.setChecked(True)
            else:
                w.setChecked(False)
        self._updateOptions(names)

    def _updateOptions(self, selected):
        ds = self._dataStructure
        for n, w in self.checkBoxes.items():
            if selected != [] and ds[n]['axes'] != ds[selected[0]]['axes']:
                self.setItemEnabled(n, False)
            else:
                self.setItemEnabled(n, True)


class DataSelector(Node):
    """
    This node allows extracting data from datasets. The fields specified by
    `selectedData' and their axes are kept, the rest is discarded in the output.
    All selected data fields must be compatible in the sense that they have the
    same axes (also in the same order).
    The utility of this node is that afterwards data can safely be processed
    together, as the structure of all remaining fields is shared.

    Properties of this node:
        * selectedData : a list/tuple of data field names
    """

    # TODO: allow the user to control dtypes.

    nodeName = "DataSelector"
    uiClass = DataDisplayWidget

    guiOptions = {
        'selectedData' : {
            'widget' : None,
            'setFunc' : 'setSelected',
        },
    }

    newDataStructure = QtCore.pyqtSignal(object)
    dataShapeChanged = QtCore.pyqtSignal(object)

    force_numerical_data = True

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
    def selectedData(self, val: List[str]):
        """
        Set the selected data fields to val, which is a list of names of the fields.
        Checks if the datafields are compatible in axes and will raise ValueError
        if not (selection is not possible then).
        """
        if isinstance(val, str):
            val = [val]

        self._selectedData = val

    ### Data processing

    def validateOptions(self, data):
        """
        Validations performed:
        * only compatible data fields can be selected.
        """
        if data is None:
            return True

        if len(self.selectedData) > 0:
            allowed_axes = data.axes(self.selectedData[0])
            for d in self.selectedData:
                if data.axes(d) != allowed_axes:
                    self.logger().error(
                        f'Datasets {self.selectedData[0]} (with axes {allowed_axes}) '
                        f'and {d}(with axes {data.axes(d)}) are not compatible '
                        f'and cannot be selected simultaneously.'
                        )
                    return False
        return True

    def _reduceData(self, data):
        if isinstance(self.selectedData, str):
            dnames = [self.selectedData]
        else:
            dnames = self.selectedData
        if len(self.selectedData) == 0:
            return None

        ret = data.extract(dnames)
        if self.force_numerical_data:
            for d, _ in ret.data_items():
                dt = num.largest_numtype(ret.data_vals(d),
                                         include_integers=False)
                if dt is not None:
                    ret[d]['values'] = ret[d]['values'].astype(dt)
                else:
                    return None

        return ret

    def process(self, **kw):
        data = super().process(**kw)
        if data is None:
            return None
        data = data['dataOut']

        # this is for the UI
        struct = data.structure()
        if not DataDict.same_structure(struct, self._dataStructure):
            self._dataStructure = struct
            self.newDataStructure.emit(struct)
        self.dataShapeChanged.emit(data.shapes())

        # this is the actual operation of the node
        data = self._reduceData(data)
        if data is None:
            return None

        return dict(dataOut=data)

    ### Methods for GUI interaction

    def setupUi(self):
        self.newDataStructure.connect(self.ui.setData)
        self.dataShapeChanged.connect(self.ui.setShape)
        self.ui.selectionChanged.connect(self._setSelected)

    @QtCore.pyqtSlot(list)
    def _setSelected(self, vals):
        self.selectedData = vals
