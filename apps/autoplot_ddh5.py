import sys
import argparse

from plottr import QtGui
from plottr.apps.autoplot import autoplotDDH5


def main(f, g):
    app = QtGui.QApplication([])
    fc, win = autoplotDDH5(f, g)

    return app.exec_()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='plottr autoplot .dd.h5 files.'
    )
    parser.add_argument('--filepath', help='path to .dd.h5 file',
                        default='')
    parser.add_argument('--groupname', help='group in the hdf5 file',
                        default='data')
    args = parser.parse_args()

    main(args.filepath, args.groupname)
