import numpy as np

from plottr import QtWidgets
from plottr.plot.base import ComplexRepresentation
from plottr.plot.mpl import FigureMaker, AutoPlot
from plottr.plot.mpl.widgets import figureDialog


def test_multiple_line_plots(single_panel: bool = False):
    """plot a few 1d traces."""
    fig, win = figureDialog()

    setpts = np.linspace(0, 10, 101)
    data_1 = np.cos(setpts)

    with FigureMaker(fig) as fm:
        line_1 = fm.addData(setpts, data_1, labels=['x', r'$\cos(x)$'])

        kwargs = {}
        if single_panel:
            kwargs['join'] = line_1
        _ = fm.addData(setpts, data_1 ** 2,
                       labels=['x', r'$\cos^2(x)$'], **kwargs)
        _ = fm.addData(setpts, data_1 ** 3,
                       labels=['x', r'$\cos^3(x)$'], **kwargs)

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
            fm.complex_representation = ComplexRepresentation.magAndPhase

        line_1 = fm.addData(setpts, data_1, labels=['x', r'$\exp(-ix)$'])
        kwargs = {}
        if single_panel:
            kwargs['join'] = line_1
        _ = fm.addData(setpts, data_2,
                        labels=['x', r'$\exp(ix)$'], **kwargs)

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
