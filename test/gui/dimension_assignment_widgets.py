"""dimension_assignment_widgets.py

Testing for axis settings / dimension-reduction widgets.
"""

from plottr import QtGui, QtCore
from plottr.gui.tools import widgetDialog
from plottr.utils import testdata
from plottr.node.dim_reducer import DimensionAssignmentWidget
from plottr.data.datadict import DataDict

class TestWidget(DimensionAssignmentWidget):

    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)

        self.availableChoices[DataDict] += ['Boo!']

    def setRole(self, dim, role, **kw):
        super().setRole(dim, role, **kw)

        item = self.findItems(dim, QtCore.Qt.MatchExactly, 0)[0]
        if role == 'Boo!':
            idx = kw.get('value', 0)
            w = self._makeSlider(value=idx)
            w.valueChanged.connect(lambda x: self.sliderChange(dim, role, x))

            self.choices[dim]['optionsWidget'] = w
            self.setItemWidget(item, 2, w)

    def getRole(self, name):
        role, opts = super().getRole(name)

        if role == 'Boo!':
            opts['value'] = self.choices[name]['optionsWidget'].value()

        return role, opts

    def sliderChange(self, name, role, value):
        self.rolesChanged.emit(self.getRoles())

    def _makeSlider(self, value=0):
        npts = 5
        w = QtGui.QSlider(0x01)
        w.setMinimum(0)
        w.setMaximum(npts-1)
        w.setSingleStep(1)
        w.setPageStep(1)
        w.setTickInterval(10)
        w.setTickPosition(QtGui.QSlider.TicksBelow)
        w.setValue(value)
        return w


def axisReductionWidget():
    def selectionCb(selection):
        print(selection)

    app = QtGui.QApplication([])
    widget = TestWidget()
    widget.rolesChanged.connect(selectionCb)

    # set up the UI, feed data in
    data = testdata.three_incompatible_3d_sets(5, 5, 5)
    dialog = widgetDialog(widget)
    widget.setData(data)
    widget.clear()
    widget.setData(data)
    return app.exec_()
