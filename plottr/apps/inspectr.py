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
import logging
from typing import Optional, Sequence, List, Dict, Iterable, Union, cast, Tuple
from typing_extensions import TypedDict

from numpy import rint
import pandas

from plottr import QtCore, QtWidgets, Signal, Slot, QtGui, Flowchart

from .. import log as plottrlog
from ..data.qcodes_dataset import (get_runs_from_db_as_dataframe,
                                   get_ds_structure, load_dataset_from)
from plottr.gui.widgets import MonitorIntervalInput, FormLayoutWrapper, dictToTreeWidgetItems

from .autoplot import autoplotQcodesDataset, QCAutoPlotMainWindow


__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


def logger() -> logging.Logger:
    logger = plottrlog.getLogger('plottr.apps.inspectr')
    return logger


### Database inspector tool

class DateList(QtWidgets.QListWidget):
    """Displays a list of dates for which there are runs in the database."""

    datesSelected = Signal(list)
    fileDropped = Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        self.setAcceptDrops(True)
        self.setDefaultDropAction(QtCore.Qt.CopyAction)

        self.setSelectionMode(QtWidgets.QListView.ExtendedSelection)
        self.itemSelectionChanged.connect(self.sendSelectedDates)

    @Slot(list)
    def updateDates(self, dates: Sequence[str]) -> None:
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
    def sendSelectedDates(self) -> None:
        selection = [item.text() for item in self.selectedItems()]
        self.datesSelected.emit(selection)

    ### Drag/drop handling
    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
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

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        url = event.mimeData().urls()[0].toLocalFile()
        self.fileDropped.emit(url)

    def mimeTypes(self) -> List[str]:
        return ([
            'text/uri-list',
            'application/x-qabstractitemmodeldatalist',
    ])


class SortableTreeWidgetItem(QtWidgets.QTreeWidgetItem):
    """
    QTreeWidgetItem with an overridden comparator that sorts numerical values
    as numbers instead of sorting them alphabetically.
    """
    def __init__(self, strings: Iterable[str]):
        super().__init__(strings)

    def __lt__(self, other: "SortableTreeWidgetItem") -> bool:
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

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        self.setColumnCount(len(self.cols))
        self.setHeaderLabels(self.cols)

        self.itemSelectionChanged.connect(self.selectRun)
        self.itemActivated.connect(self.activateRun)

    def addRun(self, runId: int, **vals: str) -> None:
        lst = [str(runId)]
        lst.append(vals.get('experiment', ''))
        lst.append(vals.get('sample', ''))
        lst.append(vals.get('name', ''))
        lst.append(vals.get('started_date', '') + ' ' + vals.get('started_time', ''))
        lst.append(vals.get('completed_date', '') + ' ' + vals.get('completed_time', ''))
        lst.append(str(vals.get('records', '')))
        lst.append(vals.get('guid', ''))

        item = SortableTreeWidgetItem(lst)
        self.addTopLevelItem(item)

    def setRuns(self, selection: Dict[int, Dict[str, str]]) -> None:
        self.clear()

        # disable sorting before inserting values to avoid performance hit
        self.setSortingEnabled(False)

        for runId, record in selection.items():
            self.addRun(runId, **record)

        self.setSortingEnabled(True)

        for i in range(len(self.cols)):
            self.resizeColumnToContents(i)

    def updateRuns(self, selection: Dict[int, Dict[str, str]]) -> None:

        run_added = False
        for runId, record in selection.items():
            item = self.findItems(str(runId), QtCore.Qt.MatchExactly)
            if len(item) == 0:
                self.setSortingEnabled(False)
                self.addRun(runId, **record)
                run_added = True
            elif len(item) == 1:
                completed = record.get('completed_date', '') + ' ' + record.get(
                    'completed_time', '')
                if completed != item[0].text(5):
                    item[0].setText(5, completed)

                num_records = str(record.get('records', ''))
                if num_records != item[0].text(6):
                    item[0].setText(6, num_records)
            else:
                raise RuntimeError(f"More than one runs found with runId: "
                                   f"{runId}")

        if run_added:
            self.setSortingEnabled(True)
            for i in range(len(self.cols)):
                self.resizeColumnToContents(i)

    @Slot()
    def selectRun(self) -> None:
        selection = self.selectedItems()
        if len(selection) == 0:
            return

        runId = int(selection[0].text(0))
        self.runSelected.emit(runId)

    @Slot(QtWidgets.QTreeWidgetItem, int)
    def activateRun(self, item: QtWidgets.QTreeWidgetItem, column: int) -> None:
        runId = int(item.text(0))
        self.runActivated.emit(runId)


