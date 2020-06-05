import sys
import os
import argparse

from plottr import QtGui
from plottr.apps.monitr import Monitr

QtWidgets = QtGui


def main(path, refresh_interval):
    app = QtWidgets.QApplication([])
    win = Monitr(path, refresh_interval)
    win.show()
    return app.exec_()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Monitr main application')
    parser.add_argument("path", help="path to monitor for data", default=None)
    parser.add_argument("-r", "--refresh_interval", default=2,
                        help="interval at which to look for changes in the "
                             "monitored path (in seconds)")
    args = parser.parse_args()

    path = os.path.abspath(args.path)
    if not (os.path.exists(path) and os.path.isdir(path)):
        print('Invalid path.')
        sys.exit()
    else:
        main(path=os.path.abspath(args.path), refresh_interval=args.refresh_interval)
