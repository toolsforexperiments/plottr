"""
inspectr.py

Inspectr app for browsing qcodes data.
"""

import os
import time

from pyqtgraph.Qt import QtGui, QtCore

from .. import log as plottrlog
from ..data.qcodes_dataset import (get_runs_from_db_as_dataframe,
                                   get_ds_structure, load_dataset_from)
from plottr.gui.widgets import MonitorIntervalInput, FormLayoutWrapper, dictToTreeWidgetItems

from .autoplot import autoplotQcodesDataset


__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


def logger():
    logger = plottrlog.getLogger('plottr.apps.inspectr')
    return logger


### Database inspector tool

class DateList(QtGui.QListWidget):

    datesSelected = QtCore.pyqtSignal(list)
    fileDropped = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setAcceptDrops(True)
        self.setDefaultDropAction(QtCore.Qt.CopyAction)

        self.setSelectionMode(QtGui.QListView.ExtendedSelection)
        self.itemSelectionChanged.connect(self.sendSelectedDates)

    @QtCore.pyqtSlot(list)
    def updateDates(self, dates):
        for d in dates:
            if len(self.findItems(d, QtCore.Qt.MatchExactly)) == 0:
                self.insertItem(0, d)

        i = 0
        while i < self.count():
            if self.item(i).text() not in dates:
                item = self.takeItem(i)
                del item
            else:
                i += 1

            if i >= self.count():
                break

        self.sortItems(QtCore.Qt.DescendingOrder)

    @QtCore.pyqtSlot()
    def sendSelectedDates(self):
        selection = [item.text() for item in self.selectedItems()]
        self.datesSelected.emit(selection)

    ### Drag/drop handling
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1:
                url = urls[0]
                if url.isLocalFile():
                    event.accept()
            else:
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event):
        url = event.mimeData().urls()[0].toLocalFile()
        self.fileDropped.emit(url)

    def mimeTypes(self):
        return ([
            'text/uri-list',
            'application/x-qabstractitemmodeldatalist',
    ])


