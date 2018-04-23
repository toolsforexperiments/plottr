"""
plottr. A simple server application that can plot data streamed through
network sockets from other processes.

Author: Wolfgang Pfaff <wolfgangpfff@gmail.com>

TODO: (before releasing into the wild)
    * all constants should become configurable
    * launcher .bat or so.
    * examples
    * better checking if we can work with data that came in.
    * some tools for packaging the data correctly.
    * a qcodes subscriber.
    * docstrings everywhere public.
    * make some methods private?
"""

import sys
import time
from collections import OrderedDict

import numpy as np
import pandas as pd
import xarray as xr
import zmq
from matplotlib import rcParams
from matplotlib.backends.backend_qt5agg import (FigureCanvasQTAgg as FCanvas,
                                                NavigationToolbar2QT as NavBar, )
from matplotlib.figure import Figure
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (QApplication, QComboBox, QDialog, QFormLayout,
                             QFrame, QGroupBox, QHBoxLayout, QLabel,
                             QMainWindow, QPlainTextEdit, QSizePolicy,
                             QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                             QWidget, QSlider)

APPTITLE = "plottr"
AVGAXISNAMES = ['average', 'averages', 'repetition', 'repetitions']
PORT = 5557
TIMEFMT = "[%Y/%m/%d %H:%M:%S]"


def getTimestamp(timeTuple=None):
    if not timeTuple:
        timeTuple = time.localtime()
    return time.strftime(TIMEFMT, timeTuple)


def getAppTitle():
    return f"{APPTITLE}"

### matplotlib tools
def setMplDefaults():
    rcParams['axes.grid'] = True
    rcParams['font.family'] = 'Arial'
    rcParams['font.size'] = 8
    rcParams['lines.markersize'] = 4
    rcParams['lines.linestyle'] = '-'
    rcParams['savefig.transparent'] = False


def centers2edges(arr):
    e = (arr[1:] + arr[:-1]) / 2.
    e = np.concatenate(([arr[0] - (e[0] - arr[0])], e))
    e = np.concatenate((e, [arr[-1] + (arr[-1] - e[-1])]))
    return e


def pcolorgrid(xaxis, yaxis):
    xedges = centers2edges(xaxis)
    yedges = centers2edges(yaxis)
    xx, yy = np.meshgrid(xedges, yedges)
    return xx, yy


### structure tools
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
    """
    Convert pandas DataFrame with MultiIndex to an xarray DataArray.
    """
    # conversion with MultiIndex leaves some residue; need to unstack the MI dimension.
    arr = xr.DataArray(df).unstack('dim_0').squeeze()

    # for tidiness, remove also any empty dimensions.
    for k, v in arr.coords.items():
        if not isinstance(v.values, np.ndarray) or v.values.size <= 1:
            arr = arr.drop(k)
    return arr


class MPLPlot(FCanvas):

    def __init__(self, parent=None, width=4, height=3, dpi=150):
        self.fig = Figure(figsize=(width, height), dpi=dpi)

        # TODO: option for multiple subplots
        self.axes = self.fig.add_subplot(111)

        super().__init__(self.fig)
        self.setParent(parent)

    def clearFig(self):
        self.fig.clear()
        self.axes = self.fig.add_subplot(111)
        self.draw()


