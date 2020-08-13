"""
plottr/apps/inspectr.py -- tool for browsing qcodes data.

This module provides a GUI tool to browsing qcodes .db files.
You can drap/drop .db files into the inspectr window, then browse through
datasets by date. The inspectr itself shows some elementary information
about each dataset and you can launch a plotting window that allows visualizing
the data in it.

Note that this tool is essentially only visualizing some basic structure of the
runs contained in the database. It does not to any handling or loading of
data. it relies on the public qcodes API to get its information.
"""

import os
import time
import sys
import argparse

from plottr import QtCore, QtWidgets, Signal, Slot

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

class DateList(QtWidgets.QListWidget):
    """Displays a list of dates for which there are runs in the database."""

    datesSelected = Signal(list)
    fileDropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setAcceptDrops(True)
        self.setDefaultDropAction(QtCore.Qt.CopyAction)

        self.setSelectionMode(QtWidgets.QListView.ExtendedSelection)
        self.itemSelectionChanged.connect(self.sendSelectedDates)

    @Slot(list)
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

    @Slot()
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


class SortableTreeWidgetItem(QtWidgets.QTreeWidgetItem):
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


class RunList(QtWidgets.QTreeWidget):
    """Shows the list of runs for a given date selection."""

    cols = ['Run ID', 'Experiment', 'Sample', 'Name', 'Started', 'Completed', 'Records', 'GUID']

    runSelected = Signal(int)
    runActivated = Signal(int)

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
        lst.append(vals.get('guid', ''))

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

    @Slot()
    def selectRun(self):
        selection = self.selectedItems()
        if len(selection) == 0:
            return

        runId = int(selection[0].text(0))
        self.runSelected.emit(runId)

    @Slot(QtWidgets.QTreeWidgetItem, int)
    def activateRun(self, item, column):
        runId = int(item.text(0))
        self.runActivated.emit(runId)


class RunInfo(QtWidgets.QTreeWidget):
    """widget that shows some more details on a selected run.

    When sending information in form of a dictionary, it will create
    a tree view of that dictionary and display that.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setHeaderLabels(['Key', 'Value'])
        self.setColumnCount(2)

    @Slot(dict)
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
    dbdfLoaded = Signal(object)
    pathSet = Signal()

    def setPath(self, path: str):
        self.path = path
        self.pathSet.emit()

    def loadDB(self):
        dbdf = get_runs_from_db_as_dataframe(self.path)
        self.dbdfLoaded.emit(dbdf)


class QCodesDBInspector(QtWidgets.QMainWindow):
    """
    Main window of the inspectr tool.
    """

    #: `Signal ()` -- Emitted when when there's an update to the internally
    #: cached data (the *data base data frame* :)).
    dbdfUpdated = Signal()

    #: Signal (`dict`) -- emitted to communicate information about a given
    #: run to the widget that displays the information
    _sendInfo = Signal(dict)

    def __init__(self, parent=None, dbPath=None):
        """Constructor for :class:`QCodesDBInspector`."""
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

        rightSplitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        rightSplitter.addWidget(self.runList)
        rightSplitter.addWidget(self.runInfo)
        rightSplitter.setSizes([400, 200])

        splitter = QtWidgets.QSplitter()
        splitter.addWidget(self.dateList)
        splitter.addWidget(rightSplitter)
        splitter.setSizes([100, 500])

        self.setCentralWidget(splitter)

        # status bar
        self.status = QtWidgets.QStatusBar()
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
            ('Auto-plot new', QtWidgets.QCheckBox())
        ])
        tt = "If checked, and automatic refresh is running, "
        tt += " launch plotting window for new datasets automatically."
        self.autoLaunchPlots.setToolTip(tt)
        self.toolbar.addWidget(self.autoLaunchPlots)

        # menu bar
        menu = self.menuBar()
        fileMenu = menu.addMenu('&File')

        # action: load db file
        loadAction = QtWidgets.QAction('&Load', self)
        loadAction.setShortcut('Ctrl+L')
        loadAction.triggered.connect(self.loadDB)
        fileMenu.addAction(loadAction)

        # action: updates from the db file
        refreshAction = QtWidgets.QAction('&Refresh', self)
        refreshAction.setShortcut('R')
        refreshAction.triggered.connect(self.refreshDB)
        fileMenu.addAction(refreshAction)

        # sizing
        self.resize(640, 640)

        ### Thread workers
        
        # DB loading. can be slow, so nice to have in a thread.
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
        self._sendInfo.connect(self.runInfo.setInfo)
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

    @Slot()
    def showDBPath(self):
        tstamp = time.strftime("%Y-%m-%d %H:%M:%S")
        path = os.path.abspath(self.filepath)
        self.status.showMessage(f"{path} (loaded: {tstamp})")

    ### loading the DB and populating the widgets
    @Slot()
    def loadDB(self):
        """
        Open a file dialog that allows selecting a .db file for loading.
        If a file is selected, opens the db.
        """
        if self.filepath is not None:
            curdir = os.path.split(self.filepath)[0]
        else:
            curdir = os.getcwd()

        path, _fltr = QtWidgets.QFileDialog.getOpenFileName(
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

            # makes sure we treat a newly loaded file fresh and not as a
            # refreshed one.
            self.latestRunId = None

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



    @Slot()
    def updateDates(self):
        if self.dbdf.size > 0:
            dates = list(self.dbdf.groupby('started date').indices.keys())
            self.dateList.updateDates(dates)

    ### reloading the db
    @Slot()
    def refreshDB(self):
        if self.filepath is not None:
            if self.dbdf is not None and self.dbdf.size > 0:
                self.latestRunId = self.dbdf.index.values.max()
            else:
                self.latestRunId = -1

            self.loadFullDB()

    @Slot(int)
    def setMonitorInterval(self, val):
        self.monitor.stop()
        if val > 0:
            self.monitor.start(val * 1000)

        self.monitorInput.spin.setValue(val)

    @Slot()
    def monitorTriggered(self):
        logger().debug('Refreshing DB')
        self.refreshDB()

    ### handling user selections
    @Slot(list)
    def setDateSelection(self, dates):
        if len(dates) > 0:
            selection = self.dbdf.loc[self.dbdf['started date'].isin(dates)].sort_index(ascending=False)
            self.runList.setRuns(selection.to_dict(orient='index'))
        else:
            self.runList.clear()

    @Slot(int)
    def setRunSelection(self, runId):
        ds = load_dataset_from(self.filepath, runId)
        snap = None
        if hasattr(ds, 'snapshot'):
            snap = ds.snapshot

        structure = get_ds_structure(ds)
        for k, v in structure.items():
            v.pop('values')
        contentInfo = {'Data structure': structure,
                       'QCoDeS Snapshot': snap}
        self._sendInfo.emit(contentInfo)

    @Slot(int)
    def plotRun(self, runId):
        fc, win = autoplotQcodesDataset(pathAndId=(self.filepath, runId))
        self._plotWindows[runId] = {
            'flowchart': fc,
            'window': win,
        }
        win.showTime()


def inspectr(dbPath: str = None):
    win = QCodesDBInspector(dbPath=dbPath)
    return win


def main(dbPath):
    app = QtWidgets.QApplication([])
    plottrlog.enableStreamHandler(True)

    win = inspectr(dbPath=dbPath)
    win.show()

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtWidgets.QApplication.instance().exec_()


def script():
    parser = argparse.ArgumentParser(description='inspectr -- sifting through qcodes data.')
    parser.add_argument('--dbpath', help='path to qcodes .db file',
                        default=None)
    args = parser.parse_args()
    main(args.dbpath)
