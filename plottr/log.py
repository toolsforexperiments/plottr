"""
log.py

Handler and widget for logging in plottr.

Use the setupLogging method to create a logging widget/dialog.

If a logger is accessed via loggin.getLogger('plottr.*') the logging
widget will capture the log and display it.
"""

import sys
from PyQt5 import QtWidgets, QtGui
import logging

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'

COLORS = {
    logging.ERROR : QtGui.QColor('red'),
    logging.WARNING : QtGui.QColor('orange'),
    logging.INFO : QtGui.QColor('green'),
    logging.DEBUG : QtGui.QColor('blue'),
    }

class QLogHandler(logging.Handler):
    def __init__(self, parent):
        super().__init__()
        self.widget = QtWidgets.QTextEdit(parent)
        self.widget.setReadOnly(True)

    def emit(self, record):
        msg = self.format(record)
        clr = COLORS.get(record.levelno, QtGui.QColor('black'))
        self.widget.setTextColor(clr)
        self.widget.append(msg)
        self.widget.verticalScrollBar().setValue(
            self.widget.verticalScrollBar().maximum()
        )


class LogWidget(QtWidgets.QWidget):
    """
    A simple logger widget. Uses QLogHandler as handler.
    Does not do much else.
    """

    def __init__(self, parent=None, level=logging.DEBUG):
        super().__init__(parent)

        fmt = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s\n" +
                "    %(message)s",
            datefmt='%Y-%m-%d %H:%M:%S',
            )
        logTextBox = QLogHandler(self)
        logTextBox.setFormatter(fmt)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(logTextBox.widget)
        self.setLayout(layout)

        self.logger = logging.getLogger('plottr')
        self.logger.addHandler(logTextBox)
        self.logger.setLevel(level)

    def setLevel(self, level):
        self.logger.setLevel(level)


def logDialog(widget):
    layout = QtWidgets.QVBoxLayout()
    d = QtWidgets.QDialog()
    d.setLayout(layout)
    layout.addWidget(widget)
    d.setWindowTitle('Plottr Log')
    return d


def setupLogging(level=logging.INFO, makeDialog=True):
    """
    Setup logging for plottr. Creates the widget and handler.
    if makeDialog is True, embed the widget into the dialog.
    Returns either the widget or the dialog.
    """
    w = LogWidget(level=level)
    if makeDialog:
        d = logDialog(w)
        d.show()
        return d
    else:
        return w
