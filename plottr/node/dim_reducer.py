"""
xy_axes_selector.py

A node and widget for reducing data to 1d/2d data.
"""
import copy
from pprint import pprint

import numpy as np

from pyqtgraph import Qt
from pyqtgraph.Qt import QtGui, QtCore

from .node import Node
from ..data.datadict import togrid, DataDict, GridDataDict

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


def selectAxisElement(arr, axis=0, index=0):
    """
    return the squeezed array where the given axis has been reduced to its
    value with the given index.
    """
    slices = [np.s_[::] for i in arr.shape]
    slices[axis] = np.s_[index:index+1:]
    return np.squeeze(arr[slices])


class DimensionReducer(Node):
    """
    A Node that allows the user to reduce the dimensionality of input data.

    Each axis can be assigned an arbitrary reduction function that will reduce the
    axis to a single value. For each assigned reduction the dimension shrinks by 1.

    If the input is not GridData, data is simply passed through.

    Reductions affect all data fields that are given to the property targetNames (as list).
    if targetNames is None (default), then we'll try to apply the reduction to all
    dependents.

    Reductions can be set as property, as a dictionary in the format
        {'axis_name' : (function, [args], {kwargs}), ... }.
    args and kwargs are optional.
    The function's first arg must be the data array, and it must accept a
    kwarg 'axis' (int), and reduce the data dimension by 1 by removing the given axis.
    """

    nodeName = 'DimensionReducer'

    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)

        self._reductions = {}
        self._targetNames = None

    @property
    def reductions(self):
        return self._reductions

    @reductions.setter
    @Node.updateOption()
    def reductions(self, val):
        self._reductions = val

    @property
    def targetNames(self):
        return self._targetNames

    @targetNames.setter
    @Node.updateOption()
    def targetNames(self, val):
        self._targetNames = val

    def _applyDimReductions(self, data):
        if self._targetNames is not None:
            dnames = self._targetNames
        else:
            dnames = data.dependents()

        for n in dnames:
            for ax, reduction in self._reductions.items():
                fun = reduction[0]
                if len(reduction) == 1:
                    arg = []; kw = {}
                elif len(reduction) == 2:
                    arg = reduction[1]; kw = {}
                else:
                    arg = reduction[1]; kw = reduction[2]

                idx = data[n]['axes'].index(ax)
                kw['axis'] = idx
                data[n]['values'] = fun(data[n]['values'], *arg, **kw)
                del data[n]['axes'][idx]

        data.remove_unused_axes()
        data.validate()
        return data

    def process(self, **kw):
        data = kw['dataIn']

        if not isinstance(data, GridDataDict):
            return dict(dataOut=data)

        data = self._applyDimReductions(copy.deepcopy(data))
        return dict(dataOut=data)



class XYAxesSelector(DimensionReducer):
    """
    A Node that allows the user to select one or two axes (x and/or y); these
    will be only remaining axes after processing, i.e., the output is either 1d
    or 2d.

    Basic behavior:
    * if the input is GridData, then we can select x and or y, and apply a reduction
      function over any unselected axis; this could, eg, be selecting a single-value slice,
      averaging, integration, ... The output is then a 1d or 2d dataset with x and/or y axis.
    * if the input is non-GridData, then we simply discard the non-x/y axes.
    """

    nodeName = 'XYAxesSelector'

    def __init__(self, *arg, **kw):
        super().__init__(self, *arg, **kw)

        self._xAxis = None
        self._yAxis = None

    def process(self, **kw):
        data = copy.deepcopy(kw['dataIn'])

        # no x-axis is invalid. because i say so.
        if self._xSelection in ['', None]:
            return dict(dataOut=DataDict())

