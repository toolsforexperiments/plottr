import sys
import numpy as np
from pprint import pprint

from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication, QDialog, QWidget

from plottr.data.datadict import DataDict
from plottr.gui.ui_lineplot import Ui_LinePlot



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