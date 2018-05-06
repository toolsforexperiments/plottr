import sys
from PyQt5.QtWidgets import QApplication
from plottr.qcodes_dataset_inspectr import InspectrMain

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
