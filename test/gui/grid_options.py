"""grid_options.py

Testing Widgets for the gridding node.
"""

from plottr import QtGui
from plottr.data.datadict import datadict_to_meshgrid
from plottr.gui.tools import widgetDialog
from plottr.node.grid import GridOptionWidget, ShapeSpecificationWidget
from plottr.utils import testdata


def shapeSpecWidget():
    def cb(val):
        print(val)

    app = QtGui.QApplication([])
    widget = ShapeSpecificationWidget()
    widget.newShapeNotification.connect(cb)

    # set up the UI, feed data in
    data = datadict_to_meshgrid(
        testdata.three_compatible_3d_sets(5, 5, 5)
    )
    dialog = widgetDialog(widget)
    widget.setAxes(data.axes())
    widget.setShape(data.shape())

    return app.exec_()


def gridOptionWidget():
    def cb(val):
        print(val)

    app = QtGui.QApplication([])
    widget = GridOptionWidget()
    widget.optionSelected.connect(cb)

    # set up the UI, feed data in
    data = datadict_to_meshgrid(
        testdata.three_compatible_3d_sets(5, 5, 5)
    )
    dialog = widgetDialog(widget)
    # widget.setAxes(data.axes())
    # widget.setShape(data.shape())

    return app.exec_()
