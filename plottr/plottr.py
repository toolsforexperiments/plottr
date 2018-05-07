"""
plottr. A simple server application that can plot data streamed through
network sockets from other processes.

Author: Wolfgang Pfaff <wolfgangpfff@gmail.com>

This is the main part that contains the server application.

TODO:
    * launcher .bat or so.
    * better checking if we can work with data that came in.
    * check what happens when data includes NaN.
"""

import sys
import time
from collections import OrderedDict

import numpy as np
import pandas as pd
import xarray as xr
import zmq
from matplotlib import rcParams
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavBar
from matplotlib.figure import Figure
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (QApplication, QComboBox, QDialog, QFormLayout,
                             QFrame, QGroupBox, QHBoxLayout, QLabel,
                             QMainWindow, QPlainTextEdit, QSizePolicy, QSlider,
                             QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                             QWidget)

from .config import config

APPTITLE = "plottr"
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
def combineDicts(dict1, dict2):
    if dict1 != {}:
        for k in dict1.keys():
            dict1[k]['values'] += dict2[k]['values']
        return dict1
    else:
        return dict2


def dictToDataFrames(dataDict):
    dfs = []
    for n in dataDict:
        if 'axes' not in dataDict[n]:
            continue
        vals = dataDict[n]['values']

        coord_vals = []
        coord_names = []
        for a in dataDict[n]['axes']:
            coord_vals.append(dataDict[a]['values'])
            m = a
            unit = dataDict[m].get('unit', '')
            if unit != '':
                m += f" ({unit})"
            coord_names.append(m)

        coords = list(zip(coord_names, coord_vals))

        mi = pd.MultiIndex.from_tuples(list(zip(*[v for n, v in coords])), names=coord_names)
        df = pd.DataFrame(vals, mi)

        name = n
        unit = dataDict[n].get('unit', '')
        if unit != '':
            name += f" ({unit})"
        df.columns.name = name

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
    arr = xr.DataArray(df)

    # remove automatically generated indices.
    for idxn in arr.indexes:
        idx = arr.indexes[idxn]
        if 'dim_' in idxn or idxn == df.columns.name:
            if isinstance(idx, pd.MultiIndex):
                arr = arr.unstack(idxn)
            else:
                arr = arr.squeeze(idxn).drop(idxn)

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

    dataUpdated = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setColumnCount(2)
        self.setHeaderLabels(['Array', 'Properties'])
        self.setSelectionMode(QTreeWidget.SingleSelection)

    def getSelected(self):
        curSelection = self.selectedItems()
        if len(curSelection) == 0:
            return None
        else:
            return curSelection[0].text(0)

    @pyqtSlot(dict)
    def update(self, structure):
        for n, v in structure.items():
            items = self.findItems(n, Qt.MatchExactly)
            if len(items) == 0:
                item = QTreeWidgetItem([n, '{} points'.format(v['nValues'])])
                for m, w in v['axes'].items():
                    childItem = QTreeWidgetItem([m, '{} points'.format(w['nValues'])])
                    childItem.setDisabled(True)
                    item.addChild(childItem)

                self.addTopLevelItem(item)
                item.setExpanded(True)

            else:
                item = items[0]
                item.setText(1, '{} points'.format(v['nValues']))
                for m, w in v['axes'].items():
                    for k in range(item.childCount()):
                        if item.child(k).text(0) == m:
                            item.child(k).setText(1, '{} points'.format(w['nValues']))

        curSelection = self.selectedItems()
        if len(curSelection) == 0:
            item = self.topLevelItem(0)
            if item:
                item.setSelected(True)



