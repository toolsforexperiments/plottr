"""grid_options.py

Testing Widgets for the gridding node.
"""

from plottr import QtGui
from plottr.data.datadict import datadict_to_meshgrid
from plottr.gui.tools import widgetDialog
from plottr.node.grid import GridOptionWidget, ShapeSpecificationWidget, DataGridder, GridOption
from plottr.utils import testdata
from plottr.node.tools import linearFlowchart


def test_shapeSpecWidget():
    def cb(val):
        print(val)

    widget = ShapeSpecificationWidget()
    widget.newShapeNotification.connect(cb)

    # set up the UI, feed data in
    dialog = widgetDialog(widget)
    widget.setAxes(['x', 'y', 'aVeryVeryVeryVeryLongAxisName'])

    widget.setShape({
        'order': ['x', 'y', 'aVeryVeryVeryVeryLongAxisName'],
        'shape': (5,5,5),
    })

    widget.setShape({
        'order': ['y', 'x', 'aVeryVeryVeryVeryLongAxisName'],
        'shape': (11, 4, -9),
    })

    return dialog


def test_gridOptionWidget():
    def cb(val):
        print(val)

    widget = GridOptionWidget()
    widget.optionSelected.connect(cb)

    # set up the UI, feed data in
    data = datadict_to_meshgrid(
        testdata.three_compatible_3d_sets(5, 5, 5)
    )
    dialog = widgetDialog(widget)
    widget.setAxes(data.axes())

    widget.setShape({
        'order': ['x', 'y', 'z'],
        'shape': (5,5,5),
    })

    return dialog


def test_GridNode():
    def cb(val):
        print(val)

    fc = linearFlowchart(('grid', DataGridder))
    gridder = fc.nodes()['grid']
    dialog = widgetDialog(gridder.ui, 'gridder')

    data = testdata.three_compatible_3d_sets(2, 2, 2)
    fc.setInput(dataIn=data)

    gridder.shapeDetermined.connect(cb)

    gridder.grid = GridOption.guessShape, {}
    gridder.grid = GridOption.specifyShape, \
                   dict(order=['x', 'y', 'z'], shape=(2,2,3))
    gridder.grid = GridOption.guessShape, {}
    gridder.grid = GridOption.specifyShape, \
                   dict(order=['x', 'y', 'z'], shape=(2,2,3))

    return dialog, fc
