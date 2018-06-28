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
    dataRequested = pyqtSignal()

    sources = ['input']

    @staticmethod
    def updateOption(func):
        def wrap(self, val):
            ret = func(self, val)
            self._uptodate = False
            self.optionsUpdated.emit()
            return ret
        return wrap


    def __init__(self):
        super().__init__()

        self._data = None
        self._updateOnSource = True
        self._updateOnOptionChange = True
        self._uptodate = False
        self._running = False
        self._sources = { s : {'ref' : None, 'data' : None}  for s in self.__class__.sources }

        self.optionsUpdated.connect(self.run)

        for k, v in self._sources.items():
            setattr(self, 'set' + k.capitalize(),
                lambda ref: self.setSource(k, ref))
            setattr(self, 'set' + k.capitalize() + 'Data',
                pyqtSlot(object)(lambda data: self.setSourceData(k, data)))
            setattr(self, 'get' + k.capitalize() + 'Data',
                lambda: self._sources[k]['data'])

    @property
    def updateOnSource(self):
        return self._updateOnSource

    @updateOnSource.setter
    def updateOnSource(self, val):
        self._updateOnSource = val

    @property
    def updateOnOptionChange(self):
        return self._updateOnOptionChange

    @updateOnOptionChange.setter
    def updateOnOptionChange(self, val):
        self._updateOnOptionChange = val

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, val):
        self._data = val
        self.broadcastData()

    @pyqtSlot()
    def broadcastData(self):
        self.dataProcessed.emit(self._data)

    def setSourceData(self, sourceName, value):
        if sourceName not in self._sources:
            raise ValueError("'{}' is not a recognized source.")

        self._sources[sourceName]['data'] = value
        if self.updateOnSource:
            self.run()
        else:
            self._uptodate = False

    def setSource(self, sourceName, ref):
        if sourceName not in self._sources:
            raise ValueError("'{}' is not a recognized source." )

        setfunc = getattr(self, 'set' + sourceName.capitalize() + 'Data')
        src = self._sources[sourceName]['ref']
        if src is not None:
            src.dataProcessed.disconnect(setfunc)
            self.dataRequested.disconnect(src.broadcastData)

        self._sources[sourceName]['ref'] = ref
        src = self._sources[sourceName]['ref']
        src.dataProcessed.connect(setfunc)
        self.dataRequested.connect(src.broadcastData)
        self.dataRequested.emit()


    @pyqtSlot()
    def run(self):
        if not self._running:
            self._running = True
            for n, s in self._sources.items():
                if s['ref'] is not None:
                    s['ref'].run()

            if not self._uptodate:
                self.data = self.processData()
                print('processed data:', self)
                pprint(self.data)
                print('')
                self._uptodate = True
                self._running = False

    def processData(self):
        return self.data


class DataSelector(Node):

    def __init__(self):
        super().__init__()

        self._dataName = None
        self._slices = {}
        self._grid = True
        self._axesOrder = {}
        self._squeeze = True

    @property
    def dataName(self):
        return self._dataName

    @dataName.setter
    @Node.updateOption
    def dataName(self, val):
        self._dataName = val

    @property
    def slices(self):
        return self._slices

    @slices.setter
    @Node.updateOption
    def slices(self, val):
        self._slices = val

    @property
    def grid(self):
        return self._grid

    @grid.setter
    @Node.updateOption
    def grid(self, val):
        self._grid = val

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

    def processData(self):
        data = self.getInputData()

        if data is None:
            return {}

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



### OLD STUFF BELOW


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