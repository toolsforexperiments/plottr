import sys
import os
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (QApplication,
                             QFrame, QHBoxLayout, QLabel,
                             QMainWindow,QSizePolicy,
                             QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                             QWidget)


FN = "./experiments.db"

class CentralW(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        print(event.mimeData().urls())
        event.accept()

    def dropEvent(self, event):
        print(event)


class InspectrMain(QMainWindow):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle('inspectr')
        self.activateWindow()

        self.centralWidget = CentralW()
        self.setCentralWidget(self.centralWidget)
        self.centralWidget.setFocus()

    def setFilePath(self, filepath):
        if filepath:
            self.filepath = os.path.abspath(filepath)
            self.setWindowTitle('inspectr - {}'.format(self.filepath))


if __name__ == "__main__":
    nargs = len(sys.argv) - 1
    if nargs > 0:
        fp = sys.argv[1]
    else:
        fp = None

    app = QApplication(sys.argv)
    main = InspectrMain()
    main.show()
    main.setFilePath(fp)

    sys.exit(app.exec_())
