import sys
import numpy as np

from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication, QDialog, QWidget

from plottr.data.datadict import DataDict
from plottr.gui.ui_lineplot import Ui_LinePlot


class Node(QObject):

    dataProcessed = pyqtSignal(object)
    optionsUpdated = pyqtSignal()

    def __init__(self, source=None):
        super().__init__()
        self._inputData = None
        self._outputData = None

        self.setSource(source)
        self.optionsUpdated.connect(self.update)

    def setSource(self, source, autorun=True):
        self._source = source
        if isinstance(self._source, Node):
            self._source.dataProcessed.connect(self.run)
            if autorun:
                self.run(self._source._outputData)

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

    def processData(self, data):
        print('process:', self, data)
        return data


class DataDictSourceNode(Node):

    def __init__(self):
        super().__init__(source=None)

    def setData(self, data):
        self._inputData = data
        self.run(data)


### seems uneccessary... put in data class?
class AxesSelector(Node):

    def __init__(self, source):
        super().__init__(source)
        self._axesNames = None

    def axesList(self, dataName=None):
        lst = []
        if self._inputData is not None:
            if dataName is None:
                for k, v in self._inputData.items():
                    if 'axes' in v:
                        for n in v['axes']:
                            if n not in lst:
                                lst.append(n)
            else:
                if dataName in self._inputData and 'axes' in self._inputData:
                    lst = self._inputData['axes']

        return lst

    @property
    def axesNames(self):
        return self._axesNames

    @axesNames.setter
    def axesNames(self, vals):
        axlst = []
        for v in vals:
            if v not in self.axesList():
                raise ValueError("'{}' is not a valid axis".format(v))
            if v in axlst:
                raise ValueError("'{}' specified multiple times.".format(v))
            axlst.append(v)
        self._axesNames = axlst




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

    axsel = AxesSelector(source=datasrc)
    print(axsel.axesList())

    sys.exit(app.exec_())