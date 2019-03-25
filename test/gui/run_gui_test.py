import argparse

from plottr import QtGui
from plottr.gui.tools import widgetDialog
from plottr.gui.data_display import DataSelectionWidget
from plottr.utils import testdata

from data_display_widgets import dataSelectionWidget
from dimension_assignment_widgets import axisReductionWidget


funcmap = {
    'dataselect': (dataSelectionWidget, [], {}),
    'dataselect-readonly': (dataSelectionWidget, [True, ], {}),
    'axis-reductions' : (axisReductionWidget, [], {})
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
