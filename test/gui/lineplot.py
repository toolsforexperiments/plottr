import sys
import numpy as np

from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication, QDialog, QWidget

from plottr.data.datadict import DataDict
from plottr.gui.ui_lineplot import Ui_LinePlot


class PlotData(QObject):

    dataProcessed = pyqtSignal(object)

    def setData(self, data):
        self.srcdata = data

    def processData(self):
        self.data = self.srcdata


class GridPlotData(PlotData):
    pass


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

    def setXaxis(self, name):
        self.xaxisname = name

    def setTraces(self, names):
        self.tracenames = names

    def processData(self):
        super().processData()

        ret = []
        for dn in self.tracenames:
            if dn in self.data:
                if self.xaxisname in self.data[dn]['axes']:
                    ret.append(self.data[dn]['values'])
                else:
                    raise ValueError("Trace '{}' does not depend on '{}'".format(dn, self.xaxisname))
            else:
                raise ValueError("Trace '{}' not in dataset.".format(dn))

        return self.data[self.xaxisname]['values'], ret


class LinePlot(PlotWidget):

    def __init__(self, parent):
        super().__init__(parent)
        ui = Ui_LinePlot()
        ui.setupUi(self)

    def plot(self, x, ylst):
        for y in ylst:
            self.plot.axes.plot(x, y, 'o-')



def dummyData():
    x = np.linspace(0, 10, 11)
    y = np.cos(x)
    d = DataDict(
        x = {'values' : x},
        y = {'values' : y, axes=['x']},
    )
    return d


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = QDialog()
    plot = LinePlot(window)
    window.show()
    sys.exit(app.exec_())