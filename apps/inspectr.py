import sys
import argparse

from pyqtgraph.Qt import QtCore, QtGui

from plottr import log as plottrlog
from plottr.apps import inspectr


def main(dbPath):
    app = QtGui.QApplication([])
    plottrlog.enableStreamHandler(True)

    win = inspectr.inspectr(dbPath=dbPath)
    win.show()

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='inspectr -- sifting through qcodes data.')
    parser.add_argument('--dbpath', help='path to qcodes .db file',
                        default=None)

    args = parser.parse_args()

    main(args.dbpath)
