import sys
import numpy as np
from pprint import pprint

from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication, QDialog, QWidget

from plottr.data.datadict import DataDict
from plottr.gui.ui_lineplot import Ui_LinePlot


class Node(QObject):

    dataProcessed = pyqtSignal(object)
    optionsUpdated = pyqtSignal()

    _userOptions = {}

    def __init__(self):
        super().__init__()
        self._inputData = None
        self._outputData = None
        self._updateOnSource = True
        self._updateOnOptionChange = True
        self._source = None

        self.optionsUpdated.connect(self.update)

        for k, v in self._userOptions.items():
            self._addOption(
                name=k,
                initialValue=v.get('initialValue', None),
                doc=v.get('doc', ''),
            )

    def _addOption(self, name, initialValue=None, doc='', force=False):
        varname = '_' + name
        if hasattr(self, varname) and not force:
            raise ValueError("attribute name '{}' is in use already".format(varname))
        setattr(self, varname, initialValue)

        def fget(self):
            return getattr(self, varname)

        def fset(self, val):
            setattr(self, varname, val)
            if self._updateOnOptionChange:
                self.optionsUpdated.emit()

        opt = property(fget=fget, fset=fset, doc=doc)
        setattr(self.__class__, name, opt)

    @property
    def updateOnSource(self):
        return self._updateOnSource

    @updateOnSource.setter
    def updateOnSource(self, val):
        if self._updateOnSource and not val and self._source is not None:
            self._source.dataProcessed.disconnect(self.run)
        if not self._updateOnSource and val and self._source is not None:
            self._source.dataProcessed.connect(self.run)
        self._updateOnSource = val

    @property
    def updateOnOptionChange(self):
        return self._updateOnOptionChange

    @updateOnOptionChange.setter
    def updateOnOptionChange(self, val):
        self._updateOnOptionChange = val

    def setSource(self, source, run=True):
        self._source = source
        if isinstance(self._source, Node):
            self._inputData = self._source._outputData
            if self._updateOnSource:
                self._source.dataProcessed.connect(self.run)
            if run:
                self.update()

    def getInputData(self):
        self._inputData = self._source._outputData

    @pyqtSlot()
    def update(self):
        print('update:', self)
        self.run(self._inputData)

    @pyqtSlot(object)
    def run(self, data):
        print('run:', self)
        self._inputData = data
        if self._inputData is not None:
            self._outputData = self.processData(self._inputData)
            self.dataProcessed.emit(self._outputData)
            print('processed:', self)
            pprint(self._outputData)
            print('')

    def processData(self, data):
        print('process:', self)
        pprint(data)
        print('')
        return data


class DataDictSourceNode(Node):

    def __init__(self):
        super().__init__()

    def setData(self, data):
        self._inputData = data
        self.run(data)