class AxisSlider(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.axisName = None
        self.nAxisVals = None

        self.slider = QSlider(Qt.Horizontal)
        self.label = QLabel()

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.slider)

        self.slider.valueChanged.connect(self.idxSet)

    def setAxis(self, name, nvals, reset=True):
        self.axisName = name
        self.nAxisVals = nvals
        self.slider.setMaximum(nvals-1)
        if reset:
            self.slider.setMinimum(0)
            self.slider.setSingleStep(1)
            self.slider.setPageStep(1)
            self.slider.setValue(0)
            self.slider.valueChanged.emit(0)
        else:
            self.idxSet(self.slider.value())

    @pyqtSlot(int)
    def idxSet(self, idx):
        if self.nAxisVals is not None:
            lbl = "{} : {}/{}".format(
                self.axisName, idx+1, self.nAxisVals)
            self.label.setText(lbl)


class PlotChoice(QWidget):

    choiceUpdated = pyqtSignal(object)

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
        self.idxChoiceLayout = QVBoxLayout()
        self.idxChoiceBox.setLayout(self.idxChoiceLayout)
        self.idxChoiceSliders = []

        mainLayout = QVBoxLayout(self)
        mainLayout.addWidget(axisChoiceBox)
        mainLayout.addWidget(self.idxChoiceBox)

        self.doEmitChoiceUpdate = False
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

    @pyqtSlot(dict)
    def updateData(self, dataStructure):
        for i, n in enumerate(self.axesNames[1:]):
            try:
                slider = self.idxChoiceSliders[i]
                slider.setAxis(n, dataStructure['axes'][n]['nValues'], reset=False)
            except IndexError:
                pass

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

        if self.doEmitChoiceUpdate:
            self.choiceUpdated.emit(self.choiceInfo)

    @pyqtSlot(dict)
    def setOptions(self, dataStructure):
        """
        Populates the data choice widgets initially.
        """
        self.doEmitChoiceUpdate = False
        self.axesNames = [ n for n, k in dataStructure['axes'].items() ]

        # Need an option that indicates that the choice is 'empty'
        self.noSelName = '<None>'
        while self.noSelName in self.axesNames:
            self.noSelName = '<' + self.noSelName + '>'
        self.axesNames.insert(0, self.noSelName)

        # remove old sliders / add sliders for all dimensions
        for i, slider in enumerate(self.idxChoiceSliders):
            self.idxChoiceLayout.removeWidget(slider)
            slider.deleteLater()
        self.idxChoiceSliders = []

        for n in self.axesNames[1:]:
            slider = AxisSlider()
            self.idxChoiceLayout.addWidget(slider)
            self.idxChoiceSliders.append(slider)
            slider.setAxis(n, dataStructure['axes'][n]['nValues'])
            slider.slider.valueChanged.connect(self.idxSliderUpdated)

        # check if some axis is obviously meant for averaging
        avgAxisNames = config['data']['avg_axes_names']
        self.avgAxisName = None
        for n in self.axesNames:
            if n.lower() in avgAxisNames:
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

        self.doEmitChoiceUpdate = True
        self.choiceUpdated.emit(self.choiceInfo)


class PlotData(QObject):

    dataProcessed = pyqtSignal(object, object, object)

    def setData(self, df, choiceInfo):
        self.df = df
        self.choiceInfo = choiceInfo

    def processData(self):
        try:
            xarr = dataFrameToXArray(self.df)
        except ValueError:
            print('Yikes. It appears we cannot recognize a good shape for the data :( Is it corrupted?')
            return

        data = xarr.values[self.choiceInfo['slices']]
        shp = list(data.shape)

        squeezeExclude = [ self.choiceInfo['avgAxis']['idx'],
                           self.choiceInfo['xAxis']['idx'],
                           self.choiceInfo['yAxis']['idx'], ]
        squeezeDims = tuple([ i for i in range(len(shp)) if ((i not in squeezeExclude) and (shp[i] == 1)) ])
        newMeanIdx = self.choiceInfo['avgAxis']['idx'] - \
            len([i for i in squeezeDims if i < self.choiceInfo['avgAxis']['idx']])

        plotData = data.squeeze(squeezeDims)

        if self.choiceInfo['avgAxis']['idx'] > -1:
            plotData = plotData.mean(newMeanIdx)

        if self.choiceInfo['xAxis']['idx'] > -1:
            xVals = xarr.coords[self.choiceInfo['xAxis']['name']].values
        else:
            xVals = None

        if self.choiceInfo['yAxis']['idx'] > -1:
            yVals = xarr.coords[self.choiceInfo['yAxis']['name']].values
        else:
            yVals = None

        self.dataProcessed.emit(plotData, xVals, yVals)


