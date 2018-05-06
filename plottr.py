import sys
from PyQt5.QtWidgets import QApplication
from plottr.plottr import PlottrMain

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main = PlottrMain()
    main.show()
    sys.exit(app.exec_())
