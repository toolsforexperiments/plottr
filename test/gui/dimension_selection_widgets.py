import argparse
from typing import Tuple

from plottr import QtWidgets
from plottr.data.datadict import str2dd
from plottr.gui.widgets import AxisSelector, DependentSelector, DimensionSelector, \
    MultiDimensionSelector
from plottr.gui.tools import widgetDialog


def main(multi=False):
    def cb(value):
        print('Selection made:', value)

    data = str2dd("data1(x,y,z); data2(x,z);")

    if not multi:
        w = DimensionSelector()
        combo = w.combo
        combo.setDimensions(data.axes()+data.dependents())
        combo.dimensionSelected.connect(cb)
    else:
        w = MultiDimensionSelector()
        w.setDimensions(data.axes()+data.dependents())
        w.dimensionSelectionMade.connect(cb)

    return widgetDialog(w)


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    dialog = main(multi=True)
    app.exec_()
