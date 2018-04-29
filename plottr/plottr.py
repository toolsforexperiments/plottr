"""
plottr. A simple server application that can plot data streamed through
network sockets from other processes.

Author: Wolfgang Pfaff <wolfgangpfff@gmail.com>

This is the main part that contains the server application.

FIXME:
    * Performance issue: if we send data too fast, the whole thing will crash.
      We need a way to make sure data still makes it there, and that
      the sender thread stays happy

TODO:
    * launcher .bat or so.
    * better checking if we can work with data that came in.
    * some tools for packaging the data correctly.
    * a qcodes subscriber.
    * check what happens when data includes NaN.
    * the data adding should probably live in a separate thread.
      need to make sure that things get pipelined properly.
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

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.slider)

        self.slider.valueChanged.connect(self.idxSet)

    def setAxis(self, name, vals):
        self.axisVals = vals
        self.axisName = name
        self.slider.setMinimum(0)
        self.slider.setMaximum(vals.size-1)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(1)
        self.slider.setValue(0)
        self.slider.valueChanged.emit(0)

    @pyqtSlot(int)
    def idxSet(self, idx):
        if self.axisVals is not None:
            lbl = "{} : {}/{} ({})".format(self.axisName,
                idx+1, self.axisVals.size, self.axisVals[idx])
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
        self.idxChoiceLayout = QVBoxLayout()
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

        # remove old sliders / add sliders for all dimensions
        for i, slider in enumerate(self.idxChoiceSliders):
            self.idxChoiceLayout.removeWidget(slider)
            slider.deleteLater()
        self.idxChoiceSliders = []

        for n in self.axesNames:
            slider = AxisSlider()
            self.idxChoiceLayout.addWidget(slider)
            self.idxChoiceSliders.append(slider)
            slider.slider.valueChanged.connect(self.idxSliderUpdated)

        # Need an option that indicates that the choice is 'empty'
        self.noSelName = '<None>'
        while self.noSelName in self.axesNames:
            self.noSelName = '<' + self.noSelName + '>'
        self.axesNames.insert(0, self.noSelName)

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

        self.choiceUpdated.emit()


class DataAdder(QObject):

    dataUpdated = pyqtSignal(object, dict)

    def __init__(self, curData, newDataDict, update=True):
        super().__init__()

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

    def updateData(self):
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

    plotDataProcessed = pyqtSignal()
    windowClosed = pyqtSignal(str)

    def __init__(self, dataId, parent=None):
        super().__init__(parent)

        self.dataId = dataId
        self.setWindowTitle(getAppTitle() + f" ({dataId})")
        self.data = {}
        self.df = None
        self.xarr = None

        self.currentlyAddingData = False
        self.addingQueue = {}

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

        # data processing threads


        # signals/slots for data selection etc.
        # self.structure.itemSelectionChanged.connect(self.dataSelected)
        # self.plotChoice.choiceUpdated.connect(self.updatePlotData)
        # self.plotDataProcessed.connect(self.updatePlot)

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

    def activateData(self, name, resetOptions=True):
        print('activateData called...')

        if resetOptions:
            self.df = None
            self.plotChoice.setOptions(self.dataStructure[name])
        else:
            sel = self.structure.selectedItems()
            name = sel[0].text(0)

        self.activeDataSet = name
        self.df = self.data[name]
        self.xarr = dataFrameToXArray(self.df)
        self.axesNames = self.plotChoice.axesNames
        for i, n in enumerate(self.axesNames[1:]):
            self.plotChoice.idxChoiceSliders[i].setAxis(n, self.xarr.coords[n].values)

        self.updatePlotData()

    @pyqtSlot()
    def updatePlotData(self):
        self.processData(self.plotChoice.choiceInfo)

    def processData(self, info):
        print('processData called...')

        self.axesInfo = info

        if self.df is None:
            self.plot.clearFig()
            return

        data = self.xarr.values[info['slices']]
        shp = list(data.shape)

        squeezeExclude = [ info['avgAxis']['idx'],
                           info['xAxis']['idx'],
                           info['yAxis']['idx'], ]
        squeezeDims = tuple([ i for i in range(len(shp)) if ((i not in squeezeExclude) and (shp[i] == 1)) ])
        newMeanIdx = info['avgAxis']['idx'] - len([i for i in squeezeDims if i < info['avgAxis']['idx']])

        self.plotData = data.squeeze(squeezeDims)

        if info['avgAxis']['idx'] > -1:
            self.plotData = self.plotData.mean(newMeanIdx)

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
        if self.axesInfo['xAxis']['idx'] < self.axesInfo['yAxis']['idx']:
            im = self.plot.axes.pcolormesh(x, y, self.plotData.T)
        else:
            im = self.plot.axes.pcolormesh(x, y, self.plotData)
        cb = self.plot.fig.colorbar(im)
        self.plot.axes.set_xlabel(self.axesInfo['xAxis']['name'])
        self.plot.axes.set_ylabel(self.axesInfo['yAxis']['name'])

    @pyqtSlot()
    def updatePlot(self):
        self.plot.clearFig()

        if self.xVals is None and self.yVals is None:
            self.plot.draw()
            return
        elif self.xVals is not None and self.yVals is None:
            self._plot1D()
        elif self.yVals.size < 2:
            self._plot1D()
        elif self.xVals is not None and self.yVals is not None and self.xVals.size > 1:
            self._plot2D()

        self.plot.axes.set_title("{} [{}]".format(self.dataId, self.activeDataSet), size='x-small')
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
            for n, v in self.dataStructure.items():
                item = self.structure.findItems(n, Qt.MatchExactly)[0]
                item.setText(1, '{} points'.format(v['nValues']))
                for m, w in v['axes'].items():
                    for k in range(item.childCount()):
                        if item.child(k).text(0) == m:
                            item.child(k).setText(1, '{} points'.format(w['nValues']))

                self.activateData(None, resetOptions=False)


    def _getDataShape(self, name):
        shape = []
        s = self.dataStructure[name]
        for n in self.axesNames[1:]:
            shape.append(s['axes'][n]['nValues'])
        return tuple(shape)

    def addData(self, dataDict):
        doUpdate = dataDict.get('update', False) and self.data != {}
        dataDict = dataDict.get('datasets', {})

        if self.currentlyAddingData:
            if self.addingQueue == {}:
                self.addingQueue = dataDict
            else:
                self.addingQueue = combineDicts(self.addingQueue, dataDict)
        else:
            if self.addingQueue != {}:
                dataDict = combineDicts(self.addingQueue, dataDict)

            if dataDict != {}:
                self.currentlyAddingData = True

                self.dataAdder = DataAdder(self.data, dataDict, update=doUpdate)
                self.dataAdderThread = QThread()
                self.dataAdder.moveToThread(self.dataAdderThread)

                self.dataAdder.dataUpdated.connect(self.dataFromAdder)
                self.dataAdder.dataUpdated.connect(self.dataAdderThread.quit)
                self.dataAdder.dataUpdated.connect(self.dataAdder.deleteLater)
                self.dataAdderThread.started.connect(self.dataAdder.updateData)
                self.dataAdderThread.finished.connect(self.dataAdderThread.deleteLater)
                self.dataAdderThread.start()

                self.addingQueue = {}

    @pyqtSlot(object, dict)
    def dataFromAdder(self, data, dataStructure):
        self.data = data
        self.dataStructure = dataStructure
        self.currentlyAddingData = False

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
        # self.listeningThread.wait()

        hs = [h for d, h in self.dataHandlers.items()]
        for h in hs:
            h.close()

    @pyqtSlot(str)
    def dataWindowClosed(self, dataId):
        self.dataHandlers[dataId].close()
        del self.dataHandlers[dataId]


if __name__ == "__main__":
    from config import config

    app = QApplication(sys.argv)
    main = PlottrMain()
    main.show()
    sys.exit(app.exec_())
