"""
xy_axes_selector.py

A node and widget for reducing data to 1d/2d data.
"""
import copy
from pprint import pprint
import enum

import numpy as np

from pyqtgraph import Qt
from pyqtgraph.Qt import QtGui, QtCore

from .node import Node
from ..data.datadict import togrid, DataDict, GridDataDict

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


# TODO:
# * ATM xy and reduction signals are called separate, resulting in two processing
#   events when dropdowns have changed. should combine that.


# Some helpful reduction functions
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


# Translation between reduction functions and some name we like to use
# to address them
axisReductionFuncs = {
    'select value' : selectAxisElement,
    'average' : np.mean,
}

def reductionFuncFromName(name):
    return axisReductionFuncs.get(name, None)

def reductionNameFromFunc(func):
    for n, f in axisReductionFuncs.items():
        if f == func:
            return n
    return None


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

        self._reductions = {}
        self._targetNames = None
        self._protectedAxes = []

        super().__init__(*arg, **kw)

    # Properties

    @property
    def reductions(self):
        return self._reductions

    @reductions.setter
    @Node.updateOption('reductions')
    def reductions(self, val):
        self._reductions = val

    @property
    def targetNames(self):
        return self._targetNames

    @targetNames.setter
    @Node.updateOption()
    def targetNames(self, val):
        self._targetNames = val

    # Tools for passing reductions -- mapping to strings and back
    @staticmethod
    def encodeReductions(reductions):
        red = {}
        for k, val in reductions.items():
            if val is None:
                continue
            f, arg, kw = val
            red[k] = (reductionNameFromFunc(f), arg, kw)
        return red

    @staticmethod
    def decodeReductions(reductions):
        red = {}
        for k, val in reductions.items():
            if val is None:
                continue
            n, arg, kw = val
            red[k] = (reductionFuncFromName(n), arg, kw)
        return red

    # Data processing

    def _applyDimReductions(self, data):
        if self._targetNames is not None:
            dnames = self._targetNames
        else:
            dnames = data.dependents()

        if not isinstance(data, GridDataDict):
            self.logger().debug(f"Data is not on a grid. Reduction functions are ignored, axes will simply be removed.")

        for n in dnames:
            for ax, reduction in self._reductions.items():
                if reduction is not None:
                    fun, arg, kw = reduction
                else:
                    fun, arg, kw = None, [], {}

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

        delete = []
        for ax, reduction in self._reductions.items():
            if reduction is None:
                if isinstance(data, GridDataDict):
                    self.logger().warning(f'Reduction for axis {ax} is None. Removing.')
                    delete.append(ax)
                else:
                    pass
                continue

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

        for ax in delete:
            del self._reductions[ax]

        return True

    def process(self, **kw):
        data = super().process(**kw)
        if data is None:
            return None

        data = self._applyDimReductions(copy.deepcopy(data['dataOut']))

        if data is None:
            return None
        return dict(dataOut=data)


