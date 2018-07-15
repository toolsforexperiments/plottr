"""
node.py

Contains the base class for Nodes, and some basic nodes for data analysis.
"""
import copy
from pprint import pprint

import numpy as np

from pyqtgraph.flowchart import Flowchart, Node as pgNode
from pyqtgraph.Qt import QtGui, QtCore

from .data.datadict import togrid, DataDict, GridDataDict


__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'

class Node(pgNode):

    raiseExceptions = False
    nodeName = "DataDictNode"
    terminals = {
        'dataIn' : {'io' : 'in'},
        'dataOut' : {'io' : 'out'},
    }

    def __init__(self, name):
        super().__init__(name, terminals=self.__class__.terminals)

        self.signalUpdate = True
        self._grid = False
        self._selectedData = None

    def updateOption(func):
        def wrap(self, val):
            ret = func(self, val)
            self.update(self.signalUpdate)
            return ret
        return wrap

    def update(self, signal=True):
        super().update(signal=signal)
        if Node.raiseExceptions and self.exception is not None:
            raise self.exception[1]

    @property
    def grid(self):
        return self._grid

    @grid.setter
    @updateOption
    def grid(self, val):
        self._grid = val

    def process(self, **kw):
        data = kw['dataIn']
        if self.grid:
            data = togrid(data)

        return dict(dataOut=data)


class DataSelector(Node):

    nodeName = "DataSelector"

    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)

        self._grid = True
        self._selectedData = []
        self._slices = {}
        self._axesOrder = {}
        self._squeeze = True

    @property
    def slices(self):
        return self._slices

    @slices.setter
    @Node.updateOption
    def slices(self, val):
        self._slices = val

    @property
    def axesOrder(self):
        return self._axesOrder

    @axesOrder.setter
    @Node.updateOption
    def axesOrder(self, val):
        self._axesOrder = val

    @property
    def squeeze(self):
        return self._squeeze

    @squeeze.setter
    @Node.updateOption
    def squeeze(self, val):
        self._squeeze = val

    @property
    def selectedData(self):
        return self._selectedData

    @selectedData.setter
    @Node.updateOption
    def selectedData(self, val):
        self._selectedData = val

    def _sliceData(self, data):
        axnames = data[data.dependents()[0]]['axes']
        slices = [np.s_[::] for a in axnames]
        for n, s in self.slices.items():
            idx = axnames.index(n)
            slices[idx] = s
            data[n]['values'] = data[n]['values'][s]

        for n in self.selectedData:
            data[n]['values'] = data[n]['values'][slices]

        return data

    def _reorderData(self, data):
        axnames = data[data.dependents()[0]]['axes']
        neworder = [None for a in axnames]
        oldorder = list(range(len(axnames)))
        for n, newidx in self.axesOrder.items():
            neworder[newidx] = axnames.index(n)

        for i in neworder:
            if i in oldorder:
                del oldorder[oldorder.index(i)]

        for i in range(len(neworder)):
            if neworder[i] is None:
                neworder[i] = oldorder[0]
                del oldorder[0]

        for n in self.selectedData:
            data[n]['values'] = data[n]['values'].transpose(tuple(neworder))
            data[n]['axes'] = [axnames[i] for i in neworder]

        return data

    def _squeezeData(self, data):
        oldshape = data[data.dependents()[0]]['values'].shape
        axnames = data[data.dependents()[0]]['axes']

        for m in data.dependents():
            data[m]['values'] = np.squeeze(data[m]['values'])
            for i, n in enumerate(axnames):
                if oldshape[i] < 2:
                    del data[m]['axes'][i]
                    del data[n]

        return data

    def process(self, **kw):
        data = kw['dataIn']

        if isinstance(self.selectedData, str):
            dnames = [self.selectedData]
        else:
            dnames = self.selectedData

        if self.grid:
            data = togrid(data, names=dnames)
        else:
            _data = DataDict()
            for n in dnames:
                _data[n] = data[n]
                for k, v in data.items():
                    if k in data[n].get('axes', []):
                        _data[k] = v
            data = _data

        if self.grid and len(data.dependents()) > 0:
            if self.slices != {}:
                data = self._sliceData(data)
            if self.axesOrder != {}:
                data = self._reorderData(data)
            if self.squeeze:
                data = self._squeezeData(data)

        return dict(dataOut=data)
