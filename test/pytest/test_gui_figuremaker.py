"""GUI smoke tests for the matplotlib and pyqtgraph FigureMaker classes.

These verify that both plotting backends can build line plots, images and
scatter plots (including complex data) without raising under the active Qt
binding (PySide6 by default).

They are the pytest-qt successors of the old interactive scripts that used to
live under ``test/gui`` (``mpl_figuremaker.py`` and
``pyqtgraph_figuremaker.py``).
"""

import numpy as np

from plottr.plot.base import ComplexRepresentation, PlotDataType
from plottr.plot.mpl.autoplot import FigureMaker as MPLFigureMaker, PlotType
from plottr.plot.mpl.widgets import figureDialog
from plottr.plot.pyqtgraph.autoplot import FigureMaker as PGFigureMaker


# -- matplotlib ----------------------------------------------------------------

def test_mpl_multiple_line_plots(qtbot):
    """Several real 1d traces produce at least one axes."""
    fig, win = figureDialog()
    qtbot.addWidget(win)

    setpts = np.linspace(0, 10, 101)
    data = np.cos(setpts)
    with MPLFigureMaker(fig) as fm:
        fm.plotType = PlotType.singletraces
        line = fm.addData(setpts, data, labels=['x', r'$\cos(x)$'])
        fm.addData(setpts, data ** 2, labels=['x', r'$\cos^2(x)$'])
        fm.addData(setpts, data ** 3, labels=['x', r'$\cos^3(x)$'])
        assert line is not None

    assert len(fig.axes) > 0


def test_mpl_complex_line_plots(qtbot):
    """Complex traces in mag-and-phase format produce axes."""
    fig, win = figureDialog()
    qtbot.addWidget(win)

    setpts = np.linspace(0, 10, 101)
    data_1 = np.exp(-1j * setpts)
    data_2 = np.conjugate(data_1)
    with MPLFigureMaker(fig) as fm:
        fm.complexRepresentation = ComplexRepresentation.magAndPhase
        fm.plotType = PlotType.multitraces
        fm.addData(setpts, data_1, labels=['x', r'$\exp(-ix)$'])
        fm.addData(setpts, data_2, labels=['x', r'$\exp(ix)$'])

    assert len(fig.axes) > 0


# -- pyqtgraph -----------------------------------------------------------------

def test_pyqtgraph_basic_line_plot(qtbot):
    """Line + scatter 1d traces produce a widget."""
    x = np.linspace(0, 10, 51)
    y = np.cos(x)
    with PGFigureMaker() as fm:
        line_1 = fm.addData(x, y, labels=['x', 'cos(x)'],
                            plotDataType=PlotDataType.line1d)
        fm.addData(x, y ** 2, labels=['x', 'cos^2(x)'],
                   join=line_1, plotDataType=PlotDataType.scatter1d)
        fm.addData(x, np.abs(y), labels=['x', '|cos(x)|'],
                   plotDataType=PlotDataType.line1d)
    qtbot.addWidget(fm.widget)
    assert fm.widget is not None


def test_pyqtgraph_images(qtbot):
    """2d grid images produce a widget."""
    x = np.linspace(0, 10, 51)
    y = np.linspace(-4, 2, 51)
    xx, yy = np.meshgrid(x, y, indexing='ij')
    zz = np.cos(xx) * np.exp(-yy ** 2)
    with PGFigureMaker() as fm:
        fm.addData(xx, yy, zz, labels=['x', 'y', 'fake data'],
                   plotDataType=PlotDataType.grid2d)
        fm.addData(xx, yy, zz[:, ::-1], labels=['x', 'y', 'fake data (mirror)'],
                   plotDataType=PlotDataType.grid2d)
    qtbot.addWidget(fm.widget)
    assert fm.widget is not None


def test_pyqtgraph_scatter2d(qtbot):
    """2d scatter data produces a widget."""
    x = np.linspace(0, 10, 21)
    y = np.linspace(-4, 2, 21)
    xx, yy = np.meshgrid(x, y, indexing='ij')
    zz = np.cos(xx) * np.exp(-yy ** 2)
    with PGFigureMaker() as fm:
        fm.addData(xx.flatten(), yy.flatten(), zz.flatten(),
                   labels=['x', 'y', 'fake data'],
                   plotDataType=PlotDataType.scatter2d)
    qtbot.addWidget(fm.widget)
    assert fm.widget is not None


def test_pyqtgraph_complex_line_plots(qtbot):
    """Complex 1d traces (single panel) produce a widget."""
    setpts = np.linspace(0, 10, 101)
    data_1 = np.exp(-1j * setpts)
    data_2 = np.conjugate(data_1)
    with PGFigureMaker() as fm:
        line_1 = fm.addData(setpts, data_1, labels=['x', 'exp(-ix)'])
        fm.addData(setpts, data_2, labels=['x', 'exp(ix)'], join=line_1)
    qtbot.addWidget(fm.widget)
    assert fm.widget is not None


def test_pyqtgraph_complex_images(qtbot):
    """Complex 2d images in mag-and-phase format produce a widget."""
    x = np.linspace(0, 10, 51)
    y = np.linspace(-4, 2, 51)
    xx, yy = np.meshgrid(x, y, indexing='ij')
    zz = np.exp(-1j * xx) * np.exp(-yy ** 2)
    with PGFigureMaker() as fm:
        fm.complexRepresentation = ComplexRepresentation.magAndPhase
        fm.addData(xx, yy, zz, labels=['x', 'y', 'fake data'],
                   plotDataType=PlotDataType.grid2d)
        fm.addData(xx, yy, np.conjugate(zz),
                   labels=['x', 'y', 'fake data (conjugate)'],
                   plotDataType=PlotDataType.grid2d)
    qtbot.addWidget(fm.widget)
    assert fm.widget is not None
