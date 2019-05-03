from plottr import QtGui
from plottr.gui.tools import widgetDialog
from plottr.node.data_selector import DataSelector
from plottr.node.tools import linearFlowchart
from plottr.utils import testdata


def test_data_selector(interactive=True):
    if not interactive:
        app = QtGui.QApplication([])

    fc = linearFlowchart(('selector', DataSelector))
    selector = fc.nodes()['selector']
    dialog = widgetDialog(selector.ui, 'selector')

    data = testdata.three_incompatible_3d_sets(2, 2, 2)
    fc.setInput(dataIn=data)
    selector.selectedData = ['data']

    # for testing purposes, insert differently structured data
    data2 = testdata.two_compatible_noisy_2d_sets()
    fc.setInput(dataIn=data2)

    # ... and go back.
    fc.setInput(dataIn=data)
    selector.selectedData = ['data']

    if not interactive:
        app.exec_()
    else:
        return dialog, fc


if __name__ == '__main__':
    test_data_selector(False)
