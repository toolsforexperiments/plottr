import io
import numpy as np
from matplotlib import rcParams, cm
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FCanvas,
    NavigationToolbar2QT as NavBar,
)
from matplotlib.figure import Figure
from mpl_toolkits.axes_grid1 import make_axes_locatable

from plottr.utils.num import (
    interp_meshgrid_2d, centers2edges_1d,
    centers2edges_2d
)
from .. import QtGui, QtCore
from ..data.datadict import DataDictBase, MeshgridDataDict, meshgrid_to_datadict
from ..node.node import Node
from ..utils import (
    num
)


# TODO: configurable plot options
# TODO: refactor into small plot methods, plot widgets/canvases/data checkers

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


def pcolorgrid(xaxis, yaxis):
    xedges = centers2edges_1d(xaxis)
    yedges = centers2edges_1d(yaxis)
    xx, yy = np.meshgrid(xedges, yedges)
    return xx, yy


def ppcolormesh_from_meshgrid(ax, x, y, z, **kw):
    cmap = kw.get('cmap', cm.viridis)

    x = x.astype(float)
    y = y.astype(float)
    z = z.astype(float)

    if np.ma.is_masked(x):
        x = x.filled(np.nan)
    if np.ma.is_masked(y):
        y = y.filled(np.nan)
    if np.ma.is_masked(z):
        z = z.filled(np.nan)

    if np.all(num.is_invalid(x)) or np.all(num.is_invalid(y)):
        return

    if np.any(np.isnan(x)) or np.any(np.isnan(y)):
        x, y = interp_meshgrid_2d(x, y)

    if np.any(num.is_invalid(x)) or np.any(num.is_invalid(y)):
        x, y, z = num.crop2d(x, y, z)

    for g in x, y, z:
        if g.size == 0:
            return
        elif len(g.shape) < 2:
            return
        elif min(g.shape) < 2:
            im = ax.scatter(x, y, c=z)
            return im

    try:
        x = centers2edges_2d(x)
        y = centers2edges_2d(y)
    except:
        return

    im = ax.pcolormesh(x, y, z, cmap=cmap, **kw)
    ax.set_xlim(x.min(), x.max())
    ax.set_ylim(y.min(), y.max())
    return im


class PlotNode(Node):
    """
    Basic Plot Node.

    ATM this doesn't do much besides passing data to the plotting widget.
    Data is at the moment just passed through.
    """
    nodeName = 'Plot'
    newPlotData = QtCore.pyqtSignal(object)

    def setPlotWidget(self, widget):
        self.plotWidget = widget
        self.newPlotData.connect(self.plotWidget.setData)

    def process(self, **kw):
        data = kw['dataIn']
        self.newPlotData.emit(data)
        return dict(dataOut=data)


class MPLPlot(FCanvas):
    """
    This is the basic matplotlib canvas widget we are using for matplotlib
    plots. ATM, this canvas only provides a few convenience tools for automatic
    sizing and creating subfigures, but is otherwise not very different
    from the class that comes with matplotlib.
    It can be used as any QT widget.
    """

    def __init__(self, parent: QtGui.QWidget = None, width: float = 4.0,
                 height: float = 3.0, dpi: int = 150, nrows: int = 1,
                 ncols: int = 1):
        """
        Create the canvas.

        :param parent: the parent widget
        :param width: canvas width (inches)
        :param height: canvas height (inches)
        :param dpi: figure dpi
        :param nrows: number of subplot rows
        :param ncols: number of subplot columns
        """

        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)

        self._tightLayout = False
        self._showInfo = False
        self._infoArtist = None
        self._info = ''

        self.clearFig(nrows, ncols)
        self.setParent(parent)

    def autosize(self):
        """
        Sets some default spacings/margins.
        :return:
        """
        if not self._tightLayout:
            self.fig.subplots_adjust(left=0.125, bottom=0.125, top=0.9,
                                     right=0.875,
                                     wspace=0.35, hspace=0.2)
        else:
            self.fig.tight_layout(rect=[0, 0.03, 1, 0.95])

        self.draw()

    def clearFig(self, nrows=1, ncols=1, naxes=1):
        """
        Clear and reset the canvas.

        :param nrows: number of subplot/axes rows to prepare
        :param ncols: number of subplot/axes column to prepare
        :param naxes: number of axes in total
        :return:
        """
        self.fig.clear()
        setMplDefaults()

        self.axes = []
        iax = 1
        if naxes > nrows * ncols:
            raise ValueError(
                f'Number of axes ({naxes}) larger than rows ({nrows}) x '
                f'columns ({ncols}).')

        for i in range(1, naxes + 1):
            kw = {}
            if iax > 1:
                kw['sharex'] = self.axes[0]
                kw['sharey'] = self.axes[0]

            self.axes.append(self.fig.add_subplot(nrows, ncols, i))
            iax += 1

        self.autosize()
        return self.axes

    def resizeEvent(self, event):
        """
        Re-implementation of the widget resizeEvent method.
        Makes sure we resize the plots appropriately.
        """
        self.autosize()
        super().resizeEvent(event)

    def setTightLayout(self, tight: bool):
        """
        Set tight layout mode.
        :param tight: if true, use tight layout for autosizing.
        :return:
        """
        self._tightLayout = tight
        self.autosize()

    def setShowInfo(self, show: bool):
        """Whether to show additional info in the plot"""
        self._showInfo = show
        self.updateInfo()

    def updateInfo(self):
        if self._infoArtist is not None:
            self._infoArtist.remove()
            self._infoArtist = None

        if self._showInfo:
            self._infoArtist = self.fig.text(
                0, 0, self._info,
                fontsize='x-small',
                verticalalignment='bottom',
            )
        self.draw()

    def toClipboard(self):
        """
        Copy the current canvas to the clipboard.
        :return:
        """
        buf = io.BytesIO()
        self.fig.savefig(buf, dpi=300, facecolor='w', format='png',
                         transparent=True)
        QtGui.QApplication.clipboard().setImage(
            QtGui.QImage.fromData(buf.getvalue()))
        buf.close()

    def setFigureTitle(self, title: str):
        """Add a title to the figure."""
        self.fig.text(0.5, 0.99, title,
                      horizontalalignment='center',
                      verticalalignment='top',
                      fontsize='small')
        self.draw()

    def setFigureInfo(self, info: str):
        """Display an info string in the figure"""
        self._info = info
        self.updateInfo()


