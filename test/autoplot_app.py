import sys
import logging

from pyqtgraph.Qt import QtCore, QtGui

from common import data
from plottr.apps import autoplot
from plottr import log as plottrlog

def make_data():
    d = data.three_incompatible_3d_sets(51, 51, 21)
    return d

def main():
    plottrlog.LEVEL = logging.DEBUG
    testdata = make_data()

    app = QtGui.QApplication([])
    fc, win = autoplot.autoplot(inputData=testdata, log=True)

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()

if __name__ == '__main__':
    main()