class SortableTreeWidgetItem(QtGui.QTreeWidgetItem):
    """
    QTreeWidgetItem with an overridden comparator that sorts numerical values
    as numbers instead of sorting them alphabetically.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

    def __lt__(self, other):
        col = self.treeWidget().sortColumn()
        text1 = self.text(col)
        text2 = other.text(col)
        try:
            return float(text1) < float(text2)
        except ValueError:
            return text1 < text2


class RunList(QtGui.QTreeWidget):

    cols = ['Run ID', 'Experiment', 'Sample', 'Name', 'Started', 'Completed', 'Records']

    runSelected = QtCore.pyqtSignal(int)
    runActivated = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setColumnCount(len(self.cols))
        self.setHeaderLabels(self.cols)

        self.itemSelectionChanged.connect(self.selectRun)
        self.itemActivated.connect(self.activateRun)

    def addRun(self, runId, **vals):
        lst = [str(runId)]
        lst.append(vals.get('experiment', ''))
        lst.append(vals.get('sample', ''))
        lst.append(vals.get('name', ''))
        lst.append(vals.get('started date', '') + ' ' + vals.get('started time', ''))
        lst.append(vals.get('completed date', '') + ' ' + vals.get('completed time', ''))
        lst.append(str(vals.get('records', '')))

        item = SortableTreeWidgetItem(lst)
        self.addTopLevelItem(item)

    def setRuns(self, selection):
        self.clear()

        # disable sorting before inserting values to avoid performance hit
        self.setSortingEnabled(False)

        for runId, record in selection.items():
            self.addRun(runId, **record)

        self.setSortingEnabled(True)

        for i in range(len(self.cols)):
            self.resizeColumnToContents(i)

    @QtCore.pyqtSlot()
    def selectRun(self):
        selection = self.selectedItems()
        if len(selection) == 0:
            return

        runId = int(selection[0].text(0))
        self.runSelected.emit(runId)

    @QtCore.pyqtSlot(QtGui.QTreeWidgetItem, int)
    def activateRun(self, item, column):
        runId = int(item.text(0))
        self.runActivated.emit(runId)


class RunInfo(QtGui.QTreeWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setHeaderLabels(['Key', 'Value'])
        self.setColumnCount(2)

    @QtCore.pyqtSlot(dict)
    def setInfo(self, infoDict):
        self.clear()

        items = dictToTreeWidgetItems(infoDict)
        for item in items:
            self.addTopLevelItem(item)
            item.setExpanded(True)

        self.expandAll()
        for i in range(2):
            self.resizeColumnToContents(i)


class LoadDBProcess(QtCore.QObject):
    """
    Worker object for getting a qcodes db overview as pandas dataframe.
    It's good to have this in a separate thread because it can be a bit slow
    for large databases.
    """
    dbdfLoaded = QtCore.pyqtSignal(object)
    pathSet = QtCore.pyqtSignal()

    def setPath(self, path: str):
        self.path = path
        self.pathSet.emit()

    def loadDB(self):
        dbdf = get_runs_from_db_as_dataframe(self.path)
        self.dbdfLoaded.emit(dbdf)

class QCodesDBInspector(QtGui.QMainWindow):
    """
    Main window of the inspectr tool.
    """

    dbdfUpdated = QtCore.pyqtSignal()
    sendInfo = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None, dbPath=None):
        super().__init__(parent)

        self._plotWindows = {}

        self.filepath = dbPath
        self.dbdf = None
        self.monitor = QtCore.QTimer()
        
        # flag for determining what has been loaded so far.
        # * None: nothing opened yet.
        # * -1: empty DS open.
        # * any value > 0: run ID from the most recent loading.
        self.latestRunId = None

        self.setWindowTitle('Plottr | QCoDeS dataset inspectr')

        ### GUI elements

        # Main Selection widgets
        self.dateList = DateList()
        self.runList = RunList()
        self.runInfo = RunInfo()

        rightSplitter = QtGui.QSplitter(QtCore.Qt.Vertical)
        rightSplitter.addWidget(self.runList)
        rightSplitter.addWidget(self.runInfo)
        rightSplitter.setSizes([400, 200])

        splitter = QtGui.QSplitter()
        splitter.addWidget(self.dateList)
        splitter.addWidget(rightSplitter)
        splitter.setSizes([100, 500])

        self.setCentralWidget(splitter)

        # status bar
        self.status = QtGui.QStatusBar()
        self.setStatusBar(self.status)

        # toolbar
        self.toolbar = self.addToolBar('Data monitoring')

        # toolbar item: monitor interval
        self.monitorInput = MonitorIntervalInput()
        self.monitorInput.setToolTip('Set to 0 for disabling')
        self.monitorInput.intervalChanged.connect(self.setMonitorInterval)
        self.toolbar.addWidget(self.monitorInput)

        self.toolbar.addSeparator()

        # toolbar item: auto-launch plotting
        self.autoLaunchPlots = FormLayoutWrapper([
            ('Auto-plot new', QtGui.QCheckBox())
        ])
        tt = "If checked, and automatic refresh is running, "
        tt += " launch plotting window for new datasets automatically."
        self.autoLaunchPlots.setToolTip(tt)
        self.toolbar.addWidget(self.autoLaunchPlots)

        # menu bar
        menu = self.menuBar()
        fileMenu = menu.addMenu('&File')

        # action: load db file
        loadAction = QtGui.QAction('&Load', self)
        loadAction.setShortcut('Ctrl+L')
        loadAction.triggered.connect(self.loadDB)
        fileMenu.addAction(loadAction)

        # action: updates from the db file
        refreshAction = QtGui.QAction('&Refresh', self)
        refreshAction.setShortcut('R')
        refreshAction.triggered.connect(self.refreshDB)
        fileMenu.addAction(refreshAction)

        # sizing
        self.resize(640, 640)

        ### Thread workers
        
        # DB loading
        self.loadDBProcess = LoadDBProcess()
        self.loadDBThread = QtCore.QThread()
        self.loadDBProcess.moveToThread(self.loadDBThread)
        self.loadDBProcess.pathSet.connect(self.loadDBThread.start)
        self.loadDBProcess.dbdfLoaded.connect(self.DBLoaded)
        self.loadDBProcess.dbdfLoaded.connect(self.loadDBThread.quit)
        self.loadDBThread.started.connect(self.loadDBProcess.loadDB)

        ### connect signals/slots

        self.dbdfUpdated.connect(self.updateDates)
        self.dbdfUpdated.connect(self.showDBPath)

        self.dateList.datesSelected.connect(self.setDateSelection)
        self.dateList.fileDropped.connect(self.loadFullDB)
        self.runList.runSelected.connect(self.setRunSelection)
        self.runList.runActivated.connect(self.plotRun)
        self.sendInfo.connect(self.runInfo.setInfo)
        self.monitor.timeout.connect(self.monitorTriggered)

        if self.filepath is not None:
            self.loadFullDB(self.filepath)

    def closeEvent(self, event):
        """
        When closing the inspectr window, do some house keeping:
        * stop the monitor, if running
        * close all plot windows
        """

        if self.monitor.isActive():
            self.monitor.stop()

        for runId, info in self._plotWindows.items():
            info['window'].close()

    @QtCore.pyqtSlot()
    def showDBPath(self):
        tstamp = time.strftime("%Y-%m-%d %H:%M:%S")
        path = os.path.abspath(self.filepath)
        self.status.showMessage(f"{path} (loaded: {tstamp})")

    ### loading the DB and populating the widgets
    @QtCore.pyqtSlot()
    def loadDB(self):
        """
        Open a file dialog that allows selecting a .db file for loading.
        If a file is selected, opens the db.
        """
        if self.filepath is not None:
            curdir = os.path.split(self.filepath)[0]
        else:
            curdir = os.getcwd()

        path, _fltr = QtGui.QFileDialog.getOpenFileName(
            self,
            'Open qcodes .db file',
            curdir,
            'qcodes .db files (*.db);;all files (*.*)',
            )

        if path:
            logger().info(f"Opening: {path}")
            self.loadFullDB(path=path)

    def loadFullDB(self, path=None):
        if path is not None and path != self.filepath:
            self.filepath = path

        if self.filepath is not None:
            if not self.loadDBThread.isRunning():
                self.loadDBProcess.setPath(self.filepath)

    
    def DBLoaded(self, dbdf):
        self.dbdf = dbdf
        self.dbdfUpdated.emit()
        self.dateList.sendSelectedDates()
        logger().debug('DB reloaded')

        if self.latestRunId is not None:
            idxs = self.dbdf.index.values
            newIdxs = idxs[idxs > self.latestRunId]
            
            if self.monitor.isActive() and self.autoLaunchPlots.elements['Auto-plot new'].isChecked():
                for idx in newIdxs:
                    self.plotRun(idx)
                    self._plotWindows[idx]['window'].setMonitorInterval(2)



    @QtCore.pyqtSlot()
    def updateDates(self):
        if self.dbdf.size > 0:
            dates = list(self.dbdf.groupby('started date').indices.keys())
            self.dateList.updateDates(dates)

    ### reloading the db
    @QtCore.pyqtSlot()
    def refreshDB(self):
        if self.filepath is not None:
            if self.dbdf.size > 0:
                self.latestRunId = self.dbdf.index.values.max()
            else:
                self.latestRunId = -1

            self.loadFullDB()

    @QtCore.pyqtSlot(int)
    def setMonitorInterval(self, val):
        self.monitor.stop()
        if val > 0:
            self.monitor.start(val * 1000)

        self.monitorInput.spin.setValue(val)

    @QtCore.pyqtSlot()
    def monitorTriggered(self):
        logger().debug('Refreshing DB')
        self.refreshDB()

    ### handling user selections
    @QtCore.pyqtSlot(list)
    def setDateSelection(self, dates):
        if len(dates) > 0:
            selection = self.dbdf.loc[self.dbdf['started date'].isin(dates)].sort_index(ascending=False)
            self.runList.setRuns(selection.to_dict(orient='index'))
        else:
            self.runList.clear()

    @QtCore.pyqtSlot(int)
    def setRunSelection(self, runId):
        ds = load_dataset_from(self.filepath, runId)
        structure = get_ds_structure(ds)
        for k, v in structure.items():
            v.pop('values')
        contentInfo = {'data' : structure}
        self.sendInfo.emit(contentInfo)

    @QtCore.pyqtSlot(int)
    def plotRun(self, runId):
        fc, win = autoplotQcodesDataset(pathAndId=(self.filepath, runId))
        self._plotWindows[runId] = {
            'flowchart' : fc,
            'window' : win,
        }
        win.showTime()


def inspectr(dbPath: str = None):
    win = QCodesDBInspector(dbPath=dbPath)
    return win
