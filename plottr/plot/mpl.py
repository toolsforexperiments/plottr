from pprint import pprint

import numpy as np

from matplotlib import rcParams
from matplotlib import cm
from matplotlib import pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavBar
from matplotlib.figure import Figure
from mpl_toolkits.axes_grid1 import make_axes_locatable

from pyqtgraph.Qt import QtGui, QtCore

from ..node.node import Node

# TODO:
# * plot properties should be configurable

### matplotlib tools
def setMplDefaults():
    rcParams['figure.dpi'] = 300
    rcParams['figure.figsize'] = (4.5, 3)
    rcParams['savefig.dpi'] = 300
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

def ppcolormesh(ax, x, y, z, cmap=None, make_grid=True, **kw):
    if cmap is None:
        cmap = cm.viridis

    if make_grid:
        _x, _y = pcolorgrid(x, y)
    else:
        _x, _y = x, y

    im = ax.pcolormesh(_x, _y, z, cmap=cmap, **kw)
    ax.set_xlim(_x.min(), _x.max())
    ax.set_ylim(_y.min(), _y.max())

    return im


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

    def clearFig(self, nrows=1, ncols=1, naxes=1):
        self.fig.clear()

        self.axes = []
        iax = 1
        if naxes > nrows * ncols:
            raise ValueError(f'Number of axes ({naxes}) larger than rows ({nrows}) x columns ({ncols}).')

        for i in range(1,naxes+1):
            kw = {}
            if iax > 1:
                kw['sharex'] = self.axes[0]
                kw['sharey'] = self.axes[0]

            self.axes.append(self.fig.add_subplot(nrows, ncols, i))
            iax += 1

        self.fig.tight_layout()
        self.draw()
        return self.axes

    def resizeEvent(self, event):
        self.fig.tight_layout()
        super().resizeEvent(event)



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
        self.plot.fig.tight_layout()

    def _plot2d(self, data, ax, xName, yName, dName):
        x = data[xName]['values']
        y = data[yName]['values']
        zz = data[dName]['values'].T

        im = ppcolormesh(ax, x, y, zz)
        div = make_axes_locatable(ax)
        cax = div.append_axes("right", size="5%", pad=0.05)
        self.plot.fig.colorbar(im, cax=cax)

        ax.set_title(dName, size='small')
        ax.set_ylabel(yName + " ({})".format(data[yName]['unit']))
        ax.set_xlabel(xName + " ({})".format(data[xName]['unit']))
        cax.set_ylabel(dName + " ({})".format(data[dName]['unit']))
    

    def setData(self, data):
        axesNames = data.axes_list()
        dataNames = data.dependents()

        naxes = len(axesNames)
        ndata = len(dataNames)

        if naxes == 0 or ndata == 0:
            self.plot.clearFig(naxes=0)

        elif naxes == 1:
            ax = self.plot.clearFig(1, 1, 1)[0]
            self._plot1d(data, ax, axesNames[0], dataNames)
        elif naxes == 2:
            nrows = ndata**.5//1
            ncols = np.ceil(ndata/nrows)
            axes = self.plot.clearFig(nrows, ncols, ndata)
            for i, dn in enumerate(dataNames):
                ax = axes[i]
                self._plot2d(data, ax, axesNames[0], axesNames[1], dn)
                
        elif naxes > 2:
            raise ValueError('Cannot plot more than two axes. (given: {})'.format(axesNames))

        self.plot.fig.tight_layout()
        self.plot.draw()
