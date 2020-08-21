"""data_display_widgets.py

Testing scripts for GUI elements for data display.
"""

from plottr import QtWidgets
from plottr.gui.tools import widgetDialog
from plottr.gui.data_display import DataSelectionWidget
from plottr.utils import testdata


def test_dataSelectionWidget(readonly: bool = False):
    def selectionCb(selection):
        print(selection)

    # app = QtWidgets.QApplication([])
    widget = DataSelectionWidget(readonly=readonly)
    widget.dataSelectionMade.connect(selectionCb)

    # set up the UI, feed data in
    data = testdata.three_incompatible_3d_sets(5, 5, 5)
    dialog = widgetDialog(widget)
    widget.setData(data.structure(), data.shapes())
    widget.clear()
    widget.setData(data.structure(), data.shapes())
    return dialog

