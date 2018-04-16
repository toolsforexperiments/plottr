import sys
import time
from collections import OrderedDict

import numpy as np
import pandas as pd
import xarray as xr
import zmq
from matplotlib import rcParams
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FCanvas
from matplotlib.figure import Figure
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout,
                             QMainWindow, QPlainTextEdit, QSizePolicy,
                             QTreeWidget, QTreeWidgetItem, QVBoxLayout)

APPTITLE = "plottr"
PORT = 5557
TIMEFMT = "[%Y/%m/%d %H:%M:%S]"


def getTimestamp(timeTuple=None):
    if not timeTuple:
        timeTuple = time.localtime()
    return time.strftime(TIMEFMT, timeTuple)


def getAppTitle():
    return f"{APPTITLE}"


def setMplDefaults():
    rcParams['axes.grid'] = True
    rcParams['font.family'] = 'Arial'
    rcParams['font.size'] = 8
    rcParams['lines.markersize'] = 4
    rcParams['lines.linestyle'] = '-'
    rcParams['savefig.transparent'] = False


def dictToDataFrames(dataDict):
    dfs = []
    for n in dataDict:
        if 'axes' not in dataDict[n]:
            continue
        vals = dataDict[n]['values']
        coords = [ (a, dataDict[a]['values']) for a in dataDict[n]['axes']]

        mi = pd.MultiIndex.from_tuples(list(zip(*[v for n, v in coords])), names=dataDict[n]['axes'])
        df = pd.DataFrame(vals, mi)
        df.columns.name = n

        dfs.append(df)

    return dfs


def combineDataFrames(df1, df2, sortIndex=True):
    df = df1.append(df2)
    if sortIndex:
        df = df.sort_index()
    return df


def dataFrameToXArray(df):
    arr = xr.DataArray(df).unstack('dim_0').squeeze()
    return arr


class MPLPlot(FCanvas):

    def __init__(self, parent=None, width=4, height=3, dpi=150):
        fig = Figure(figsize=(width, height), dpi=dpi)

        # TODO: option for multiple subplots
        self.axes = fig.add_subplot(111)

        super().__init__(fig)

        self.setParent(parent)


class DataStructure(QTreeWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setColumnCount(2)
        self.setHeaderLabels(['Array', 'Properties'])


class DataWindow(QMainWindow):

    def __init__(self, dataId=None, parent=None):
        super().__init__(parent)

        self.dataId = dataId
        self.setWindowTitle(getAppTitle() + f" ({dataId})")
        self.data = {}

        # TODO: somewhere here we should implement a choice of backend i feel.
        # plot settings
        setMplDefaults()

        # data chosing widgets
        self.structure = DataStructure()
        chooserLayout = QVBoxLayout()
        chooserLayout.addWidget(self.structure)

        # plot control widgets
        self.plot = MPLPlot()
        plotLayout = QVBoxLayout()
        plotLayout.addWidget(self.plot)

        # Main layout
        self.frame = QFrame()
        mainLayout = QHBoxLayout(self.frame)
        mainLayout.addLayout(chooserLayout)
        mainLayout.addLayout(plotLayout)

        # signals/slots for data selection etc.
        self.structure.itemSelectionChanged.connect(self.dataSelected)

        # activate window
        self.frame.setFocus()
        self.setCentralWidget(self.frame)
        self.activateWindow()

    @pyqtSlot()
    def dataSelected(self):
        sel = self.structure.selectedItems()
        if len(sel) == 1:
            self.activateData(sel[0].text(0))

        elif len(sel) == 0:
            self.plot.axes.clear()
            self.plot.draw()


    def activateData(self, name):
        df = self.data[name]
        xarr = dataFrameToXArray(df)
        vals = xarr.values

        axname = [ n for n, k in self.dataStructure[name]['axes'].items() ][0]
        xvals = xarr.coords[axname].values

        self.plot.axes.plot(xvals, vals, 'o')
        self.plot.axes.set_xlabel(axname)
        self.plot.axes.set_ylabel(name)
        self.plot.draw()

    def updateDataStructure(self, reset=True):
        # TODO: keep in mind what we had selected before.
        # TODO: reset option
        self.structure.clear()
        for n, v in self.dataStructure.items():
            item = QTreeWidgetItem([n, '{} points'.format(v['nValues'])])
            for m, w in v['axes'].items():
                childItem = QTreeWidgetItem([m, '{} points'.format(w['nValues'])])
                childItem.setDisabled(True)
                item.addChild(childItem)

            self.structure.addTopLevelItem(item)
            item.setExpanded(True)

    @pyqtSlot(dict)
    def addData(self, dataDict):
        doUpdate = dataDict.get('update', False)
        dataDict = dataDict.get('datasets', None)

        if dataDict:
            newDataFrames = dictToDataFrames(dataDict)
            if not doUpdate:
                self.dataStructure = {}
                for df in newDataFrames:
                    n = df.columns.name

                    self.dataStructure[n] = {}
                    self.dataStructure[n]['nValues'] = df.size
                    self.dataStructure[n]['axes'] = OrderedDict({})
                    for m, lvls in zip(df.index.names, df.index.levels):
                        self.dataStructure[n]['axes'][m] = {}
                        self.dataStructure[n]['axes'][m]['nValues'] = len(lvls)

                    self.data[n] = df
                    self.updateDataStructure(reset=True)
            else:
                raise NotImplementedError






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
                dataId = data['id']

            except KeyError:
                self.sendInfo.emit('Received invalid data (no ID)')
                continue

            # TODO: we probably should do some basic checking of the received data here.
            self.sendInfo.emit(f'Received data for dataset: {dataId}')
            self.sendData.emit(data)


class Logger(QPlainTextEdit):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)

    @pyqtSlot(str)
    def addMessage(self, msg):
        newMsg = "{} {}".format(getTimestamp(), msg)
        self.appendPlainText(newMsg)


class PlottrMain(QMainWindow):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(getAppTitle())
        self.setWindowIcon(QIcon('./plottr_icon.png'))
        self.activateWindow()

        # layout of basic widgets
        self.logger = Logger()
        self.frame = QFrame()
        layout = QVBoxLayout(self.frame)
        layout.addWidget(self.logger)

        # self.setLayout(layout)
        self.setCentralWidget(self.frame)
        self.frame.setFocus()

        # basic setup of the data handling
        self.dataHandlers = {}

        # setting up the Listening thread
        self.listeningThread = QThread()
        self.listener = DataReceiver()
        self.listener.moveToThread(self.listeningThread)

        # communication with the ZMQ thread
        self.listeningThread.started.connect(self.listener.loop)
        self.listener.sendInfo.connect(self.logger.addMessage)
        self.listener.sendData.connect(self.processData)

        # go!
        self.listeningThread.start()

    @pyqtSlot(dict)
    def processData(self, data):
        dataId = data['id']
        if dataId not in self.dataHandlers:
            self.dataHandlers[dataId] = DataWindow(dataId=dataId)
            self.dataHandlers[dataId].show()
            self.logger.addMessage(f'Started new data window for {dataId}')

        w = self.dataHandlers[dataId]
        w.addData(data)


    def closeEvent(self, event):
        self.listener.running = False
        self.listeningThread.quit()
        # self.listeningThread.wait()

        for d in self.dataHandlers:
            self.dataHandlers[d].close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main = PlottrMain()
    main.show()
    sys.exit(app.exec_())
