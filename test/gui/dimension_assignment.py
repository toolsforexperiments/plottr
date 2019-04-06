"""dimension_assignment.py

Testing for axis settings / dimension-reduction widgets.
"""

from plottr import QtGui
from plottr.data.datadict import datadict_to_meshgrid
from plottr.gui.tools import widgetDialog
from plottr.node.dim_reducer import XYSelectionWidget, DimensionReducer, DimensionReducerWidget
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
    selector = fc.nodes()['reducer']
    dialog = widgetDialog(selector.ui, 'reducer')

    data = datadict_to_meshgrid(
        testdata.three_compatible_3d_sets(5, 5, 5)
    )
    fc.setInput(dataIn=data)

    if not interactive:
        app.exec_()
    else:
        return dialog, fc
