"""data_display_widgets.py

Testing scripts for GUI elements for data display.
"""
import argparse

from plottr import QtGui
from plottr.gui.tools import widgetDialog
from plottr.gui.data_display import DataSelectionWidget
from plottr.utils import testdata


def dataSelectionWidget(readonly=False):
    def selectionCb(selection):
        print(selection)

    app = QtGui.QApplication([])
    widget = DataSelectionWidget(readonly=readonly)
    widget.dataSelectionMade.connect(selectionCb)

    # set up the UI, feed data in
    data = testdata.three_incompatible_3d_sets(5, 5, 5)
    dialog = widgetDialog(widget)
    widget.setData(data)
    widget.clear()
    widget.setData(data)
    return app.exec_()


funcmap = {
    'dataselect': (dataSelectionWidget, [], {}),
    'dataselect-readonly': (dataSelectionWidget, [True, ], {}),
}


def main(name):
    if name is None:
        return 0

    func, arg, kw = funcmap[name]
    func(*arg, **kw)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Testing data display widgets')
    parser.add_argument('name', help='which test to run', default=None,
                        choices=list(funcmap.keys()))

    args = parser.parse_args()
    main(args.name)
