import sys
import numpy as np

from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication, QDialog, QWidget

from plottr.data.datadict import DataDict
from plottr.gui.ui_lineplot import Ui_LinePlot


class PlotData(QObject):

    dataProcessed = pyqtSignal(object)
    dataSet = pyqtSignal()
    optionsUpdated = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.dataSet.connect(self.processData)
        self.optionsUpdated.connect(self.processData)

    def setData(self, data):
        self.srcdata = data
        self.dataSet.emit()

    @pyqtSlot()
    def processData(self):
        return self.srcdata


class PlotWidget(QWidget):
    # TODO: use data adder thread.

    def __init__(self, parent):
        super().__init__(parent)

        self.data = None

    def setData(self, data):
        self.data = data

    def addData(self, newdata):
        if self.data is not None:
            self.data.append(newdata)
        else:
            self.data = newdata


class LinePlotData(PlotData):

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

    def processData(self):
        _data = super().processData()

        data = DataDict()
        for k in self.traceNames:
            data[k] = _data.get(k)
        if self.xaxisName in _data:
            data[self.xaxisName] = _data[self.xaxisName]

        self.dataProcessed.emit(data)
        return data


class LinePlot(PlotWidget):

    def __init__(self, parent):
        super().__init__(parent)
        ui = Ui_LinePlot()
        ui.setupUi(self)

        self.plot = ui.plot

        self.plotData = LinePlotData()
        self.plotData.dataProcessed.connect(self.updatePlot)


    @pyqtSlot(object)
    def updatePlot(self, data):
        ax = self.plot.axes

        xvals = data.get(self.plotData.xaxisName, {}).get('values', None)
        for k, v in data.items():
            if k != self.plotData.xaxisName:
                yvals = data[k]['values']
                if xvals is not None:
                    ax.plot(xvals, yvals, 'o-', label=k)

        ax.legend(loc='best')
        ax.set_xlabel(self.plotData.xaxisName)


def dummyData():
    x = np.linspace(0, 10, 101)
    y = np.cos(x)
    d = DataDict(
        x = {'values' : x},
        y = {'values' : y, 'axes' : ['x']},
    )
    return d


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = QDialog()
    plot = LinePlot(window)
    window.show()

    plot.plotData.setData(dummyData())
    plot.plotData.xaxisName = 'x'
    plot.plotData.traceNames = ['y']

    sys.exit(app.exec_())