class XYAxesSelectionWidget(QtGui.QTreeWidget):

    options = ['', 'x-axis', 'y-axis', 'average', 'select value']
    gridOnlyOptions = ['average', 'select value']

    # signals for when the user has changed options via the UI.
    xyAxesChanged = QtCore.pyqtSignal(tuple)
    reductionsChanged = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setColumnCount(4)
        self.setHeaderLabels(['Axis', 'Role', 'Options', 'Info'])

        self._dataStructure = None
        self._grid = True
        self._emitChoiceChange = True

        self.choices = {}

    def clear(self):
        super().clear()
        for n, opts in self.choices.items():
            opts['role'].deleteLater()
            del opts['role']

        self.choices = {}

    def updateSizes(self):
        for i in range(4):
            self.resizeColumnToContents(i)

    def addAxis(self, name, grid=True):
        item = QtGui.QTreeWidgetItem([name, '', '', ''])
        self.addTopLevelItem(item)

        combo = QtGui.QComboBox()
        for o in self.options:
            if not grid and o in self.gridOnlyOptions:
                pass
            else:
                combo.addItem(o)
        combo.setMinimumSize(50, 22)
        combo.setMaximumHeight(22)
        self.setItemWidget(item, 1, combo)
        self.updateSizes()

        self.choices[name] = {'role' : combo, 'options' : None}
        combo.currentTextChanged.connect(lambda x: self.roleChanged(name, x))

    # Generic role handling

    def _setRole(self, ax, role=None, **kw):
        if role is None:
            role = ''

        item = self.findItems(ax, QtCore.Qt.MatchExactly, 0)[0]

        roleHasChanged = False
        if self.choices[ax]['role'].currentText() != role:
            self.choices[ax]['role'].setCurrentText(role)

        self.setInfo(ax, '')

        w = self.choices[ax]['options']
        if w is not None:
            # we need to make sure to delete the widget in this case.
            # not entirely sure yet about this procedure.
            # i have seen crashes seen before with similar constructions.
            # need to keep an eye on this.
            self.setItemWidget(item, 2, None)
            w.deleteLater()
            self.choices[ax]['options'] = None
            self.updateSizes()

        if self._grid and role == 'select value': # and w is None:
            # TODO: set slider from current value?
            w = self._axisSlider(self._dataStructure[ax]['info']['shape'][0])
            self.choices[ax]['options'] = w
            self.setItemWidget(item, 2, w)
            w.setMinimumSize(150, 22)
            w.setMaximumHeight(22)
            self.updateSizes()

            w.valueChanged.connect(lambda x: self.axisValueSelected(ax, x))
            w.valueChanged.emit(w.value())

    def _getRole(self, ax):
        return self.choices[ax]['role'].currentText()

    def clearInfos(self):
        for ax in self.choices.keys():
            self.setInfo(ax, '')

    @QtCore.pyqtSlot(str, str)
    def setInfo(self, ax, info):
        try:
            item = self.findItems(ax, QtCore.Qt.MatchExactly, 0)[0]
            item.setText(3, info)
        except IndexError:
            pass

    @QtCore.pyqtSlot(dict)
    def setInfos(self, infos):
        for ax, info in infos.items():
            self.setInfo(ax, info)

    @QtCore.pyqtSlot(str, str)
    def roleChanged(self, axis, newSelection):
        """
        when a user changes the selection on a role combo box manually,
        we need to check whether we need to update other roles, and update
        role options.
        """
        if self._emitChoiceChange:

            # cannot have multiple axes selected as x or y
            self._setRole(axis, newSelection)
            if newSelection in ['x-axis', 'y-axis', '']:
                for ax, opt in self.choices.items():
                    if ax != axis and opt['role'].currentText() == newSelection:

                        # this is a programmatic change of role,
                        # so we should make sure we don't tell the node yet.
                        self._emitChoiceChange = False
                        self._setRole(ax, None)
                        self._emitChoiceChange = True

            # this might be overkill, but for now always emit option change.
            # TODO: in the long run, probably want to combine this into
            #       one signal, and have the node itself determine if action
            #       is necessary.
            self.xyAxesChanged.emit(self._getXY())
            self.reductionsChanged.emit(self._getReductions())

    # Data structure handling

    def enableGrid(self, enable=True):
        """
        When data is gridded, we can use axes reductions.
        When it's not, we want to hide options that aren't applicable.
        """
        self._grid = enable

        if self._dataStructure is not None:
            for ax in self._dataStructure.axes_list():
                combo = self.choices[ax]['role']
                for o in self.gridOnlyOptions:
                    idx = combo.findText(o)
                    if enable and idx < 0:
                        combo.addItem(o)
                    elif not enable and idx >= 0:
                        if combo.currentText() in self.gridOnlyOptions:
                            self._setRole(ax, None)
                        combo.removeItem(idx)

    def setDataStructure(self, structure, grid):
        """
        This function populates the axes items and the
        role selection widgets correctly.
        """
        # TODO: things when data size changes

        self._emitChoiceChange = False

        _set = False
        if structure is None or self._dataStructure is None:
            _set = True
        elif structure.axes_list() != self._dataStructure.axes_list():
            _set = True
        if _set:
            self.clear()
            if structure is not None:
                for ax in structure.axes_list():
                    self.addAxis(ax, grid=grid)

        self._dataStructure = structure
        if grid != self._grid:
            self.enableGrid(grid)

        self._emitChoiceChange = True

    # Handling of particular options

    # XY axes

    @QtCore.pyqtSlot(str)
    def setXYAxes(self, xy):
        """
        Programatically set x and y axes in the roles.
        Do not emit a signal about UI element changes.
        """
        self._emitChoiceChange = False
        x, y = xy
        for ax, opts in self.choices.items():
            if ax == x and opts['role'].currentText() != 'x-axis':
                self._setRole(ax, 'x-axis')
            if ax != x and opts['role'].currentText() == 'x-axis':
                self._setRole(ax, None)
            if ax == y and opts['role'].currentText() != 'y-axis':
                self._setRole(ax, 'y-axis')
            if ax != y and opts['role'].currentText() == 'y-axis':
                self._setRole(ax, None)

        self._emitChoiceChange = True

    def _getXY(self):
        x = None; y = None
        for ax, opt in self.choices.items():
            if opt['role'].currentText() == 'x-axis':
                x = ax
            elif opt['role'].currentText() == 'y-axis':
                y = ax

        return x, y

    # Reductions

    @QtCore.pyqtSlot(dict)
    def setReductions(self, reductions):
        """
        Programatically set reduction roles.
        Do not emit signals about UI element changes.

        reductions are expected in the form the DimensionReducer class
        stores them internally (unencoded!).
        """
        self._emitChoiceChange = False

        # get a string-representation of the reduction functions
        red = DimensionReducer.encodeReductions(reductions)

        # now can set the role by name for each reduction
        for ax, val in red.items():
            if val is None:
                continue

            name, args, kwargs = val
            if self._getRole(ax) != name:
                self._setRole(ax, name)

            # now we can process options for reductions that have any.
            # value selection uses a slider
            if name == 'select value':
                slider = self.choices[ax]['options']
                if slider is not None:
                    if slider.value() != kwargs['index']:
                        slider.setValue(kwargs['index'])

        self._emitChoiceChange = True

    def _getReductions(self):
        ret = {}
        for ax, opt in self.choices.items():
            role = self._getRole(ax)
            if role not in ['x-axis', 'y-axis', '']:
                ret[ax] = [role, [], {}]

                # Special options below, if applicable
                # value selection: has a slider, value is index
                if role == 'select value':
                    slider = self.choices[ax]['options']
                    if slider is not None:
                        idx = slider.value()
                    else:
                        idx = 0
                    ret[ax][2] = dict(index=idx)

                ret[ax] = tuple(ret[ax])

            if role == '':
                ret[ax] = None

        return ret


    # value selection

    def _axisSlider(self, npts, value=0):
        """
        Return a new axis slider widget.
        """
        w = QtGui.QSlider(0x01)
        w.setMinimum(0)
        w.setMaximum(npts-1)
        w.setSingleStep(1)
        w.setPageStep(1)
        w.setTickInterval(10)
        w.setTickPosition(QtGui.QSlider.TicksBelow)
        w.setValue(value)
        return w

    @QtCore.pyqtSlot(str, int)
    def axisValueSelected(self, ax, idx):
        info = f"{idx+1}/{self._dataStructure[ax]['info']['shape'][0]}"
        self.setInfo(ax, info)
        if self._emitChoiceChange:
            self.reductionsChanged.emit(self._getReductions())


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
    dataStructureChanged = QtCore.pyqtSignal(dict, bool)
    sendAxisInfo = QtCore.pyqtSignal(dict)

    uiClass = XYAxesSelectionWidget
    guiOptions = {
        'xyAxes' : {
            'widget' : None,
            'setFunc' : 'setXYAxes',
        },
        'reductions' : {
            'widget' : None,
            'setFunc' : 'setReductions',
        },
    }

    def __init__(self, *arg, **kw):

        self._xyAxes = None, None
        self._dataStructure = None
        self._grid = True

        super().__init__(*arg, **kw)

    # properties

    @property
    def xyAxes(self):
        return self._xyAxes

    @xyAxes.setter
    @Node.updateOption('xyAxes')
    def xyAxes(self, val):
        self._xyAxes = val

    # data processing

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

        if len(availableAxes) > 0:
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

        # below we actually mess with the reduction options, but
        # without using the decorated property.
        # make sure we emit the right signal at the end.
        reductionsChanged = False

        # Check: an axis marked as x/y cannot be also reduced.
        delete = []
        for n, _ in self._reductions.items():
            if n in self._xyAxes:
                self.logger().debug(f"{n} has been selected as axis, cannot be reduced.")
                delete.append(n)
        for n in delete:
            del self._reductions[n]
            reductionsChanged = True

        # check: axes not marked as x/y should all be reduced.
        for ax in availableAxes:
            if ax not in self._xyAxes:
                if ax not in self._reductions:
                    self.logger().debug(f"{ax} must be reduced. Default to selecting first element.")

                    # reductions are only supported on GridData
                    if isinstance(data, GridDataDict):
                        red = (selectAxisElement, [], dict(index=0))
                    else:
                        red = None

                    self._reductions[ax] = red
                    reductionsChanged = True

                if isinstance(data, GridDataDict) and ax in self._reductions:
                    uiRed = self.ui._getReductions()
                    if ax not in uiRed:
                        reductionsChanged = True
                    elif uiRed[ax] is None:
                        reductionsChanged = True

        if reductionsChanged:
            self.optionChanged.emit('reductions', self._reductions)

        # some output infos for the reduction widgets
        infos = {}
        reductionsEncoded = DimensionReducer.encodeReductions(self._reductions)
        for ax, item in reductionsEncoded.items():
            # the DimReducer currenlty doesn't delete reductions pointing to unused
            # axes (by choice). We just ignore those here.
            if ax not in availableAxes:
                continue
            if isinstance(data, GridDataDict) and item[0] == 'select value':
                idx = item[2].get('index')
                infos[ax] = (f"pt. {idx+1}/{len(data[ax]['values'])}"
                            f" ({data[ax]['values'][idx]:1.3e} {data[ax]['unit']})")
            else:
                infos[ax] = ''

        self.sendAxisInfo.emit(infos)
        return True

    def process(self, **kw):
        data = kw['dataIn']
        self.updateUi(data)

        data = super().process(dataIn=data)
        if data is None:
            return None

        data = data['dataOut']
        if self._xyAxes[0] is not None and self._xyAxes[1] is not None:
            _kw = {self._xyAxes[0]: 0, self._xyAxes[1]: 1}
            data.reorder_axes(**_kw)

        return dict(dataOut=data)

    # GUI interaction

    def setupUi(self):
        self.dataStructureChanged.connect(self.ui.setDataStructure)
        self.ui.setXYAxes(self._xyAxes)
        self.ui.xyAxesChanged.connect(self._setXYAxes)
        self.ui.setReductions(self._reductions)
        self.ui.reductionsChanged.connect(self._setReductions)
        self.sendAxisInfo.connect(self.ui.setInfos)
        self.ui.enableGrid(self.grid)

    def updateUi(self, data):
        structure = data.structure()
        self.dataStructureChanged.emit(structure, isinstance(data, GridDataDict))

    @QtCore.pyqtSlot(tuple)
    def _setXYAxes(self, xy):
        self.xyAxes = xy

    @QtCore.pyqtSlot(dict)
    def _setReductions(self, reductionsEncoded):
        reductions = DimensionReducer.decodeReductions(reductionsEncoded)
        self.reductions = reductions

