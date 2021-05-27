"""A set of simple tests of the pyqtgraph FigureMaker classes."""

import numpy as np

from plottr import QtWidgets
from plottr.gui.tools import widgetDialog
from plottr.plot.pyqtgraph.autoplot import FigureMaker


def test_single_line_plot():

    x = np.linspace(0, 10, 51)
    y = np.cos(x)

    with FigureMaker() as fm:
        line_1 = fm.addData(x, y)
        _ = fm.addData(x, y**2, join=line_1)

    return fm.layoutWidget

def main():
    app = QtWidgets.QApplication([])

    widgets = []

    widgets.append(
        test_single_line_plot()
    )

    # wins.append(
    #     test_multiple_line_plots())
    # wins.append(
    #     test_multiple_line_plots(single_panel=True))
    # wins.append(
    #     test_complex_line_plots())
    # wins.append(
    #     test_complex_line_plots(single_panel=True))
    # wins.append(
    #     test_complex_line_plots(mag_and_phase_format=True))
    # wins.append(
    #     test_complex_line_plots(single_panel=True, mag_and_phase_format=True))

    for w in widgets:
        dg = widgetDialog(w)
        dg.show()
    return app.exec_()


if __name__ == '__main__':
    main()