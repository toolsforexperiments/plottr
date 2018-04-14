import sys
import time
import zmq
import numpy as np

from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout,
    QPlainTextEdit, QFrame)
from PyQt5.QtCore import (QObject, pyqtSignal, pyqtSlot, QThread)
from PyQt5.QtGui import (QIcon, )

from matplotlib import pyplot as plt


APPTITLE = "plottr"
PORT = 5557
TIMEFMT = "[%Y/%m/%d %H:%M:%S]"


def get_timestamp(time_tuple=None):
    if not time_tuple:
        time_tuple = time.localtime()
    return time.strftime(TIMEFMT, time_tuple)

def get_app_title():
    return f"{APPTITLE}"



class DataWindow(QMainWindow):

    def __init__(self, parent=None):
        super().__init__(self, parent)

    @pyqtSlot(dict)
    def setData(self, dataDict):
        pass


class DataReceiver(QObject):

    sendInfo = pyqtSignal(str)
    sendData = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

        context = zmq.Context()
        port = PORT
        self.socket = context.socket(zmq.PULL)
        self.socket.bind(f"tcp://127.0.0.1:{port}")
        self.running = True

    @pyqtSlot()
    def loop(self):
        self.sendInfo.emit("Listening...")

        while self.running:
            data = self.socket.recv_json()
            try:
                data_id = data['id']

            except KeyError:
                self.sendInfo.emit('Received invalid data (no id)')
                continue

            # TODO: we probably should do some basic checking of the received data here.
            self.sendInfo.emit(f'Received data for dataset: {data_id}')
            self.sendData.emit(data)




class Logger(QPlainTextEdit):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)

    @pyqtSlot(str)
    def addMessage(self, msg):
        newMsg = "{} {}".format(get_timestamp(), msg)
        self.appendPlainText(newMsg)


class PlottrMain(QMainWindow):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowIcon(QIcon('./plottr_icon.png'))

        # layout of basic widgets
        self.logger = Logger()
        self.frame = QFrame()
        layout = QVBoxLayout(self.frame)
        layout.addWidget(self.logger)

        # self.setLayout(layout)
        self.setCentralWidget(self.frame)
        self.setWindowTitle(get_app_title())

        # basic setup of the data handling
        self.dataHandlers = {}

        # setting up the Listening thread
        self.listeningThread = QThread()
        self.listener = DataReceiver()
        self.listener.moveToThread(self.listeningThread)

        # communication with the ZMQ thread
        self.listeningThread.started.connect(self.listener.loop)
        self.listener.sendInfo.connect(self.logger.addMessage)

        # go!
        self.listeningThread.start()


    def closeEvent(self, event):
        self.listener.running = False
        self.listeningThread.quit()
        # self.listeningThread.wait()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main = PlottrMain()
    main.show()
    sys.exit(app.exec_())