class DataAdder(QObject):

    dataUpdated = pyqtSignal(object, dict)

    def setData(self, curData, newDataDict, update=True):
        self.curData = curData
        self.newDataDict = newDataDict
        self.update = update

    def _getDataStructure(self, df):
        ds = {}
        ds['nValues'] = df.size
        ds['axes'] = OrderedDict({})

        for m, lvls in zip(df.index.names, df.index.levels):
            ds['axes'][m] = {}
            ds['axes'][m]['uniqueValues'] = lvls.values
            ds['axes'][m]['nValues'] = len(lvls)

        return ds

    def run(self):
        newDataFrames = dictToDataFrames(self.newDataDict)
        dataStructure = {}
        data = {}

        self.update = self.update and self.curData != {}

        for df in newDataFrames:
            n = df.columns.name

            if not self.update:
                data[n] = df
                dataStructure[n] = self._getDataStructure(df)
            elif self.update and n in self.curData:
                data[n] = combineDataFrames(self.curData[n], df)
                dataStructure[n] = self._getDataStructure(data[n])

        self.dataUpdated.emit(data, dataStructure)


class DataWindow(QMainWindow):

    dataAdded = pyqtSignal(dict)
    dataActivated = pyqtSignal(dict)
    windowClosed = pyqtSignal(str)

    def __init__(self, dataId, parent=None):
        super().__init__(parent)

        self.dataId = dataId
        self.setWindowTitle(getAppTitle() + f" ({dataId})")
        self.data = {}

        self.addingQueue = {}
        self.currentlyProcessingPlotData = False
        self.pendingPlotData = False

        # plot settings
        setMplDefaults()

        # data chosing widgets
        self.structureWidget = DataStructure()
        self.plotChoice = PlotChoice()
        chooserLayout = QVBoxLayout()
        chooserLayout.addWidget(self.structureWidget)
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

        # data processing threads
        self.dataAdder = DataAdder()
        self.dataAdderThread = QThread()
        self.dataAdder.moveToThread(self.dataAdderThread)
        self.dataAdder.dataUpdated.connect(self.dataFromAdder)
        self.dataAdder.dataUpdated.connect(self.dataAdderThread.quit)
        self.dataAdderThread.started.connect(self.dataAdder.run)

        self.plotData = PlotData()
        self.plotDataThread = QThread()
        self.plotData.moveToThread(self.plotDataThread)
        self.plotData.dataProcessed.connect(self.updatePlot)
        self.plotData.dataProcessed.connect(self.plotDataThread.quit)
        self.plotDataThread.started.connect(self.plotData.processData)

        # signals/slots for data selection etc.
        self.dataAdded.connect(self.structureWidget.update)
        self.dataAdded.connect(self.updatePlotChoices)
        self.dataAdded.connect(self.updatePlotData)

        self.structureWidget.itemSelectionChanged.connect(self.activateData)
        self.dataActivated.connect(self.plotChoice.setOptions)

        self.plotChoice.choiceUpdated.connect(self.updatePlotData)

        # activate window
        self.frame.setFocus()
        self.setCentralWidget(self.frame)
        self.activateWindow()

    @pyqtSlot()
    def activateData(self):
        item = self.structureWidget.selectedItems()[0]
        self.activeDataSet = item.text(0)
        self.dataActivated.emit(self.dataStructure[self.activeDataSet])

    def updatePlotChoices(self, dataStructure):
        n = self.structureWidget.getSelected()
        if n is not None:
            self.plotChoice.updateData(dataStructure[n])

    @pyqtSlot()
    def updatePlotData(self):
        if self.plotDataThread.isRunning():
            self.pendingPlotData = True
        else:
            self.currentPlotChoiceInfo = self.plotChoice.choiceInfo
            self.pendingPlotData = False
            self.plotData.setData(self.data[self.activeDataSet], self.currentPlotChoiceInfo)
            self.plotDataThread.start()

    def _plot1D(self, x, data):
        self.plot.axes.plot(x, data, 'o')
        self.plot.axes.set_xlabel(self.currentPlotChoiceInfo['xAxis']['name'])

    def _plot2D(self, x, y, data):
        xx, yy = pcolorgrid(x, y)
        if self.currentPlotChoiceInfo['xAxis']['idx'] < self.currentPlotChoiceInfo['yAxis']['idx']:
            im = self.plot.axes.pcolormesh(xx, yy, data.T)
        else:
            im = self.plot.axes.pcolormesh(xx, yy, data)
        cb = self.plot.fig.colorbar(im)
        self.plot.axes.set_xlabel(self.currentPlotChoiceInfo['xAxis']['name'])
        self.plot.axes.set_ylabel(self.currentPlotChoiceInfo['yAxis']['name'])

    @pyqtSlot(object, object, object)
    def updatePlot(self, data, x, y):
        self.plot.clearFig()

        if x is None and y is None:
            self.plot.draw()
        elif x is not None and y is None:
            self._plot1D(x, data)
        elif y.size < 2:
            self._plot1D(x, data)
        elif x is not None and y is not None and x.size > 1:
            self._plot2D(x, y, data)

        self.plot.axes.set_title("{} [{}]".format(self.dataId, self.activeDataSet), size='x-small')
        self.plot.fig.tight_layout()
        self.plot.draw()

        if self.pendingPlotData:
            self.updatePlotData()

    #
    # Data adding
    #
    def addData(self, dataDict):
        """
        Here we receive new data from the listener.
        We'll use a separate thread for processing and combining (numerics might be costly).
        If the thread is already running, we'll put the new data into a queue that will
        be resolved during the next call of addData (i.e, queue will grow until current
        adding thread is done.)
        """
        doUpdate = dataDict.get('update', False) and self.data != {}
        dataDict = dataDict.get('datasets', {})

        if self.dataAdderThread.isRunning():
            if self.addingQueue == {}:
                self.addingQueue = dataDict
            else:
                self.addingQueue = combineDicts(self.addingQueue, dataDict)
        else:
            if self.addingQueue != {}:
                dataDict = combineDicts(self.addingQueue, dataDict)

            if dataDict != {}:
                self.dataAdder.setData(self.data, dataDict, doUpdate)
                self.dataAdderThread.start()
                self.addingQueue = {}

    @pyqtSlot(object, dict)
    def dataFromAdder(self, data, dataStructure):
        self.data = data
        self.dataStructure = dataStructure
        self.dataAdded.emit(self.dataStructure)

    # clean-up
    def closeEvent(self, event):
        self.windowClosed.emit(self.dataId)


class DataReceiver(QObject):

    sendInfo = pyqtSignal(str)
    sendData = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

        context = zmq.Context()
        port = config['network']['port']
        addr = config['network']['addr']
        self.socket = context.socket(zmq.PULL)
        self.socket.bind(f"tcp://{addr}:{port}")
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
            self.dataHandlers[dataId].windowClosed.connect(self.dataWindowClosed)

        w = self.dataHandlers[dataId]
        w.addData(data)

    def closeEvent(self, event):
        self.listener.running = False
        self.listeningThread.quit()

        hs = [h for d, h in self.dataHandlers.items()]
        for h in hs:
            h.close()

    @pyqtSlot(str)
    def dataWindowClosed(self, dataId):
        self.dataHandlers[dataId].close()
        del self.dataHandlers[dataId]