class RunInfo(QtWidgets.QTreeWidget):
    """widget that shows some more details on a selected run.

    When sending information in form of a dictionary, it will create
    a tree view of that dictionary and display that.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        self.setHeaderLabels(['Key', 'Value'])
        self.setColumnCount(2)

    @Slot(dict)
    def setInfo(self, infoDict: Dict[str, Union[dict, str]]) -> None:
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

    def setPath(self, path: str) -> None:
        self.path = path
        self.pathSet.emit()

    def loadDB(self) -> None:
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

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None,
                 dbPath: Optional[str] = None):
        """Constructor for :class:`QCodesDBInspector`."""
        super().__init__(parent)

        self._plotWindows: Dict[int, WindowDict] = {}

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
        self._selected_dates: Tuple[str, ...] = ()
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
        scaledSize = 640 * rint(self.logicalDpiX() / 96.0)
        self.resize(scaledSize, scaledSize)

        ### Thread workers

        # DB loading. can be slow, so nice to have in a thread.
        self.loadDBProcess = LoadDBProcess()
        self.loadDBThread = QtCore.QThread()
        self.loadDBProcess.moveToThread(self.loadDBThread)
        self.loadDBProcess.pathSet.connect(self.loadDBThread.start)
        self.loadDBProcess.dbdfLoaded.connect(self.DBLoaded)
        self.loadDBProcess.dbdfLoaded.connect(self.loadDBThread.quit)
        self.loadDBThread.started.connect(self.loadDBProcess.loadDB)  # type: ignore[attr-defined]

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

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
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
    def showDBPath(self) -> None:
        tstamp = time.strftime("%Y-%m-%d %H:%M:%S")
        assert self.filepath is not None
        path = os.path.abspath(self.filepath)
        self.status.showMessage(f"{path} (loaded: {tstamp})")

    ### loading the DB and populating the widgets
    @Slot()
    def loadDB(self) -> None:
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

    def loadFullDB(self, path: Optional[str] = None) -> None:
        if path is not None and path != self.filepath:
            self.filepath = path

            # makes sure we treat a newly loaded file fresh and not as a
            # refreshed one.
            self.latestRunId = None

        if self.filepath is not None:
            if not self.loadDBThread.isRunning():
                self.loadDBProcess.setPath(self.filepath)

    def DBLoaded(self, dbdf: pandas.DataFrame) -> None:
        if dbdf.equals(self.dbdf):
            logger().debug('DB reloaded with no changes. Skipping update')
            return None
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
                    self._plotWindows[idx]['window'].setMonitorInterval(
                        self.monitorInput.spin.value()
                    )

    @Slot()
    def updateDates(self) -> None:
        assert self.dbdf is not None
        if self.dbdf.size > 0:
            dates = list(self.dbdf.groupby('started_date').indices.keys())
            self.dateList.updateDates(dates)

    ### reloading the db
    @Slot()
    def refreshDB(self) -> None:
        if self.filepath is not None:
            if self.dbdf is not None and self.dbdf.size > 0:
                self.latestRunId = self.dbdf.index.values.max()
            else:
                self.latestRunId = -1

            self.loadFullDB()

    @Slot(float)
    def setMonitorInterval(self, val: float) -> None:
        self.monitor.stop()
        if val > 0:
            self.monitor.start(int(val * 1000))

        self.monitorInput.spin.setValue(val)

    @Slot()
    def monitorTriggered(self) -> None:
        logger().debug('Refreshing DB')
        self.refreshDB()

    ### handling user selections
    @Slot(list)
    def setDateSelection(self, dates: Sequence[str]) -> None:
        if len(dates) > 0:
            assert self.dbdf is not None
            selection = self.dbdf.loc[self.dbdf['started_date'].isin(dates)].sort_index(ascending=False)
            old_dates = self._selected_dates
            if not all(date in old_dates for date in dates):
                self.runList.setRuns(selection.to_dict(orient='index'))
            else:
                self.runList.updateRuns(selection.to_dict(orient='index'))
            self._selected_dates = tuple(dates)
        else:
            self._selected_dates = ()
            self.runList.clear()

    @Slot(int)
    def setRunSelection(self, runId: int) -> None:
        assert self.filepath is not None
        ds = load_dataset_from(self.filepath, runId)
        snap = None
        if hasattr(ds, 'snapshot'):
            snap = ds.snapshot

        structure = cast(Dict[str, dict], get_ds_structure(ds))
        # cast away typed dict so we can pop a key
        for k, v in structure.items():
            v.pop('values')
        contentInfo = {'Data structure': structure,
                       'QCoDeS Snapshot': snap}
        self._sendInfo.emit(contentInfo)

    @Slot(int)
    def plotRun(self, runId: int) -> None:
        assert self.filepath is not None
        fc, win = autoplotQcodesDataset(pathAndId=(self.filepath, runId))
        self._plotWindows[runId] = {
            'flowchart': fc,
            'window': win,
        }
        win.showTime()


class WindowDict(TypedDict):
    flowchart: Flowchart
    window: QCAutoPlotMainWindow


def inspectr(dbPath: Optional[str] = None) -> QCodesDBInspector:
    win = QCodesDBInspector(dbPath=dbPath)
    return win


def main(dbPath: Optional[str]) -> None:
    app = QtWidgets.QApplication([])
    plottrlog.enableStreamHandler(True)

    win = inspectr(dbPath=dbPath)
    win.show()

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtWidgets.QApplication.instance().exec_()


def script() -> None:
    parser = argparse.ArgumentParser(description='inspectr -- sifting through qcodes data.')
    parser.add_argument('--dbpath', help='path to qcodes .db file',
                        default=None)
    args = parser.parse_args()
    main(args.dbpath)
