from matplotlib import rcParams
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavBar
from matplotlib.figure import Figure


### matplotlib tools
def setMplDefaults():
    rcParams['figure.dpi'] = 150
    rcParams['figure.figsize'] = (4.5, 3)
    rcParams['savefig.dpi'] = 150
    rcParams['axes.grid'] = True
    rcParams['grid.linewidth'] = 0.5
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


class MPLPlot(FCanvas):

    def __init__(self, parent=None, width=4, height=3, dpi=150):
        setMplDefaults()
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)

        super().__init__(self.fig)
        self.setParent(parent)

    def clearFig(self):
        self.fig.clear()
        self.axes = self.fig.add_subplot(111)
        self.draw()