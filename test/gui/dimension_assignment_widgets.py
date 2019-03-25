"""dimension_assignment_widgets.py

Testing for axis settings / dimension-reduction widgets.
"""

from plottr import QtGui
from plottr.gui.tools import widgetDialog
from plottr.utils import testdata
from plottr.node.dim_reducer import DimensionAssignmentWidget

def axisReductionWidget():
    # def selectionCb(selection):
    #     print(selection)

    app = QtGui.QApplication([])
    widget = DimensionAssignmentWidget()
    # widget.dataSelectionMade.connect(selectionCb)

    # set up the UI, feed data in
    data = testdata.three_incompatible_3d_sets(5, 5, 5)
    dialog = widgetDialog(widget)
    widget.setData(data)
    # widget.clear()
    # widget.setData(data)
    return app.exec_()
