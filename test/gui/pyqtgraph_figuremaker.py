"""A set of simple tests of the pyqtgraph FigureMaker classes."""

import numpy as np

from plottr import QtWidgets
from plottr.gui.tools import widgetDialog
from plottr.plot.base import PlotDataType, ComplexRepresentation
from plottr.plot.pyqtgraph.autoplot import FigureMaker


def test_basic_line_plot():
    x = np.linspace(0, 10, 51)
    y = np.cos(x)
    with FigureMaker() as fm:
        line_1 = fm.addData(x, y, labels=['x', 'cos(x)'],
                            plotDataType=PlotDataType.line1d)
        _ = fm.addData(x, y**2, labels=['x', 'cos^2(x)'],
                       join=line_1,
                       plotDataType=PlotDataType.scatter1d)
        line_2 = fm.addData(x, np.abs(y), labels=['x', '|cos(x)|'],
                            plotDataType=PlotDataType.line1d)
    return fm.widget


def test_images():
    x = np.linspace(0, 10, 51)
    y = np.linspace(-4, 2, 51)
    xx, yy = np.meshgrid(x, y, indexing='ij')
    zz = np.cos(xx) * np.exp(-yy**2)
    with FigureMaker() as fm:
        img1 = fm.addData(xx, yy, zz, labels=['x', 'y', 'fake data'],
                          plotDataType=PlotDataType.grid2d)
        img2 = fm.addData(xx, yy, zz[:, ::-1], labels=['x', 'y', 'fake data (mirror)'],
                          plotDataType=PlotDataType.grid2d)
    return fm.widget


def test_scatter2d():
    x = np.linspace(0, 10, 21)
    y = np.linspace(-4, 2, 21)
    xx, yy = np.meshgrid(x, y, indexing='ij')
    zz = np.cos(xx) * np.exp(-yy**2)
    with FigureMaker() as fm:
        s = fm.addData(xx.flatten(), yy.flatten(), zz.flatten(), labels=['x', 'y', 'fake data'],
                       plotDataType=PlotDataType.scatter2d)
    return fm.widget


def test_complex_line_plots(single_panel: bool = False,
                            mag_and_phase_format: bool = False):

    setpts = np.linspace(0, 10, 101)
    data_1 = np.exp(-1j * setpts)
    data_2 = np.conjugate(data_1)

    with FigureMaker() as fm:
        if mag_and_phase_format:
            fm.complexRepresentation = ComplexRepresentation.magAndPhase

        line_1 = fm.addData(setpts, data_1, labels=['x', r'exp(-ix)'])
        _ = fm.addData(setpts, data_2, labels=['x', r'exp(ix)'],
                       join=line_1 if single_panel else None)

    return fm.widget


def test_complex_images(mag_and_phase_format: bool = False):
    x = np.linspace(0, 10, 51)
    y = np.linspace(-4, 2, 51)
    xx, yy = np.meshgrid(x, y, indexing='ij')
    zz = np.exp(-1j*xx) * np.exp(-yy**2)
    with FigureMaker() as fm:
        if mag_and_phase_format:
            fm.complexRepresentation = ComplexRepresentation.magAndPhase

        img1 = fm.addData(xx, yy, zz, labels=['x', 'y', 'fake data'],
                          plotDataType=PlotDataType.grid2d)
        img2 = fm.addData(xx, yy, np.conjugate(zz), labels=['x', 'y', 'fake data (conjugate)'],
                          plotDataType=PlotDataType.grid2d)
    return fm.widget


def main():
    app = QtWidgets.QApplication([])
    widgets = []

    widgets.append(
        test_basic_line_plot())
    # widgets.append(
    #     test_images())
    # widgets.append(
    #     test_scatter2d())
    # widgets.append(
    #     test_complex_line_plots())
    # widgets.append(
    #     test_complex_line_plots(single_panel=True))
    # widgets.append(
    #     test_complex_line_plots(mag_and_phase_format=True))
    # widgets.append(
    #     test_complex_line_plots(single_panel=True, mag_and_phase_format=True))
    # widgets.append(
    #     test_complex_images())
    # widgets.append(
    #     test_complex_images(mag_and_phase_format=True))

    dgs = []
    for w in widgets:
        dgs.append(widgetDialog(w))
        dgs[-1].show()
    return app.exec_()


if __name__ == '__main__':
    main()