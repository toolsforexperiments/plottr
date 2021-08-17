"""A set of simple tests of the MPL FigureMaker classes."""

import numpy as np

from plottr import QtWidgets
from plottr.plot.base import ComplexRepresentation
from plottr.plot.mpl.autoplot import FigureMaker, PlotType
from plottr.plot.mpl.widgets import figureDialog


def test_multiple_line_plots(single_panel: bool = False):
    """plot a few 1d traces."""
    fig, win = figureDialog()

    setpts = np.linspace(0, 10, 101)
    data_1 = np.cos(setpts)

    with FigureMaker(fig) as fm:
        fm.plotType = PlotType.multitraces if single_panel else PlotType.singletraces

        line_1 = fm.addData(setpts, data_1, labels=['x', r'$\cos(x)$'])
        _ = fm.addData(setpts, data_1 ** 2, labels=['x', r'$\cos^2(x)$'])
        _ = fm.addData(setpts, data_1 ** 3, labels=['x', r'$\cos^3(x)$'])

    return win


def test_complex_line_plots(single_panel: bool = False,
                            mag_and_phase_format: bool = False):
    """Plot a couple of complex traces"""
    fig, win = figureDialog()

    setpts = np.linspace(0, 10, 101)
    data_1 = np.exp(-1j * setpts)
    data_2 = np.conjugate(data_1)

    with FigureMaker(fig) as fm:
        if mag_and_phase_format:
            fm.complexRepresentation = ComplexRepresentation.magAndPhase
        fm.plotType = PlotType.multitraces if single_panel else PlotType.singletraces

        line_1 = fm.addData(setpts, data_1, labels=['x', r'$\exp(-ix)$'])
        _ = fm.addData(setpts, data_2, labels=['x', r'$\exp(ix)$'])

    return win


def main():
    app = QtWidgets.QApplication([])

    wins = []

    wins.append(
        test_multiple_line_plots())
    wins.append(
        test_multiple_line_plots(single_panel=True))
    # wins.append(
    #     test_complex_line_plots())
    # wins.append(
    #     test_complex_line_plots(single_panel=True))
    # wins.append(
    #     test_complex_line_plots(mag_and_phase_format=True))
    wins.append(
        test_complex_line_plots(single_panel=True, mag_and_phase_format=True))

    for w in wins:
        w.show()
    return app.exec_()


if __name__ == '__main__':
    main()
