import sys
from PyQt5.QtWidgets import QApplication, QDialog, QWidget

from plottr.gui.ui_lineplot import Ui_LinePlot


class LinePlot(QWidget):

    def __init__(self, parent):
        super().__init__(parent)
        ui = Ui_LinePlot()
        ui.setupUi(self)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = QDialog()
    plot = LinePlot(window)
    window.show()
    sys.exit(app.exec_())