"""dim_reducer.py

nodes and widgets for reducing data dimensionality.
"""
from enum import Enum

import numpy as np

from .node import Node, updateOption
from ..data.datadict import MeshgridDataDict
from .. import QtGui, QtCore

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


# Some helpful reduction functions

def sliceAxis(arr: np.ndarray, sliceObj: slice, axis: int) -> np.ndarray:
    """
    return the array where the axis with the given index is sliced
    with the given slice object.

    :param arr: input array
    :param sliceObj: slice object to use on selected dimension
    :param axis: dimension of the array to apply slice to
    :return: array after slicing
    """
    slices = [np.s_[::] for i in arr.shape]
    slices[axis] = sliceObj
    return arr[tuple(slices)]


def selectAxisElement(arr: np.ndarray, index: int, axis: int) -> np.ndarray:
    """
    return the squeezed array where the given axis has been reduced to its
    value with the given index.

    :param arr: input array
    :param index: index of the element to keep
    :param axis: dimension on which to perform the reduction
    :return: reduced array
    """
    return np.squeeze(sliceAxis(arr, np.s_[index:index+1:], axis))


# Translation between reduction functions and convenient naming

class ReductionMethod(Enum):
    """Built-in reduction methods"""
    elementSelection = 'select element'
    average = 'average'


#: mapping from reduction method Enum to functions
reductionFunc = {
    ReductionMethod.elementSelection: selectAxisElement,
    ReductionMethod.average: np.mean,
}


# def reductionFuncFromName(name):
#     return reductionFunc.get(name, None)
#
# def reductionNameFromFunc(func):
#     for n, f in reductionFunc.items():
#         if f == func:
#             return n
#     return None


