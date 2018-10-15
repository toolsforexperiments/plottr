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


def sliceAxis(arr, sliceObj, axis):
    """
    return the array where the axis with the given index is sliced
    with the given slice object.
    """
    slices = [np.s_[::] for i in arr.shape]
    slices[axis] = sliceObj
    return arr[tuple(slices)]

def selectAxisElement(arr, index, axis):
    """
    return the squeezed array where the given axis has been reduced to its
    value with the given index.
    """
    return np.squeeze(sliceAxis(arr, np.s_[index:index+1:], axis))


class DimensionReducer(Node):
    """
    A Node that allows the user to reduce the dimensionality of input data.

    Each axis can be assigned an arbitrary reduction function that will reduce the
    axis to a single value. For each assigned reduction the dimension shrinks by 1.

    If the input is not GridData, data is just passed through, but we delete the
    axes present in reductions.

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
        self._protectedAxes = []

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

        if not isinstance(data, GridDataDict):
            self.logger().debug(f"Data is not on a grid. Reduction functions are ignored, axes will simply be removed.")

        for n in dnames:
            for ax, reduction in self._reductions.items():
                fun, arg, kw = reduction
                try:
                    idx = data[n]['axes'].index(ax)
                except IndexError:
                    self.logger().info(f'{ax} specified for reduction, but not present in data; ignore.')

                kw['axis'] = idx

                if isinstance(data, GridDataDict):
                    # check that the new shape is actually correct
                    # get target shape by removing the right axis
                    targetShape = list(data[n]['values'].shape)
                    del targetShape[idx]
                    targetShape = tuple(targetShape)

                    newvals = fun(data[n]['values'], *arg, **kw)
                    if newvals.shape != targetShape:
                        self.logger().error(
                            f'Reduction on axis {ax} did not result in the right data shape. ' +
                            f'Expected {targetShape} but got {newvals.shape}.'
                            )
                        return None
                    data[n]['values'] = newvals

                del data[n]['axes'][idx]

        data.remove_unused_axes()
        data.validate()
        return data


    def validateOptions(self, data):
        """
        Checks performed:
        * each item in reduction must be of the form (fun, [*arg], {**kw}),
          with arg and kw being optional.
        """
        for ax, reduction in self._reductions.items():
            try:
                fun = reduction[0]
                if len(reduction) == 1:
                    arg = []; kw = {}
                elif len(reduction) == 2:
                    arg = reduction[1]; kw = {}
                else:
                    arg = reduction[1]; kw = reduction[2]
            except:
                self.logger().warning(f'Reduction for axis {ax} not in the right format.')
                return False

            self._reductions[ax] = (fun, arg, kw)

        return True

    def process(self, **kw):
        data = super().process(**kw)
        if data is None:
            return None

        data = self._applyDimReductions(copy.deepcopy(data['dataOut']))

        if data is None:
            return None
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
        super().__init__(*arg, **kw)

        self._xyAxes = None, None

    @property
    def xyAxes(self):
        return self._xyAxes

    @xyAxes.setter
    @Node.updateOption('xyAxes')
    def xyAxes(self, val):
        self._xyAxes = val

    def validateOptions(self, data):
        """
        Checks performed:
        * values for xAxis and yAxis must be axes that exist for the input data.
        * x/y axes cannot be the same
        * x/y axes cannot be reduced (will be removed from reductions)
        * all axes that are not x/y must be reduced (defaulting to selection of the first element)
        """
        if not super().validateOptions(data):
            return False

        availableAxes = data.axes_list()
        if self._xyAxes[0] is None:
            self.logger().debug(f'x-Axis is None. this will result in empty output data.')
            return False
        elif self._xyAxes[0] not in availableAxes:
            self.logger().warning(f'x-Axis {self._xyAxis[0]} not present in data')
            return False

        if self._xyAxes[1] is None:
            self.logger().debug(f'y-Axis is None; result will be 1D')
        elif self._xyAxes[1] not in availableAxes:
            self.logger().warning(f'y-Axis {self._xyAxes[1]} not present in data')
            return False
        elif self._xyAxes[1] == self._xyAxes[0]:
            self.logger().warning(f"y-Axis cannot be equal to x-Axis.")
            return False

        delete = []
        for n, _ in self.reductions.items():
            if n in self._xyAxes:
                self.logger().debug(f"{n} has been selected as axis, cannot be reduced.")
                delete.append(n)
        for n in delete:
            del self._reductions[n]

        for ax in availableAxes:
            if ax not in self._xyAxes and ax not in self.reductions:
                self.logger().debug(f"{ax} must be reduced. Default to selecting first element.")
                self._reductions[ax] = (selectAxisElement, [], dict(index=0))

        return True

    def process(self, **kw):
        data = super().process(**kw)
        if data is None:
            return None

        data = data['dataOut']
        if self._xyAxes[0] is not None and self._xyAxes[1] is not None:
            _kw = {self._xyAxes[0]: 0, self._xyAxes[1]: 1}
            data.reorder_axes(**_kw)

        return dict(dataOut=data)

