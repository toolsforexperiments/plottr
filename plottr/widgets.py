"""
widgets.py

Common GUI widgets that are re-used across plottr.
"""

from typing import Union, List, Tuple

from pyqtgraph.Qt import QtGui, QtCore


__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


class FormLayoutWrapper(QtGui.QWidget):
    """
    Simple wrapper widget for forms.
    Expects a list of tuples of the form (label, widget),
    creates a widget that contains these using a form layout.
    Labels have to be unique.
    """

    def __init__(self, elements: List[Tuple[str, QtGui.QWidget]],
                 parent: Union[None, QtGui.QWidget] = None):
        super().__init__(parent)

        self.elements = {}

        layout = QtGui.QFormLayout()
        for lbl, widget in elements:
            self.elements[lbl] = widget
            layout.addRow(lbl, widget)

        self.setLayout(layout)


class MonitorIntervalInput(QtGui.QWidget):
    """
    Simple form-like widget for entering a monitor/refresh interval.
    Only has a label and a spin-box as input.

    It's signal `intervalChanged(int)' is emitted when the value
    of the spinbox has changed.
    """

    intervalChanged = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.spin = QtGui.QSpinBox()
        layout = QtGui.QFormLayout()
        layout.addRow('Refresh interval (s)', self.spin)
        self.setLayout(layout)

        self.spin.valueChanged.connect(self.spinValueChanged)

    @QtCore.pyqtSlot(int)
    def spinValueChanged(self, val):
        self.intervalChanged.emit(val)
