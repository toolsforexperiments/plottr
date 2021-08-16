from matplotlib import cycler
from plottr.plot.pyqtgraph.autoplot import AutoPlot as PGAutoPlot
from plottr.plot.mpl.autoplot import AutoPlot as MPLAutoPlot

config = {

    'default-plotwidget': MPLAutoPlot,

    'matplotlibrc': {
        'axes.grid': True,
        'axes.prop_cycle': cycler('color', ['1f77b4', 'ff7f0e', '2ca02c', 'd62728', '9467bd', '8c564b',
                                            'e377c2', '7f7f7f', 'bcbd22', '17becf']),
        'figure.dpi': 150,
        'figure.figsize': (4.5, 3),
        'font.size': 6,
        'font.family': ['Helvetica', 'Arial', 'DejaVu Sans', 'Bitstream Vera Sans'],
        'grid.linewidth': 0.5,
        'grid.linestyle': '--',
        'image.cmap': 'magma',
        'legend.fontsize': 6,
        'legend.frameon': True,
        'legend.numpoints': 1,
        'legend.scatterpoints': 1,
        'lines.marker': 'o',
        'lines.markersize': '3',
        'lines.markeredgewidth': 1,
        'lines.markerfacecolor': 'w',
        'lines.linestyle': '-',
        'lines.linewidth': 1,
        'savefig.dpi': 300,
        'savefig.transparent': False,
    },

    'pyqtgraph': {
        'background': 'w',
        'foreground': 'k',
        'line_colors': ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'],
        'line_symbols': ['o', ],
        'line_symbol_size': 7,
        'minimum_plot_size': (400, 400),
    }
}