class DataStructure(QTreeWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setColumnCount(2)
        self.setHeaderLabels(['Array', 'Properties'])
        self.setSelectionMode(QTreeWidget.SingleSelection)


class AxisSlider(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.axisVals = None

        self.slider = QSlider(Qt.Horizontal)
        self.label = QLabel()

        self.layout = QHBoxLayout()
        self.setLayout(self.layout)
        self.layout.addWidget(self.slider)
        self.layout.addWidget(self.label)

        self.slider.valueChanged.connect(self.idxSet)

    def setAxis(self, vals):
        self.axisVals = vals
        self.slider.setMinimum(0)
        self.slider.setMaximum(vals.size-1)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(1)
        self.slider.setValue(0)
        self.slider.valueChanged.emit(0)

    @pyqtSlot(int)
    def idxSet(self, idx):
        if self.axisVals is not None:
            lbl = "{}/{} ({})".format(idx+1, self.axisVals.size, self.axisVals[idx])
            self.label.setText(lbl)


class PlotChoice(QWidget):

    choiceUpdated = pyqtSignal()

    def __init__(self, parent=None):

        super().__init__(parent)

        self.avgSelection = QComboBox()
        self.xSelection = QComboBox()
        self.ySelection = QComboBox()

        axisChoiceBox = QGroupBox('Plot axes')
        axisChoiceLayout = QFormLayout()
        axisChoiceLayout.addRow(QLabel('Averaging axis'), self.avgSelection)
        axisChoiceLayout.addRow(QLabel('x axis'), self.xSelection)
        axisChoiceLayout.addRow(QLabel('y axis'), self.ySelection)
        axisChoiceBox.setLayout(axisChoiceLayout)

        self.idxChoiceBox = QGroupBox('Indices')
        self.idxChoiceLayout = QFormLayout()
        self.idxChoiceBox.setLayout(self.idxChoiceLayout)
        self.idxChoiceSliders = []

        mainLayout = QVBoxLayout(self)
        mainLayout.addWidget(axisChoiceBox)
        mainLayout.addWidget(self.idxChoiceBox)

        self.avgSelection.currentTextChanged.connect(self.avgSelected)
        self.xSelection.currentTextChanged.connect(self.xSelected)
        self.ySelection.currentTextChanged.connect(self.ySelected)

    @pyqtSlot(str)
    def avgSelected(self, val):
        self.updateOptions(self.avgSelection, val)

    @pyqtSlot(str)
    def xSelected(self, val):
        self.updateOptions(self.xSelection, val)

    @pyqtSlot(str)
    def ySelected(self, val):
        self.updateOptions(self.ySelection, val)

    # TODO: this is not nice. split up a bit.
    @pyqtSlot(int)
    def idxSliderUpdated(self, val):
        self.updateOptions(None, None)

    def _isAxisInUse(self, name):
        for opt in self.avgSelection, self.xSelection, self.ySelection:
            if name == opt.currentText():
                return True
        return False

    def updateOptions(self, changedOption, newVal):
        """
        After changing the role of a data axis manually, we need to make
        sure this axis isn't used anywhere else.
        """
        for opt in self.avgSelection, self.xSelection, self.ySelection:
            if opt != changedOption and opt.currentText() == newVal:
                opt.setCurrentIndex(0)

        for i, n in enumerate(self.axesNames[1:]):
            if self._isAxisInUse(n):
                self.idxChoiceSliders[i].setDisabled(True)
            else:
                self.idxChoiceSliders[i].setEnabled(True)

        slices = [ slice(None, None, None) for n in self.axesNames[1:] ]
        for i, idxChoice in enumerate(self.idxChoiceSliders):
            if idxChoice.isEnabled():
                v = idxChoice.slider.value()
                slices[i] = slice(v, v+1, None)

        self.choiceInfo = {
            'avgAxis' : {
                'idx' : self.avgSelection.currentIndex() - 1,
                'name' : self.avgSelection.currentText(),
            },
            'xAxis' : {
                'idx' : self.xSelection.currentIndex() - 1,
                'name' : self.xSelection.currentText(),
            },
            'yAxis' : {
                'idx' : self.ySelection.currentIndex() - 1,
                'name' : self.ySelection.currentText(),
            },
            'slices' : slices,
        }

        self.choiceUpdated.emit()

    def setOptions(self, dataStructure):
        """
        Populates the data choice widgets initially.
        """
        self.axesNames = [ n for n, k in dataStructure['axes'].items() ]

        # FIXME: delete old sliders!!!
        # add sliders for all dimensions
        for n in self.axesNames:
            slider = AxisSlider()
            self.idxChoiceLayout.addRow(f'{n}', slider)
            self.idxChoiceSliders.append(slider)
            slider.slider.valueChanged.connect(self.idxSliderUpdated)

        # Need an option that indicates that the choice is 'empty'
        self.noSelName = '<None>'
        while self.noSelName in self.axesNames:
            self.noSelName = '<' + self.noSelName + '>'
        self.axesNames.insert(0, self.noSelName)

        # check if some axis is obviously meant for averaging
        self.avgAxisName = None
        for n in self.axesNames:
            if n.lower() in AVGAXISNAMES:
                self.avgAxisName = n

        # add all options
        for opt in self.avgSelection, self.xSelection, self.ySelection:
            opt.clear()
            opt.addItems(self.axesNames)

        # select averaging axis automatically
        if self.avgAxisName:
            self.avgSelection.setCurrentText(self.avgAxisName)
        else:
            self.avgSelection.setCurrentIndex(0)

        # see which options remain for x and y, apply the first that work
        xopts = self.axesNames.copy()
        xopts.pop(0)
        if self.avgAxisName:
            xopts.pop(xopts.index(self.avgAxisName))

        if len(xopts) > 0:
            self.xSelection.setCurrentText(xopts[0])
        if len(xopts) > 1:
            self.ySelection.setCurrentText(xopts[1])

        self.choiceUpdated.emit()


class DataWindow(QMainWindow):

    plotDataProcessed = pyqtSignal()

    def __init__(self, dataId=None, parent=None):
        super().__init__(parent)

        self.dataId = dataId
        self.setWindowTitle(getAppTitle() + f" ({dataId})")
        self.data = {}
        self.df = None
        self.xarr = None

        # TODO: somewhere here we should implement a choice of backend i feel.
        # plot settings
        setMplDefaults()

        # data chosing widgets
        self.structure = DataStructure()
        self.plotChoice = PlotChoice()
        chooserLayout = QVBoxLayout()
        chooserLayout.addWidget(self.structure)
        chooserLayout.addWidget(self.plotChoice)

        # plot control widgets
        self.plot = MPLPlot()
        plotLayout = QVBoxLayout()
        plotLayout.addWidget(self.plot)
        plotLayout.addWidget(NavBar(self.plot, self))

        # Main layout
        self.frame = QFrame()
        mainLayout = QHBoxLayout(self.frame)
        mainLayout.addLayout(chooserLayout)
        mainLayout.addLayout(plotLayout)

        # signals/slots for data selection etc.
        self.structure.itemSelectionChanged.connect(self.dataSelected)
        self.plotChoice.choiceUpdated.connect(self.updatePlotData)
        self.plotDataProcessed.connect(self.updatePlot)

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
            self.plot.clearFig()

    def activateData(self, name):
        self.df = None
        self.plotChoice.setOptions(self.dataStructure[name])
        self.df = self.data[name]
        self.xarr = dataFrameToXArray(self.df)
        self.axesNames = self.plotChoice.axesNames
        for i, n in enumerate(self.axesNames[1:]):
            self.plotChoice.idxChoiceSliders[i].setAxis(self.xarr.coords[n].values)

        self.updatePlotData()

    @pyqtSlot()
    def updatePlotData(self):
        self.processData(self.plotChoice.choiceInfo)

    def processData(self, info):
        self.axesInfo = info

        if self.df is None:
            self.plot.clearFig()
            return

        self.plotData = self.xarr.values[info['slices']]
        if info['avgAxis']['idx'] > -1:
            self.plotData = self.plotData.mean(info['avgAxis']['idx'])
        self.plotData = np.squeeze(self.plotData)

        if info['xAxis']['idx'] > -1:
            self.xVals = self.xarr.coords[info['xAxis']['name']].values
        else:
            self.xVals = None

        if info['yAxis']['idx'] > -1:
            self.yVals = self.xarr.coords[info['yAxis']['name']].values
        else:
            self.yVals = None

        self.plotDataProcessed.emit()

    def _plot1D(self):
        self.plot.axes.plot(self.xVals, self.plotData, 'o')
        self.plot.axes.set_xlabel(self.axesInfo['xAxis']['name'])

    def _plot2D(self):
        x, y = pcolorgrid(self.xVals, self.yVals)
        im = self.plot.axes.pcolormesh(x, y, self.plotData.T)
        cb = self.plot.fig.colorbar(im)
        self.plot.axes.set_xlabel(self.axesInfo['xAxis']['name'])
        self.plot.axes.set_ylabel(self.axesInfo['yAxis']['name'])

    @pyqtSlot()
    def updatePlot(self):
        self.plot.clearFig()

        if self.xVals is not None and self.yVals is None:
            self._plot1D()
        elif self.xVals is not None and self.yVals is not None:
            self._plot2D()

        self.plot.fig.tight_layout()
        self.plot.draw()

    def updateDataStructure(self, reset=True):
        curSelection = self.structure.selectedItems()
        if len(curSelection) > 0:
            selName = curSelection[0].text(0)
        else:
            selName = None

        if reset:
            self.structure.clear()
            for n, v in self.dataStructure.items():
                item = QTreeWidgetItem([n, '{} points'.format(v['nValues'])])
                for m, w in v['axes'].items():
                    childItem = QTreeWidgetItem([m, '{} points'.format(w['nValues'])])
                    childItem.setDisabled(True)
                    item.addChild(childItem)

                self.structure.addTopLevelItem(item)
                item.setExpanded(True)
                if selName and n == selName:
                    item.setSelected(True)

            if not selName:
                self.structure.topLevelItem(0).setSelected(True)

        else:
            raise NotImplementedError

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
