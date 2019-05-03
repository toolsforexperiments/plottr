"""dimension_assignment.py

Testing for axis settings / dimension-reduction widgets.
"""

from plottr import QtGui
from plottr.data.datadict import datadict_to_meshgrid
from plottr.gui.tools import widgetDialog
from plottr.node.dim_reducer import XYSelectionWidget, DimensionReducer, XYSelector
from plottr.node.tools import linearFlowchart
from plottr.utils import testdata


def xySelectionWidget():
    def selectionCb(selection):
        print(selection)

    app = QtGui.QApplication([])
    widget = XYSelectionWidget()
    widget.rolesChanged.connect(selectionCb)

    # set up the UI, feed data in
    data = datadict_to_meshgrid(
        testdata.three_compatible_3d_sets(5, 5, 5)
    )
    dialog = widgetDialog(widget)
    widget.setData(data)
    widget.clear()
    widget.setData(data)
    return app.exec_()


def dimReduction(interactive=False):
    if not interactive:
        app = QtGui.QApplication([])

    fc = linearFlowchart(('reducer', DimensionReducer))
    reducer = fc.nodes()['reducer']
    dialog = widgetDialog(reducer.ui, 'reducer')

    data = datadict_to_meshgrid(
        testdata.three_compatible_3d_sets(2, 2, 2)
    )
    fc.setInput(dataIn=data)

    if not interactive:
        app.exec_()
    else:
        return dialog, fc


def xySelection(interactive=False):
    if not interactive:
        app = QtGui.QApplication([])

    fc = linearFlowchart(('xysel', XYSelector))
    selector = fc.nodes()['xysel']
    dialog = widgetDialog(selector.ui, 'xysel')

    data = datadict_to_meshgrid(
        testdata.three_compatible_3d_sets(4, 4, 4)
    )
    fc.setInput(dataIn=data)

    if not interactive:
        app.exec_()
    else:
        return dialog, fc