class DataSelector(Node):

    _userOptions = dict(
        dataName = dict(
            initialValue=None,
            doc='Name of the data field to select',
            type='str',
        ),
        axesOrder = dict(
            initialValue={},
        ),
        slices = dict(
            initialValue={},
        ),
        grid = dict(
            initialValue=True,
            type=bool,
        ),
        squeeze = dict(
            initialValue=True,
            type=bool,
        ),
    )

    def __init__(self):
        super().__init__()


    @staticmethod
    def axesList(data, dataName=None):
        lst = []
        if dataName is None:
            for k, v in data.items():
                if 'axes' in v:
                    for n in v['axes']:
                        if n not in lst:
                            lst.append(n)
        else:
            if dataName in data and 'axes' in data[dataName]:
                lst = data[dataName]['axes']

        return lst

    def validate(self, data):
        return True

    def processData(self, data):
        data = super().processData(data)
        if not self.validate(data):
            return {}

        if self.dataName is None:
            return {}

        if hasattr(data, 'get_grid') and self._grid:
            data = data.get_grid(self.dataName)
        else:
            _data = {self.dataName : data[self.dataName]}
            for k, v in data:
                if k in data[self.dataName].get('axes', []):
                    _data[k] = v
            data = _data

        if self.grid:
            _datavals = data[self.dataName]['values']
            _axnames = data[self.dataName]['axes']

            slices = [np.s_[::] for a in _axnames]
            for n, s in self.slices.items():
                idx = _axnames.index(n)
                slices[idx] = s
                data[n]['values'] = data[n]['values'][s]
            data[self.dataName]['values'] = _datavals[slices]
            _datavals = data[self.dataName]['values']

            neworder = [None for a in _axnames]
            oldorder = list(range(len(_axnames)))
            for n, newidx in self.axesOrder.items():
                neworder[newidx] = _axnames.index(n)

            for i in neworder:
                if i in oldorder:
                    del oldorder[oldorder.index(i)]

            for i in range(len(neworder)):
                if neworder[i] is None:
                    neworder[i] = oldorder[0]
                    del oldorder[0]

            data[self.dataName]['values'] = _datavals.transpose(tuple(neworder))
            _datavals = data[self.dataName]['values']
            data[self.dataName]['axes'] = [_axnames[i] for i in neworder]
            _axnames = data[self.dataName]['axes']

            if self.squeeze:
                oldshape = _datavals.shape
                data[self.dataName]['values'] = np.squeeze(_datavals)
                for i, n in enumerate(_axnames):
                    if oldshape[i] < 2:
                        del data[self.dataName]['axes'][i]
                        del data[n]

        return data

class PlotWidget(QWidget):
    # TODO: use data adder thread.

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = None

    def setSource(self, source, autorun=True):
        self.source = source
        if isinstance(self.source, Node):
            self.source.dataProcessed.connect(self.run)
            if autorun:
                self.run(self.source._outputData)


    def run(self, data):
        self.data = data
        if self.data is not None:
            self.updatePlot()

    def updatePlot(self):
        self.plot.clearFig()


class LinePlotData(Node):

    def __init__(self):
        super().__init__()

        self._xaxisName = None
        self._traceNames = []

    @property
    def xaxisName(self):
        return self._xaxisName

    @xaxisName.setter
    def xaxisName(self, val):
        self._xaxisName = val
        self.optionsUpdated.emit()

    @property
    def traceNames(self):
        return self._traceNames

    @traceNames.setter
    def traceNames(self, val):
        self._traceNames = val
        self.optionsUpdated.emit()

    def processData(self, data):
        _data = super().processData(data)

        data = DataDict()
        for k in self.traceNames:
            data[k] = _data.get(k)
        if self.xaxisName in _data:
            data[self.xaxisName] = _data[self.xaxisName]

        return data


class LinePlot(PlotWidget):

    def __init__(self, parent):
        super().__init__(parent=parent)
        ui = Ui_LinePlot()
        ui.setupUi(self)

        self.plot = ui.plot
        self.setSource(LinePlotData())

    def updatePlot(self):
        super().updatePlot()
        ax = self.plot.axes
        data = self.data
        src = self.source

        xvals = data.get(src.xaxisName, {}).get('values', None)
        for k, v in data.items():
            if k != src.xaxisName:
                yvals = data[k]['values']
                if xvals is not None:
                    ax.plot(xvals, yvals, 'o-', label=k)

        ax.legend(loc='best')
        ax.set_xlabel(src.xaxisName)
        self.plot.draw()


def dummyData1d(nvals):
    x = np.linspace(0, 10, nvals)
    y = np.cos(x)
    z = np.cos(x)**2
    d = DataDict(
        x = {'values' : x},
        y = {'values' : y, 'axes' : ['x']},
        z = {'values' : z, 'axes' : ['x']},
    )
    return d


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = QDialog()
    plot = LinePlot(window)
    window.show()

    datasrc = DataDictSourceNode()
    datasrc.setData(dummyData1d(3))

    plot.source.setSource(datasrc)
    plot.source.xaxisName = 'x'
    plot.source.traceNames = ['y']

    datasrc.setData(dummyData1d(11))

    # axsel = AxesSelector(source=datasrc)
    # print(axsel.axesList())

    sys.exit(app.exec_())