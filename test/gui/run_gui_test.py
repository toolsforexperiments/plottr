import argparse

from data_display_widgets import dataSelectionWidget
from dimension_assignment import xySelectionWidget, dimReduction, xySelection
from grid_options import shapeSpecWidget, gridOptionWidget, gridder

funcmap = {
    'dataselect': (dataSelectionWidget, [], {}),
    'dataselect-readonly': (dataSelectionWidget, [True, ], {}),

    'xyselection-widget': (xySelectionWidget, [], {}),
    'xyselection': (xySelection, [], dict(interactive=False)),
    'dim-reductions': (dimReduction, [], dict(interactive=False)),

    'grid-shapespec-widget': (shapeSpecWidget, [], dict()),
    'grid-widget': (gridOptionWidget, [], dict()),
    'grid' : (gridder, [], dict(interactive=False))
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
