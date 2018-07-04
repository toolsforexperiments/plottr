import sys
import numpy as np
from pprint import pprint

from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication, QDialog, QWidget

from plottr.data.datadict import DataDict
from plottr.gui.ui_lineplot import Ui_LinePlot


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




### UNTESTED SO FAR

class PlotWidget(QWidget, NodeBase):
    # TODO: use data adder thread.

    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def run(self):
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
    @Node.updateOption
    def xaxisName(self, val):
        self._xaxisName = val

    @property
    def traceNames(self):
        return self._traceNames

    @traceNames.setter
    @Node.updateOption
    def traceNames(self, val):
        self._traceNames = val

    def processData(self):
        _data = self.getInputData()

        data = DataDict()
        for k in self.traceNames:
            data[k] = _data.get(k)
        if self.xaxisName in _data:
            data[self.xaxisName] = _data[self.xaxisName]

        return data


class LinePlot(PlotWidget):

    def __init__(self, parent):
        super().__init__(parent)
        ui = Ui_LinePlot()
        ui.setupUi(self)

        self.plot = ui.plot

    def updatePlot(self):
        super().updatePlot()
        ax = self.plot.axes
        data = self.getInputData()
        src = self._sources['input']['ref']

        xvals = data.get(src.xaxisName, {}).get('values', None)
        ntraces = 0
        for k, v in data.items():
            if k != src.xaxisName:
                yvals = data[k]['values']
                if xvals is not None:
                    ax.plot(xvals, yvals, 'o-', label=k)
                    ntraces += 1

        if ntraces > 0:
            ax.legend(loc='best')
        ax.set_xlabel(src.xaxisName)
        self.plot.draw()



### OLD STUFF BELOW

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