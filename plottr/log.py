"""
log.py

Handler and widget for logging in plottr.

Use the setupLogging method to create a logging widget/dialog.

If a logger is accessed via loggin.getLogger('plottr.*') the logging
widget will capture the log and display it.
"""

# TODO: unify with the one from instrumentserver. should maybe go into labcore?

import sys
from typing import Optional, Union
from plottr import QtWidgets, QtGui
import logging

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'

COLORS = {
    logging.ERROR : QtGui.QColor('red'),
    logging.WARNING : QtGui.QColor('orange'),
    logging.INFO : QtGui.QColor('green'),
    logging.DEBUG : QtGui.QColor('gray'),
    }

LEVEL = logging.INFO

class QLogHandler(logging.Handler):

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__()
        self.widget = QtWidgets.QTextEdit(parent)
        self.widget.setReadOnly(True)

    def emit(self, record: logging.LogRecord) -> None:
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
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None,
                 level: int = logging.INFO):
        super().__init__(parent)

        ### set up the graphical handler
        fmt = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s\n" +
                "    %(message)s",
            datefmt='%Y-%m-%d %H:%M:%S',
            )
        logTextBox = QLogHandler(self)
        logTextBox.setFormatter(fmt)

        # make the widget
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(logTextBox.widget)
        self.setLayout(layout)

        # configure the logger. delete pre-existing graphical handler.
        self.logger = getLogger()
        for h in self.logger.handlers:
            if isinstance(h, QLogHandler):
                self.logger.removeHandler(h)
                h.widget.deleteLater()
                del h

        self.logger.addHandler(logTextBox)
        self.logger.setLevel(level)


    def setLevel(self, level: int) -> None:
        self.logger.setLevel(level)


def logDialog(widget: QtWidgets.QWidget) -> QtWidgets.QDialog:
    layout = QtWidgets.QVBoxLayout()
    d = QtWidgets.QDialog()
    d.setLayout(layout)
    layout.addWidget(widget)
    d.setWindowTitle('Plottr | Log')
    return d


def setupLogging(level: int = logging.INFO,
                 makeDialog: bool = True) -> Union[QtWidgets.QDialog, LogWidget]:
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


def getLogger(module: str = '') -> logging.Logger:
    """
    Return the logger we use within the plottr framework.
    """
    mod = 'plottr'
    if module != '':
        if module.split('.')[0] == 'plottr':
            mod = module
        else:
            mod += f'.{module}'

    logger = logging.getLogger(mod)
    logger.setLevel(LEVEL)
    return logger


def enableStreamHandler(enable: bool = False) -> None:
    """
    enable/disable output to stderr. Enabling is useful when not
    using the UI logging window.
    """
    logger = getLogger()
    hasStreamHandler = False
    for h in logger.handlers:
        if isinstance(h, logging.StreamHandler):
            hasStreamHandler = True
            if not enable:
                logger.removeHandler(h)
                del h

    if enable and not hasStreamHandler:
        streamHandler = logging.StreamHandler(sys.stderr)
        fmt = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s\n" +
                "    %(message)s",
            datefmt='%Y-%m-%d %H:%M:%S',
            )
        streamHandler.setFormatter(fmt)
        logger.addHandler(streamHandler)
