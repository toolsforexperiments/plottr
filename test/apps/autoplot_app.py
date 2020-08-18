import sys
import logging

from plottr import QtCore, QtWidgets

from plottr.utils import testdata
from plottr.apps.autoplot import autoplot
from plottr import log as plottrlog


def make_data():
    # d = testdata.three_incompatible_3d_sets(51, 51, 21)
    d = testdata.three_compatible_3d_sets(51, 51, 21)
    return d


def main():
    plottrlog.LEVEL = logging.DEBUG
    data = make_data()

    app = QtWidgets.QApplication([])
    fc, win = autoplot(inputData=data)

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtWidgets.QApplication.instance().exec_()


if __name__ == '__main__':
    main()
