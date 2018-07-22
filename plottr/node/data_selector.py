"""
data_selector.py

Contains tools for selecting parts of a dataset.
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


class DataSelector(Node):

    nodeName = "DataSelector"
    sendDataStructure = QtCore.pyqtSignal(object)
    sendReducedDataStructure = QtCore.pyqtSignal(object)
    uiClass = None

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


    def _reduceData(self, data):
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
        return data

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
        axnames = copy.deepcopy(data[data.dependents()[0]]['axes'])

        for m in copy.deepcopy(data.dependents()):
            data[m]['values'] = np.squeeze(data[m]['values'])
            for i, n in enumerate(axnames):
                if oldshape[i] < 2:
                    idx = data[m]['axes'].index(n)
                    del data[m]['axes'][idx]
                    if n in data:
                        del data[n]

        return data


    def process(self, **kw):
        data = kw['dataIn']
        data = self._reduceData(data)

        if self.grid and len(data.dependents()) > 0:
            if self.slices != {}:
                data = self._sliceData(data)
            if self.axesOrder != {}:
                data = self._reorderData(data)
            if self.squeeze:
                data = self._squeezeData(data)

        return dict(dataOut=data)


class XYSelectorWidget(QtGui.QWidget):

    # TODO:
    # * make sure that options are updated when setting from cmd line

    newDataStructure = QtCore.pyqtSignal()
    dataSelectionUpdated = QtCore.pyqtSignal(str, str, list, dict)
    slicesUpdated = QtCore.pyqtSignal(dict)
    selectablesUpdateNeeded = QtCore.pyqtSignal()
    debug = False

    def __init__(self, parent=None, **kw):
        super().__init__(parent=parent, **kw)

        # Axes selection
        self._axesOptions = []
        self.xCombo = QtGui.QComboBox()
        self.yCombo = QtGui.QComboBox()
        self.xCombo.currentTextChanged.connect(
            lambda choice: self.selectAx('x', choice))
        self.yCombo.currentTextChanged.connect(
            lambda choice: self.selectAx('y', choice))

        axLayout = QtGui.QFormLayout()
        axLayout.addRow('x-axis', self.xCombo)
        axLayout.addRow('y-axis', self.yCombo)
        axGroup = QtGui.QGroupBox('Axis selection')
        axGroup.setLayout(axLayout)

        # Data fields
        self._triggerUpdateSelectables = True
        self._dataOptions = {}
        self._selectedData = []

        self.dataLayout = QtGui.QFormLayout()
        dataGroup = QtGui.QGroupBox('Data selection')
        dataGroup.setLayout(self.dataLayout)

        # Slicing sliders
        self._sliceOptions = {}
        self._slices = {}
        self.sliceLayout = QtGui.QVBoxLayout()
        sliceGroup = QtGui.QGroupBox('Slices')
        sliceGroup.setLayout(self.sliceLayout)

        mainLayout = QtGui.QVBoxLayout(self)
        mainLayout.addWidget(axGroup)
        mainLayout.addWidget(dataGroup)
        mainLayout.addWidget(sliceGroup)
        mainLayout.insertStretch(-1)

        self.newDataStructure.connect(self.resetDataStructure)
        self.selectablesUpdateNeeded.connect(self.updateSelectableData)


    @QtCore.pyqtSlot()
    def resetDataStructure(self):
        self.updateAxOptions()
        self.updateDataOptions()


    @QtCore.pyqtSlot(object)
    def setDataStructure(self, newStructure):
        # if self.debug:
        #     print('update structure:')
        #     pprint(newStructure)
        self.dataStructure = newStructure
        axes = newStructure.axes_list()
        if axes != self._axesOptions:
            self._axesOptions = axes
            self.newDataStructure.emit()


    @QtCore.pyqtSlot()
    def updateAxOptions(self):
        axOptions = [''] + self._axesOptions
        for combo in self.xCombo, self.yCombo:
            combo.clear()
            combo.addItems(axOptions)


    def selectAx(self, dimName, axName):
        # if self.debug:
        #     print('ax selected: {} => {}'.format(dimName, axName))
        emit = True
        if dimName == 'x':
            if axName != '' and axName == self.yCombo.currentText():
                emit = False
                self.yCombo.setCurrentText('')

        elif dimName == 'y':
            if axName != '' and axName == self.xCombo.currentText():
                emit = False
                self.xCombo.setCurrentText('')

        order = {}
        curx = self.xCombo.currentText()
        cury = self.yCombo.currentText()
        if curx != '':
            order[curx] = 0
        if cury != '':
            order[cury] = 1

        if emit:
            self.selectablesUpdateNeeded.emit()
            # if self.debug:
            #     print('New axes choices: {}, {}'.format(curx, cury))


    def _deleteDataOptions(self, names):
        for name in names:
            v = self._dataOptions[name]
            self.dataLayout.removeWidget(v['widget'])
            self.dataLayout.removeWidget(v['label'])
            v['widget'].deleteLater()
            v['label'].deleteLater()
            del self._dataOptions[name]


    @QtCore.pyqtSlot()
    def updateDataOptions(self):
        delete = []
        for k, v in self._dataOptions.items():
            delete.append(k)
        self._deleteDataOptions(delete)

        for n in self.dataStructure.dependents():
            if n not in self._dataOptions:
                lbl = QtGui.QLabel(n)
                chk = QtGui.QCheckBox()
                chk.setDisabled(True)
                chk.stateChanged.connect(lambda x: self.updateSelectableData())
                self._dataOptions[n] = dict(label=lbl, widget=chk)
                self.dataLayout.addRow(lbl, chk)


    def _getSelectedData(self):
        curdata = []
        for k, v in self._dataOptions.items():
            if v['widget'].isChecked():
                curdata.append(k)
        return curdata


    @QtCore.pyqtSlot()
    def updateSelectableData(self):
        if self._triggerUpdateSelectables:
            self._triggerUpdateSelectables = False

            curx = self.xCombo.currentText()
            cury = self.yCombo.currentText()
            curaxes = []
            curdata = self._getSelectedData()

            if len(curdata) > 0:
                curaxes = self.dataStructure[curdata[0]]['axes']

            for k, v in self._dataOptions.items():

                if curx == '':
                    v['widget'].setDisabled(True)
                    v['widget'].setChecked(False)

                elif curx not in self.dataStructure[k]['axes']:
                    v['widget'].setDisabled(True)
                    v['widget'].setChecked(False)

                elif (len(curaxes) > 0) and (self.dataStructure[k]['axes'] != curaxes):
                    v['widget'].setDisabled(True)
                    v['widget'].setChecked(False)

                else:
                    v['widget'].setEnabled(True)

            self._triggerUpdateSelectables = True
            curdata = self._getSelectedData()
            self._refreshSlices()
            self.dataSelectionUpdated.emit(curx, cury, curdata, self._slices)


    def _deleteSliceOptions(self, names):
        for name in names:
            v = self._sliceOptions[name]
            self.sliceLayout.removeWidget(v['widget'])
            v['widget'].deleteLater()
            del self._sliceOptions[name]


    @QtCore.pyqtSlot(object)
    def setReducedDataStructure(self, newStructure):
        # if self.debug:
        #     print('reduced structure:')
        #     pprint(newStructure)

        axes = newStructure.axes_list()
        delete = []
        for k, v in self._sliceOptions.items():
            if k not in axes:
                delete.append(k)
        self._deleteSliceOptions(delete)

        for a in axes:
            if a not in self._sliceOptions:
                w = AxisSlider()
                self.sliceLayout.addWidget(w)
                self._sliceOptions[a] = dict(widget=w)

                if a in self._slices:
                    val = self._slices[a].start
                    if val is None:
                        val = 0
                else:
                    val = 0
                w.setAxis(a, nvals=newStructure[a]['info']['shape'][0], initialValue=val)
                w.unit = newStructure[a]['unit']
                w.slider.valueChanged.connect(self.sliderUpdated)
            else:
                w = self._sliceOptions[a]['widget']
                w.setAxis(a, nvals=newStructure[a]['info']['shape'][0], reset=False)

            if a in [self.xCombo.currentText(), self.yCombo.currentText()]:
                w.setDisabled(True)
            else:
                w.setEnabled(True)


    def _refreshSlices(self):
        for k, v in self._sliceOptions.items():
            idx = v['widget'].slider.value()
            self._slices[k] = np.s_[idx:idx+1:]


    @QtCore.pyqtSlot()
    def sliderUpdated(self):
        self._refreshSlices()
        self.slicesUpdated.emit(self._slices)

    @QtCore.pyqtSlot(dict)
    def setSlices(self, sliceInfo):
        for ax, v in sliceInfo.items():
            idx = v['index']
            val = v['value']

            if ax in self._sliceOptions:
                w = self._sliceOptions[ax]['widget']
                if w.slider.value() != idx:
                    w.slider.setValue(idx)
                w.setAxValue(val)


class XYSelector(DataSelector):

    nodeName = "XYSelector"
    uiClass = XYSelectorWidget

    slicesSet = QtCore.pyqtSignal(dict)

    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)

        self._xSelection = None
        self._ySelection = None

    def setupUi(self):
        self.sendDataStructure.connect(self.ui.setDataStructure)
        self.sendReducedDataStructure.connect(self.ui.setReducedDataStructure)
        self.ui.dataSelectionUpdated.connect(self.setDataSelection)
        self.ui.slicesUpdated.connect(self.setSlices)
        self.slicesSet.connect(self.ui.setSlices)

    @QtCore.pyqtSlot(str, str, list, dict)
    def setDataSelection(self, x, y, data, slices):
        self._axesOrder = {}
        if x != '':
            self._axesOrder[x] = 0
            self._xSelection = x
        else:
            self._xSelection = None

        if y != '':
            self._axesOrder[y] = 1
            self._ySelection = y
        else:
            self._ySelection = None

        self._selectedData = data
        self._slices = slices
        self.update(signal=self.signalUpdate)

    @QtCore.pyqtSlot(dict)
    def setSlices(self, slices):
        self.slices = slices

    def process(self, **kw):
        data = kw['dataIn']

        # notify the widget about all available data
        self.sendDataStructure.emit(data.structure())

        # now we start reducing the data (i.e., take selected data
        # fields into account, and grid if necessary; remove unused axes)
        # then we notify the widget with that reduced structure, as we
        # need it to make axes sliders.
        data = self._reduceData(data)
        self.sendReducedDataStructure.emit(data.structure())

        # no x-axis is invalid. because i say so.
        if self._xSelection in ['', None]:
            return dict(dataOut=DataDict())

        # make sure that all axes that are not x/y are sliced to give 1 point
        # and that x/y are not sliced at all.
        availableAxes = data.axes_list(self.selectedData)
        for a in availableAxes:
            if a not in self._slices:
                self._slices[a] = np.s_[0:1:]

        self._slices[self._xSelection] = np.s_[::]
        if self._ySelection not in ['', None]:
            self._slices[self._ySelection] = np.s_[::]

        # things might have changed. so communicate that back to UI.
        # Also we know know the axis values, too.
        slices = {}
        for k, v in self._slices.items():
            if k not in [self._xSelection, self._ySelection] and k in data:
                idx = v.start
                val = data[k]['values'][idx]
                slices[k] = dict(index=idx, value=val)
        self.slicesSet.emit(slices)

        # if self.debug:
        #     print('Process. XY selections:')
        #     print(f'  x = {self._xSelection}, y = {self._ySelection}')
        #     print(f'  data = {self._selectedData}, slices = {self._slices}')

        ret = super().process(dataIn=data)
        # pprint(ret)
        return ret

### Tool GUI elements

class AxisSlider(QtGui.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self._idx = None

        self.unit = ''
        self.axisName = None
        self.nAxisVals = None

        self.slider = QtGui.QSlider(0x01)
        self.label = QtGui.QLabel()

        self.layout = QtGui.QVBoxLayout()
        self.setLayout(self.layout)
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.slider)

        self.slider.valueChanged.connect(self.idxSet)

    def setAxis(self, name, nvals, reset=True, initialValue=0):
        self.axisName = name
        self.nAxisVals = nvals
        self.slider.setMaximum(nvals-1)
        if reset:
            self.slider.setMinimum(0)
            self.slider.setSingleStep(1)
            self.slider.setPageStep(1)
            self.slider.setValue(initialValue)
            self.slider.valueChanged.emit(initialValue)
        else:
            self.idxSet(self.slider.value())

    def setLabel(self, idx, val=None):
        if val is None:
            val = ''
        else:
            val = f"({val} {self.unit})"

        lbl = "{} : {}/{} {}".format(
            self.axisName, idx+1, self.nAxisVals, val)
        self.label.setText(lbl)

    @QtCore.pyqtSlot(int)
    def idxSet(self, idx):
        self._idx = idx
        self.setLabel(idx)

    @QtCore.pyqtSlot(float)
    def setAxValue(self, val):
        self.setLabel(self._idx, val)

