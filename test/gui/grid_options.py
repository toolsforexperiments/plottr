"""grid_options.py

Testing Widgets for the gridding node.
"""

from plottr import QtGui
from plottr.data.datadict import datadict_to_meshgrid
from plottr.gui.tools import widgetDialog
from plottr.node.grid import GridOptionWidget, ShapeSpecificationWidget, DataGridder
from plottr.utils import testdata
from plottr.node.tools import linearFlowchart


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
    widget.setAxes(data.axes())
    widget.setShape(data.shape())

    return app.exec_()


def gridder(interactive=False):
    def cb(val):
        print(val)

    if not interactive:
        app = QtGui.QApplication([])

    fc = linearFlowchart(('grid', DataGridder))
    gridder = fc.nodes()['grid']
    dialog = widgetDialog(gridder.ui, 'gridder')

    data = testdata.three_compatible_3d_sets(2, 2, 2)
    fc.setInput(dataIn=data)

    if not interactive:
        gridder.shapeDetermined.connect(cb)
        app.exec_()
    else:
        return dialog, fc