class MPLPlotContainer(QtGui.QWidget):
    """
    A widget that contains multiple MPL plots (each with their own tools).
    """
    pass


class MPLPlotWidget(QtGui.QWidget):
    """
    Base class for matplotlib-based plot widgets.
    Per default, add a canvas and the matplotlib NavBar.
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        setMplDefaults()

        self.plot = MPLPlot()
        self.mplBar = NavBar(self.plot, self)
        self.addMplBarOptions()

        self.toolLayout = QtGui.QHBoxLayout()

        self.layout = QtGui.QVBoxLayout(self)
        self.layout.addLayout(self.toolLayout)
        self.layout.addWidget(self.plot)
        self.layout.addWidget(self.mplBar)

    def setData(self, data: DataDictBase):
        raise NotImplementedError

    def setMeta(self, data: DataDictBase):
        if data.has_meta('title'):
            self.plot.setFigureTitle(data.meta_val('title'))

        if data.has_meta('info'):
            self.plot.setFigureInfo(data.meta_val('info'))

    def addMplBarOptions(self):
        tlCheck = QtGui.QCheckBox('Tight layout')
        tlCheck.toggled.connect(self.plot.setTightLayout)

        infoCheck = QtGui.QCheckBox('Info')
        infoCheck.toggled.connect(self.plot.setShowInfo)

        self.mplBar.addSeparator()
        self.mplBar.addWidget(tlCheck)
        self.mplBar.addSeparator()
        self.mplBar.addWidget(infoCheck)
        self.mplBar.addSeparator()
        self.mplBar.addAction('Copy', self.plot.toClipboard)


class AutoPlot(MPLPlotWidget):
    # TODO: the y-label generation is a bit crude like this.

    MAXYLABELS = 3

    def _plot1d(self, data, ax, axName, dNames):
        ylabel = ""
        nylabels = 0

        fmt = 'o'
        if isinstance(data, MeshgridDataDict):
            fmt = 'o-'

        for n in dNames:
            x = data[axName]['values']
            y = data[n]['values']
            ax.plot(x, y, fmt, mfc='None', mew=1, lw=0.5, label=n)

            if nylabels < self.MAXYLABELS:
                ylabel += data.label(n)
                ylabel += '; '
                nylabels += 1

        ylabel = ylabel[:-2]
        if len(dNames) > self.MAXYLABELS:
            ylabel += '; [...]'
        ax.set_ylabel(ylabel)
        ax.set_xlabel(data.label(axName))
        ax.legend()

    def _plot2d(self, data, ax, xName, yName, dName):
        x = data[xName]['values']
        y = data[yName]['values']
        z = data[dName]['values']
        if isinstance(data, MeshgridDataDict):
            im = ppcolormesh_from_meshgrid(ax, x, y, z)
        else:
            im = ax.scatter(x, y, c=z)

        if im is None:
            return

        div = make_axes_locatable(ax)
        cax = div.append_axes("right", size="5%", pad=0.05)
        self.plot.fig.colorbar(im, cax=cax)

        ax.set_title(dName, size='small')
        ax.set_ylabel(data.label(yName))
        ax.set_xlabel(data.label(xName))
        cax.set_ylabel(data.label(dName))

    def setData(self, data):
        if data is None:
            return

        axesNames = data.axes()
        dataNames = data.dependents()
        shape = data.shapes()[dataNames[0]]

        if 0 in shape:
            return
        if len(axesNames) == 2 and isinstance(data, MeshgridDataDict):
            if min(shape) < 2:
                data = meshgrid_to_datadict(data)

        naxes = len(axesNames)
        ndata = len(dataNames)

        if naxes == 0 or ndata == 0:
            self.plot.clearFig(naxes=0)
        elif naxes == 1:
            ax = self.plot.clearFig(1, 1, 1)[0]
            self._plot1d(data, ax, axesNames[0], dataNames)
        elif naxes == 2:
            nrows = ndata ** .5 // 1
            ncols = np.ceil(ndata / nrows)
            axes = self.plot.clearFig(nrows, ncols, ndata)
            for i, dn in enumerate(dataNames):
                ax = axes[i]
                self._plot2d(data, ax, axesNames[0], axesNames[1], dn)

        elif naxes > 2:
            raise ValueError(
                'Cannot plot more than two axes. (given: {})'.format(axesNames))

        self.setMeta(data)
        self.plot.autosize()
