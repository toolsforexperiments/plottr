from pprint import pprint

from matplotlib import rcParams
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavBar
from matplotlib.figure import Figure

from pyqtgraph.Qt import QtGui, QtCore

from ..node.node import Node

### matplotlib tools
def setMplDefaults():
    rcParams['figure.dpi'] = 150
    rcParams['figure.figsize'] = (4.5, 3)
    rcParams['savefig.dpi'] = 150
    rcParams['axes.grid'] = True
    rcParams['grid.linewidth'] = 0.5
    rcParams['grid.linestyle'] = ':'
    rcParams['font.family'] = 'Arial'
    rcParams['font.size'] = 6
    rcParams['lines.markersize'] = 4
    rcParams['lines.linestyle'] = '-'
    rcParams['savefig.transparent'] = False
    rcParams['figure.subplot.bottom'] = 0.15
    rcParams['figure.subplot.top'] = 0.85
    rcParams['figure.subplot.left'] = 0.15
    rcParams['figure.subplot.right'] = 0.9


def centers2edges(arr):
    e = (arr[1:] + arr[:-1]) / 2.
    e = np.concatenate(([arr[0] - (e[0] - arr[0])], e))
    e = np.concatenate((e, [arr[-1] + (arr[-1] - e[-1])]))
    return e


def pcolorgrid(xaxis, yaxis):
    xedges = centers2edges(xaxis)
    yedges = centers2edges(yaxis)
    xx, yy = np.meshgrid(xedges, yedges)
    return xx, yy


class PlotNode(Node):

    nodeName = 'Plot'
    terminals = {
        'dataIn' : {'io' : 'in'},
    }

    newPlotData = QtCore.pyqtSignal(object)

    def setPlotWidget(self, widget):
        self.plotWidget = widget
        self.newPlotData.connect(self.plotWidget.setData)

    def process(self, **kw):
        data = kw['dataIn']
        self.newPlotData.emit(data)


class MPLPlot(FCanvas):

    def __init__(self, parent=None, width=4, height=3,
                 dpi=150, nrows=1, ncols=1):

        setMplDefaults()
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)

        self.clearFig(nrows, ncols)
        self.setParent(parent)

    def clearFig(self, nrows=1, ncols=1):
        self.fig.clear()

        self.axes = []
        naxes = nrows * ncols
        for i in range(1,nrows+1):
            for j in range(1,ncols+1):
                self.axes.append(self.fig.add_subplot(naxes, i, j))

        self.draw()


class MPLPlotWidget(QtGui.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.plot = MPLPlot()
        layout = QtGui.QVBoxLayout(self)
        layout.addWidget(self.plot)
        layout.addWidget(NavBar(self.plot, self))

    def setData(self, data):
        raise NotImplementedError


class AutoPlot(MPLPlotWidget):
    # TODO: the y-label generation is a bit crude like this.

    MAXYLABELS = 3

    def _plot1d(self, data, ax, axName, dNames):
        ylabel = ""
        nylabels = 0
        for n in dNames:
            x = data[axName]['values']
            y = data[n]['values']
            ax.plot(x, y, 'o-', mfc='None', mew=1, lw=0.5, label=n)

            if nylabels < self.MAXYLABELS:
                ylabel += "{} ({}); ".format(n, data[n]['unit'])
                nylabels += 1

        ylabel = ylabel[:-2]
        if len(dNames) > self.MAXYLABELS:
            ylabel += '; [...]'
        ax.set_ylabel(ylabel)
        ax.set_xlabel(axName + " ({})".format(data[axName]['unit']))
        ax.legend()


    def setData(self, data):
        axesNames = data.axes_list()
        dataNames = data.dependents()

        naxes = len(axesNames)
        ndata = len(dataNames)

        if naxes == 1:
            self.plot.clearFig(1, 1)
            ax = self.plot.axes[0]
            self._plot1d(data, ax, axesNames[0], dataNames)

        self.plot.draw()