class AxisOptionWidget(QtGui.QTreeWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setColumnCount(4)
        self.setHeaderLabels(['Axis', 'Setting', 'Options', 'Info'])

        self.choices = {}

        self._dataStructure = None
        self._dataType = None

    def clear(self):
        super().clear()

        for n, opts in self.choices.items():
            opts['settingWidget'].deleteLater()
            del opts['settingWidget']

        self.choices = {}

    def updateSizes(self):
        for i in range(4):
            self.resizeColumnToContents(i)


class DimensionReducer(Node):
    """
    A Node that allows the user to reduce the dimensionality of input data.

    Each axis can be assigned an arbitrary reduction function that will reduce
    the axis to a single value. For each assigned reduction the dimension
    shrinks by 1.

    If the input is not GridData, data is just passed through, but we delete the
    axes present in reductions.

    If the output contains invalid entries, they will be masked.

    Properties are:

    :targetNames: ``List[str]`` or ``None``.
        reductions affect all dependents that are given. If None, will apply
        to all dependents.
    :reductions: ``Dict[str, (callable, *args, **kwargs)]``
        reduction functions. Keys are the axis names the reductions are applied
        to; values are tuples of the reduction function, and optional
        arguments and kw-arguments.
        The function can also be via :class:`ReductionMethod`.
        The function must accept an ``axis = <int>`` keyword, and must return
        an array of dimensionality that is reduced by one compared to its
        input.
    """

    nodeName = 'DimensionReducer'

    def __init__(self, *arg, **kw):

        self._reductions = {}
        self._targetNames = None

        super().__init__(*arg, **kw)

    # Properties

    @property
    def reductions(self):
        return self._reductions

    @reductions.setter
    @updateOption('reductions')
    def reductions(self, val):
        self._reductions = val

    @property
    def targetNames(self):
        return self._targetNames

    @targetNames.setter
    @updateOption()
    def targetNames(self, val):
        self._targetNames = val

    # Data processing

    def _applyDimReductions(self, data):
        """Apply the reductions"""
        if self._targetNames is not None:
            dnames = self._targetNames
        else:
            dnames = data.dependents()

        if not isinstance(data, MeshgridDataDict):
            self.logger().debug(f"Data is not on a grid. "
                                f"Reduction functions are ignored, "
                                f"axes will simply be removed.")

        for n in dnames:
            for ax, reduction in self._reductions.items():
                if reduction is not None:
                    fun, arg, kw = reduction
                else:
                    fun, arg, kw = None, [], {}

                try:
                    idx = data[n]['axes'].index(ax)
                except IndexError:
                    self.logger().info(f'{ax} specified for reduction, '
                                       f'but not present in data; ignore.')

                kw['axis'] = idx

                # actual operation is only done if the data is on a grid.
                if isinstance(data, MeshgridDataDict):

                    # check that the new shape is actually correct
                    # get target shape by removing the right axis
                    targetShape = list(data[n]['values'].shape)
                    del targetShape[idx]
                    targetShape = tuple(targetShape)

                    # support for both pre-defined and custom functions
                    if isinstance(fun, ReductionMethod):
                        funCall = reductionFunc[fun]
                    else:
                        funCall = fun

                    newvals = funCall(data[n]['values'], *arg, **kw)
                    if newvals.shape != targetShape:
                        self.logger().error(
                            f'Reduction on axis {ax} did not result in the '
                            f'right data shape. ' +
                            f'Expected {targetShape} but got {newvals.shape}.'
                            )
                        return None
                    data[n]['values'] = newvals

                    # since we are on a meshgrid, we also need to reduce
                    # the dimensions of the coordinate meshes
                    for ax in data[n]['axes']:
                        if len(data.data_vals(ax).shape) > len(targetShape):
                            newaxvals = funCall(data[ax]['values'], *arg, **kw)
                            data[ax]['values'] = newaxvals

                del data[n]['axes'][idx]

        data = data.sanitize()
        data.validate()
        return data

    def validateOptions(self, data):
        """
        Checks performed:
        * each item in reduction must be of the form (fun, [*arg], {**kw}),
          with arg and kw being optional; if the tuple is has length 2,
          the second element is taken as the arg-list.
          The function can be of type :class:`.ReductionMethod`.
        """

        delete = []
        for ax, reduction in self._reductions.items():
            if reduction is None:
                if isinstance(data, MeshgridDataDict):
                    self.logger().warning(f'Reduction for axis {ax} is None. '
                                          f'Removing.')
                    delete.append(ax)
                else:
                    pass
                continue

            try:
                fun = reduction[0]
                if len(reduction) == 1:
                    arg = []
                    kw = {}
                elif len(reduction) == 2:
                    arg = reduction[1]
                    kw = {}
                else:
                    arg = reduction[1]
                    kw = reduction[2]
            except:
                self.logger().warning(
                    f'Reduction for axis {ax} not in the right format.'
                )
                return False

            if not callable(fun) and not isinstance(fun, ReductionMethod):
                self.logger().error(
                    f'Invalid reduction method for axis {ax}. '
                    f'Needs to be callable or a ReductionMethod type.'
                )

            self._reductions[ax] = (fun, arg, kw)

        for ax in delete:
            del self._reductions[ax]

        return True

    def process(self, **kw):
        data = super().process(**kw)
        if data is None:
            return None
        data = data['dataOut'].mask_invalid()
        data = self._applyDimReductions(data)

        if data is None:
            return None
        return dict(dataOut=data)


# class XYAxesSelectionWidget(QtGui.QTreeWidget):
#
#     options = ['', 'x-axis', 'y-axis', 'average', 'select value']
#     gridOnlyOptions = ['average', 'select value']
#
#     # signals for when the user has changed options via the UI.
#     xyAxesChanged = QtCore.pyqtSignal(tuple)
#     reductionsChanged = QtCore.pyqtSignal(dict)
#
#     def __init__(self, parent=None):
#         super().__init__(parent)
#
#         self.setColumnCount(4)
#         self.setHeaderLabels(['Axis', 'Role', 'Options', 'Info'])
#
#         self._dataStructure = None
#         self._grid = True
#         self._emitChoiceChange = True
#
#         self.choices = {}
#
#     def clear(self):
#         super().clear()
#         for n, opts in self.choices.items():
#             opts['role'].deleteLater()
#             del opts['role']
#
#         self.choices = {}
#
#     def updateSizes(self):
#         for i in range(4):
#             self.resizeColumnToContents(i)
#
#     def addAxis(self, name, grid=True):
#         item = QtGui.QTreeWidgetItem([name, '', '', ''])
#         self.addTopLevelItem(item)
#
#         combo = QtGui.QComboBox()
#         for o in self.options:
#             if not grid and o in self.gridOnlyOptions:
#                 pass
#             else:
#                 combo.addItem(o)
#         combo.setMinimumSize(50, 22)
#         combo.setMaximumHeight(22)
#         self.setItemWidget(item, 1, combo)
#         self.updateSizes()
#
#         self.choices[name] = {'role' : combo, 'options' : None}
#         combo.currentTextChanged.connect(lambda x: self.roleChanged(name, x))
#
#     # Generic role handling
#
#     def _setRole(self, ax, role=None, **kw):
#         if role is None:
#             role = ''
#
#         item = self.findItems(ax, QtCore.Qt.MatchExactly, 0)[0]
#
#         roleHasChanged = False
#         if self.choices[ax]['role'].currentText() != role:
#             self.choices[ax]['role'].setCurrentText(role)
#
#         self.setInfo(ax, '')
#
#         w = self.choices[ax]['options']
#         if w is not None:
#             # we need to make sure to delete the widget in this case.
#             # not entirely sure yet about this procedure.
#             # i have seen crashes seen before with similar constructions.
#             # need to keep an eye on this.
#             self.setItemWidget(item, 2, None)
#             w.deleteLater()
#             self.choices[ax]['options'] = None
#             self.updateSizes()
#
#         if self._grid and role == 'select value': # and w is None:
#             # TODO: set slider from current value?
#             axidx = self._dataStructure.axes().index(ax)
#             axlen = self._dataStructure.meta_val('shape', data=ax)[axidx]
#             # data_meta(ax)['shape'][axidx]
#
#             w = self._axisSlider(axlen)
#             self.choices[ax]['options'] = w
#             self.setItemWidget(item, 2, w)
#             w.setMinimumSize(150, 22)
#             w.setMaximumHeight(22)
#             self.updateSizes()
#
#             w.valueChanged.connect(lambda x: self.axisValueSelected(ax, x))
#             w.valueChanged.emit(w.value())
#
#     def _getRole(self, ax):
#         return self.choices[ax]['role'].currentText()
#
#     def clearInfos(self):
#         for ax in self.choices.keys():
#             self.setInfo(ax, '')
#
#     @QtCore.pyqtSlot(str, str)
#     def setInfo(self, ax, info):
#         try:
#             item = self.findItems(ax, QtCore.Qt.MatchExactly, 0)[0]
#             item.setText(3, info)
#         except IndexError:
#             pass
#
#     @QtCore.pyqtSlot(dict)
#     def setInfos(self, infos):
#         for ax, info in infos.items():
#             self.setInfo(ax, info)
#
#     @QtCore.pyqtSlot(str, str)
#     def roleChanged(self, axis, newSelection):
#         """
#         when a user changes the selection on a role combo box manually,
#         we need to check whether we need to update other roles, and update
#         role options.
#         """
#
#         if self._emitChoiceChange:
#
#             # cannot have multiple axes selected as x or y
#             self._setRole(axis, newSelection)
#             if newSelection in ['x-axis', 'y-axis', '']:
#                 for ax, opt in self.choices.items():
#                     if ax != axis and opt['role'].currentText() == newSelection:
#
#                         # this is a programmatic change of role,
#                         # so we should make sure we don't tell the node yet.
#                         self._emitChoiceChange = False
#                         self._setRole(ax, None)
#                         self._emitChoiceChange = True
#
#             # this might be overkill, but for now always emit option change.
#             # FIXME: need to combine this into one signal.
#             self.xyAxesChanged.emit(self._getXY())
#             self.reductionsChanged.emit(self._getReductions())
#
#     # Data structure handling
#
#     def enableGrid(self, enable=True):
#         """
#         When data is gridded, we can use axes reductions.
#         When it's not, we want to hide options that aren't applicable.
#         """
#         self._grid = enable
#
#         if self._dataStructure is not None:
#             for ax in self._dataStructure.axes():
#                 combo = self.choices[ax]['role']
#                 for o in self.gridOnlyOptions:
#                     idx = combo.findText(o)
#                     if enable and idx < 0:
#                         combo.addItem(o)
#                     elif not enable and idx >= 0:
#                         if combo.currentText() in self.gridOnlyOptions:
#                             self._setRole(ax, None)
#                         combo.removeItem(idx)
#
#     def setDataStructure(self, structure, grid):
#         """
#         This function populates the axes items and the
#         role selection widgets correctly.
#         """
#         # TODO: things when data size changes
#
#         self._emitChoiceChange = False
#
#         _set = False
#         if structure is None or self._dataStructure is None:
#             _set = True
#         elif structure.axes() != self._dataStructure.axes():
#             _set = True
#         if _set:
#             self.clear()
#             if structure is not None:
#                 for ax in structure.axes():
#                     self.addAxis(ax, grid=grid)
#
#         self._dataStructure = structure
#         if grid != self._grid:
#             self.enableGrid(grid)
#
#         self._emitChoiceChange = True
#
#     # Handling of particular options
#
#     # XY axes
#
#     @QtCore.pyqtSlot(str)
#     def setXYAxes(self, xy):
#         """
#         Programatically set x and y axes in the roles.
#         Do not emit a signal about UI element changes.
#         """
#         self._emitChoiceChange = False
#         x, y = xy
#         for ax, opts in self.choices.items():
#             if ax == x and opts['role'].currentText() != 'x-axis':
#                 self._setRole(ax, 'x-axis')
#             if ax != x and opts['role'].currentText() == 'x-axis':
#                 self._setRole(ax, None)
#             if ax == y and opts['role'].currentText() != 'y-axis':
#                 self._setRole(ax, 'y-axis')
#             if ax != y and opts['role'].currentText() == 'y-axis':
#                 self._setRole(ax, None)
#
#         self._emitChoiceChange = True
#
#     def _getXY(self):
#         x = None; y = None
#         for ax, opt in self.choices.items():
#             if opt['role'].currentText() == 'x-axis':
#                 x = ax
#             elif opt['role'].currentText() == 'y-axis':
#                 y = ax
#
#         return x, y
#
#     # Reductions
#
#     @QtCore.pyqtSlot(dict)
#     def setReductions(self, reductions):
#         """
#         Programatically set reduction roles.
#         Do not emit signals about UI element changes.
#
#         reductions are expected in the form the DimensionReducer class
#         stores them internally (unencoded!).
#         """
#         self._emitChoiceChange = False
#
#         # get a string-representation of the reduction functions
#         red = DimensionReducer.encodeReductions(reductions)
#
#         # now can set the role by name for each reduction
#         for ax, val in red.items():
#             if val is None:
#                 continue
#
#             name, args, kwargs = val
#             if self._getRole(ax) != name:
#                 self._setRole(ax, name)
#
#             # now we can process options for reductions that have any.
#             # value selection uses a slider
#             if name == 'select value':
#                 slider = self.choices[ax]['options']
#                 if slider is not None:
#                     if slider.value() != kwargs['index']:
#                         slider.setValue(kwargs['index'])
#
#         self._emitChoiceChange = True
#
#     def _getReductions(self):
#         ret = {}
#         for ax, opt in self.choices.items():
#             role = self._getRole(ax)
#             if role not in ['x-axis', 'y-axis', '']:
#                 ret[ax] = [role, [], {}]
#
#                 # Special options below, if applicable
#                 # value selection: has a slider, value is index
#                 if role == 'select value':
#                     slider = self.choices[ax]['options']
#                     if slider is not None:
#                         idx = slider.value()
#                     else:
#                         idx = 0
#                     ret[ax][2] = dict(index=idx)
#
#                 ret[ax] = tuple(ret[ax])
#
#             if role == '':
#                 ret[ax] = None
#
#         return ret
#
#
#     # value selection
#
#     def _axisSlider(self, npts, value=0):
#         """
#         Return a new axis slider widget.
#         """
#         w = QtGui.QSlider(0x01)
#         w.setMinimum(0)
#         w.setMaximum(npts-1)
#         w.setSingleStep(1)
#         w.setPageStep(1)
#         w.setTickInterval(10)
#         w.setTickPosition(QtGui.QSlider.TicksBelow)
#         w.setValue(value)
#         return w
#
#     @QtCore.pyqtSlot(str, int)
#     def axisValueSelected(self, ax, idx):
#         axidx = self._dataStructure.axes().index(ax)
#         axlen = self._dataStructure.meta_val('shape', data=ax)[axidx]
#         # data_meta(ax)['shape'][axidx]
#
#         info = f"{idx+1}/{axlen}"
#         self.setInfo(ax, info)
#         if self._emitChoiceChange:
#             self.reductionsChanged.emit(self._getReductions())
#
#
# class XYAxesSelector(DimensionReducer):
#     """
#     A Node that allows the user to select one or two axes (x and/or y); these
#     will be only remaining axes after processing, i.e., the output is either 1d
#     or 2d.
#
#     Basic behavior:
#     * if the input is GridData, then we can select x and or y, and apply a reduction
#       function over any unselected axis; this could, eg, be selecting a single-value slice,
#       averaging, integration, ... The output is then a 1d or 2d dataset with x and/or y axis.
#     * if the input is non-GridData, then we simply discard the non-x/y axes.
#     """
#
#     nodeName = 'XYAxesSelector'
#     dataStructureChanged = QtCore.pyqtSignal(dict, bool)
#     sendAxisInfo = QtCore.pyqtSignal(dict)
#
#     uiClass = XYAxesSelectionWidget
#     guiOptions = {
#         'xyAxes' : {
#             'widget' : None,
#             'setFunc' : 'setXYAxes',
#         },
#         'reductions' : {
#             'widget' : None,
#             'setFunc' : 'setReductions',
#         },
#     }
#
#     def __init__(self, *arg, **kw):
#
#         self._xyAxes = None, None
#         self._dataStructure = None
#         # self._grid = True
#
#         super().__init__(*arg, **kw)
#
#     # properties
#
#     @property
#     def xyAxes(self):
#         return self._xyAxes
#
#     @xyAxes.setter
#     @Node.updateOption('xyAxes')
#     def xyAxes(self, val):
#         self._xyAxes = val
#
#     # data processing
#
#     def validateOptions(self, data):
#         """
#         Checks performed:
#         * values for xAxis and yAxis must be axes that exist for the input data.
#         * x/y axes cannot be the same
#         * x/y axes cannot be reduced (will be removed from reductions)
#         * all axes that are not x/y must be reduced (defaulting to selection of the first element)
#         """
#         # TODO: break this up into smaller pieces.
#
#         if not super().validateOptions(data):
#             return False
#         availableAxes = data.axes()
#
#         if len(availableAxes) > 0:
#             if self._xyAxes[0] is None:
#                 self.logger().debug(f'x-Axis is None. this will result in empty output data.')
#                 return False
#             elif self._xyAxes[0] not in availableAxes:
#                 self.logger().warning(f'x-Axis {self._xyAxes[0]} not present in data')
#                 return False
#
#             if self._xyAxes[1] is None:
#                 self.logger().debug(f'y-Axis is None; result will be 1D')
#             elif self._xyAxes[1] not in availableAxes:
#                 self.logger().warning(f'y-Axis {self._xyAxes[1]} not present in data')
#                 return False
#             elif self._xyAxes[1] == self._xyAxes[0]:
#                 self.logger().warning(f"y-Axis cannot be equal to x-Axis.")
#                 return False
#
#         # below we actually mess with the reduction options, but
#         # without using the decorated property.
#         # make sure we emit the right signal at the end.
#         reductionsChanged = False
#
#         # Check: an axis marked as x/y cannot be also reduced.
#         delete = []
#         for n, _ in self._reductions.items():
#             if n in self._xyAxes:
#                 self.logger().debug(f"{n} has been selected as axis, cannot be reduced.")
#                 delete.append(n)
#         for n in delete:
#             del self._reductions[n]
#             reductionsChanged = True
#
#         # check: axes not marked as x/y should all be reduced.
#         for ax in availableAxes:
#             if ax not in self._xyAxes:
#                 if ax not in self._reductions:
#                     self.logger().debug(f"{ax} must be reduced. Default to selecting first element.")
#
#                     # reductions are only supported on GridData
#                     if isinstance(data, MeshgridDataDict):
#                         red = (selectAxisElement, [], dict(index=0))
#                     else:
#                         red = None
#
#                     self._reductions[ax] = red
#                     reductionsChanged = True
#
#                 # since we have tinkered with the reductions, we might need to
#                 # tell the GUI about that.
#                 # we simply look for inconsistencies between the GUI state
#                 # and what the current state of the reductions here is.
#                 if isinstance(data, MeshgridDataDict) and ax in self._reductions:
#                     if self.ui is not None:
#                         uiRed = self.ui._getReductions()
#                         if ax not in uiRed:
#                             reductionsChanged = True
#                         elif uiRed[ax] is None:
#                             reductionsChanged = True
#
#         if reductionsChanged:
#             self.optionChanged.emit('reductions', self._reductions)
#
#
#         # some output infos for the reduction widgets
#         infos = {}
#         reductionsEncoded = DimensionReducer.encodeReductions(self._reductions)
#         for ax, item in reductionsEncoded.items():
#             # the DimReducer currently doesn't delete reductions pointing to unused
#             # axes (by choice). We just ignore those here.
#             if ax not in availableAxes:
#                 continue
#
#             # TODO: need better procedure to extract 'best-guess' axis values.
#             # this procedure is super ghetto -- works fine for regular grids,
#             # but might not give good results anymore in case of very irregular
#             # meshes.
#             if isinstance(data, MeshgridDataDict) and item[0] == 'select value':
#                 axidx = data.axes().index(ax)
#                 axlen = data.data_vals(ax).shape[axidx]
#
#                 validx = item[2].get('index')
#                 slices = [slice(None, None, None) for i in data.axes()]
#                 slices[axidx] = slice(validx, validx+1, None)
#                 val = data[ax]['values'][tuple(slices)].mean()
#
#                 infos[ax] = (f"pt. {validx+1}/{axlen}" +\
#                              f" ({val:1.3e} {data[ax]['unit']})")
#             else:
#                 infos[ax] = ''
#
#         self.sendAxisInfo.emit(infos)
#         return True
#
#     def process(self, **kw):
#         data = kw['dataIn']
#         if data is None:
#             return None
#
#         self.updateUi(data)
#         data = super().process(dataIn=data)
#         if data is None:
#             return None
#         data = data['dataOut'].copy()
#
#         if self._xyAxes[0] is not None and self._xyAxes[1] is not None:
#             _kw = {self._xyAxes[0]: 0, self._xyAxes[1]: 1}
#             data = data.reorder_axes(**_kw)
#
#         return dict(dataOut=data)
#
#     # GUI interaction
#
#     def setupUi(self):
#         self.dataStructureChanged.connect(self.ui.setDataStructure)
#         self.ui.setXYAxes(self._xyAxes)
#         self.ui.xyAxesChanged.connect(self._setXYAxes)
#         self.ui.setReductions(self._reductions)
#         self.ui.reductionsChanged.connect(self._setReductions)
#         self.sendAxisInfo.connect(self.ui.setInfos)
#         # self.ui.enableGrid(self.grid)
#
#     def updateUi(self, data):
#         structure = data.structure(add_shape=True)
#         self.dataStructureChanged.emit(structure, isinstance(data, MeshgridDataDict))
#
#     @QtCore.pyqtSlot(tuple)
#     def _setXYAxes(self, xy):
#         self.xyAxes = xy
#
#     @QtCore.pyqtSlot(dict)
#     def _setReductions(self, reductionsEncoded):
#         reductions = DimensionReducer.decodeReductions(reductionsEncoded)
#         self.reductions = reductions
#
