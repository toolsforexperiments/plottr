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
from typing import Any, Optional, Sequence, List, Dict, Iterable, Union, cast, Tuple, Mapping

from typing_extensions import TypedDict

from numpy import rint
import pandas

from plottr import QtCore, QtWidgets, Signal, Slot, QtGui, Flowchart

from .. import log as plottrlog
from ..data.qcodes_dataset import (get_runs_from_db_as_dataframe,
                                   get_runs_from_db, get_runs_from_db_fast,
                                   get_ds_structure, load_dataset_from)
from ..data.qcodes_db_overview import get_db_overview
from plottr.gui.widgets import MonitorIntervalInput, FormLayoutWrapper, dictToTreeWidgetItems

from .autoplot import autoplotQcodesDataset, QCAutoPlotMainWindow


__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'

LOGGER = plottrlog.getLogger('plottr.apps.inspectr')

#: Hint text shown in the run list when no date is selected.
_SELECT_DATE_HINT = "Select a date on the left to browse datasets."

#: Mapping of display names to plot widget classes for the backend selector.
#: Populated lazily on first access.
_PLOT_BACKENDS: Dict[str, type] = {}


def _get_plot_backends() -> Dict[str, type]:
    """Lazily populate and return the backend mapping."""
    if not _PLOT_BACKENDS:
        from plottr.plot.mpl.autoplot import AutoPlot as MPLAutoPlot
        from plottr.plot.pyqtgraph.autoplot import AutoPlot as PGAutoPlot
        _PLOT_BACKENDS['matplotlib'] = MPLAutoPlot
        _PLOT_BACKENDS['pyqtgraph'] = PGAutoPlot
    return _PLOT_BACKENDS


def _backend_name_for_class(cls: Optional[type]) -> Optional[str]:
    """Return the display name for a plot widget class, or None if unknown."""
    for name, backend_cls in _get_plot_backends().items():
        if backend_cls is cls:
            return name
    return None


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
            elem = self.item(i)
            if elem is not None and elem.text() not in dates:
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

    def __lt__(self, other: QtWidgets.QTreeWidgetItem) -> bool:
        col = self.treeWidget().sortColumn()
        text1 = self.text(col)
        text2 = other.text(col)
        try:
            return float(text1) < float(text2)
        except ValueError:
            return text1 < text2


class RunList(QtWidgets.QTreeWidget):
    """Shows the list of runs for a given date selection."""

    cols = ['Run ID', 'Tag', 'Experiment', 'Sample', 'Name', 'Started', 'Completed', 'Records', 'GUID']
    tag_dict = {'': '', 'star': '⭐', 'cross': '❌'}

    runSelected = Signal(int)
    runActivated = Signal(int)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        self.setColumnCount(len(self.cols))
        self.setHeaderLabels(self.cols)

        self.itemSelectionChanged.connect(self.selectRun)
        self.itemActivated.connect(self.activateRun)

        # Overlay label for status messages
        self._overlayLabel = QtWidgets.QLabel(self.viewport())
        self._overlayLabel.setAlignment(QtCore.Qt.AlignCenter)
        self._overlayLabel.setWordWrap(True)
        self._overlayLabel.setStyleSheet(
            "color: gray; font-size: 13pt; padding: 40px;"
        )
        self._overlayLabel.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.setOverlayText(_SELECT_DATE_HINT)

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)

    def setOverlayText(self, text: str) -> None:
        """Show a centered overlay message. Pass empty string to hide."""
        self._overlayLabel.setText(text)
        self._overlayLabel.setVisible(bool(text))

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._overlayLabel.setGeometry(self.viewport().rect())

    @Slot(QtCore.QPoint)
    def showContextMenu(self, position: QtCore.QPoint) -> None:
        model_index = self.indexAt(position)
        item = self.itemFromIndex(model_index)
        assert item is not None
        current_tag_char = item.text(1)

        menu = QtWidgets.QMenu()

        copy_icon = self.style().standardIcon(QtWidgets.QStyle.SP_DialogSaveButton)
        copy_action = menu.addAction(copy_icon, "Copy")

        window = cast(QCodesDBInspector, self.window())
        starAction: QtWidgets.QAction = window.starAction


        starAction.setText('Star' if current_tag_char != self.tag_dict['star'] else 'Unstar')
        menu.addAction(starAction)

        crossAction: QtWidgets.QAction = window.crossAction
        crossAction.setText(
            "Cross" if current_tag_char != self.tag_dict["cross"] else "Uncross"
        )

        menu.addAction(crossAction)

        action = menu.exec_(self.mapToGlobal(position))
        if action == copy_action:
            QtWidgets.QApplication.clipboard().setText(item.text(
                model_index.column()))

    def addRun(self, runId: int, **vals: str) -> None:
        lst = [str(runId)]
        tag = vals.get('inspectr_tag', '')
        lst.append(self.tag_dict.get(tag, tag))  # if the tag is not in tag_dict, display in text
        lst.append(vals.get('experiment', ''))
        lst.append(vals.get('sample', ''))
        lst.append(vals.get('name', ''))
        lst.append(vals.get('started_date', '') + ' ' + vals.get('started_time', ''))
        lst.append(vals.get('completed_date', '') + ' ' + vals.get('completed_time', ''))
        lst.append(str(vals.get('records', '')))
        lst.append(vals.get('guid', ''))

        item = SortableTreeWidgetItem(lst)
        self.addTopLevelItem(item)

    def setRuns(self, selection: Mapping[int, Mapping[str, str]], show_only_star: bool, show_also_cross: bool) -> None:
        self.clear()
        self.setOverlayText('')

        # disable sorting before inserting values to avoid performance hit
        self.setSortingEnabled(False)

        count = 0
        for runId, record in selection.items():
            tag = record.get('inspectr_tag', '')
            if show_only_star and tag == '':
                continue
            elif show_also_cross or tag != 'cross':
                self.addRun(runId, **record)
                count += 1

        self.setSortingEnabled(True)

        for i in range(len(self.cols)):
            self.resizeColumnToContents(i)

        if count == 0:
            self.setOverlayText("No datasets match the current filter.")

    def updateRuns(self, selection: Mapping[int, Mapping[str, str]]) -> None:

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
                if completed != item[0].text(6):
                    item[0].setText(6, completed)

                num_records = str(record.get('records', ''))
                if num_records != item[0].text(7):
                    item[0].setText(7, num_records)
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

    Snapshot data is loaded lazily: a placeholder item is shown, and the full
    snapshot tree is built only when the user expands it.
    """

    #: Signal emitted when the snapshot section needs to be loaded.
    #: Argument is the QTreeWidgetItem to populate.
    _snapshotRequested = Signal(object)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        self.setHeaderLabels(['Key', 'Value'])
        self.setColumnCount(2)

        # Smooth pixel-based scrolling so tall rows (e.g., long tracebacks)
        # can be scrolled through without jumping to the next row.
        self.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)

        self._snapshotItem: Optional[QtWidgets.QTreeWidgetItem] = None
        self._snapshotData: Optional[dict] = None
        self._snapshotLoaded = False

        self.itemExpanded.connect(self._onItemExpanded)

    @Slot(dict)
    def setInfo(self, infoDict: Dict[str, Union[dict, str]]) -> None:
        self.clear()
        self._snapshotItem = None
        self._snapshotData = None
        self._snapshotLoaded = False

        for key, value in infoDict.items():
            if key == 'QCoDeS Snapshot':
                # Create a placeholder for the snapshot — don't build the tree yet
                self._snapshotItem = QtWidgets.QTreeWidgetItem([key, '(click to expand)'])
                # Add a dummy child so the expand arrow appears
                self._snapshotItem.addChild(QtWidgets.QTreeWidgetItem(['(loading...)', '']))
                self._snapshotData = value if isinstance(value, dict) else None
                self.addTopLevelItem(self._snapshotItem)
                self._snapshotItem.setExpanded(False)
            else:
                if not isinstance(value, dict):
                    item = QtWidgets.QTreeWidgetItem([str(key), str(value)])
                else:
                    item = QtWidgets.QTreeWidgetItem([key, ''])
                    for child in dictToTreeWidgetItems(value):
                        item.addChild(child)
                self.addTopLevelItem(item)
                item.setExpanded(False)

        for i in range(2):
            self.resizeColumnToContents(i)

    @Slot(QtWidgets.QTreeWidgetItem)
    def _onItemExpanded(self, item: QtWidgets.QTreeWidgetItem) -> None:
        if item is self._snapshotItem and not self._snapshotLoaded:
            self._loadSnapshot()

    def _loadSnapshot(self) -> None:
        """Replace the placeholder with the actual snapshot tree."""
        if self._snapshotItem is None:
            return

        self._snapshotLoaded = True
        snap_data = self._snapshotData

        # Remove placeholder children
        self._snapshotItem.takeChildren()

        if snap_data is None:
            self._snapshotItem.setText(1, '(no snapshot)')
            return

        self._snapshotItem.setText(1, '')

        if isinstance(snap_data, dict):
            for child in dictToTreeWidgetItems(snap_data):
                self._snapshotItem.addChild(child)
        else:
            self._snapshotItem.addChild(
                QtWidgets.QTreeWidgetItem([str(snap_data), '']))

        for i in range(2):
            self.resizeColumnToContents(i)


class LoadDBProcess(QtCore.QObject):
    """
    Worker object for getting a qcodes db overview as pandas dataframe.
    It's good to have this in a separate thread because it can be a bit slow
    for large databases.

    Uses ``get_db_overview`` (direct SQL) by default for maximum speed.
    Falls back to ``get_runs_from_db_fast`` (qcodes public API) if the
    SQL approach fails.
    """
    dbdfLoaded = Signal(object)
    progressUpdated = Signal(int, int)  # (current, total)
    pathSet = Signal()

    #: If True, use direct SQL queries (fast). If False, use qcodes API.
    use_fast_sql: bool = True

    def __init__(self) -> None:
        super().__init__()
        self.path: Optional[str] = None
        self.start_run_id: int = 1

    def setPath(self, path: str, start_run_id: int = 1) -> None:
        self.path = path
        self.start_run_id = start_run_id
        self.pathSet.emit()

    def loadDB(self) -> None:
        assert self.path is not None

        overview: Optional[Dict[int, Any]] = None
        if self.use_fast_sql:
            try:
                # start_run_id uses > comparison, so subtract 1 for inclusive
                overview = get_db_overview(
                    self.path,
                    start_run_id=self.start_run_id - 1,
                )
            except Exception as e:
                LOGGER.warning(f"Fast SQL overview failed, falling back to "
                               f"qcodes API: {e}")
                overview = None

        if overview is None:
            overview = get_runs_from_db_fast(
                self.path,
                start_run_id=self.start_run_id,
                progress_callback=self._onProgress,
            )

        if overview:
            dbdf = pandas.DataFrame.from_dict(overview, orient='index')
        else:
            dbdf = pandas.DataFrame()
        self.dbdfLoaded.emit(dbdf)

    def _onProgress(self, current: int, total: int) -> None:
        self.progressUpdated.emit(current, total)


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
                 dbPath: Optional[str] = None,
                 plotWidgetClass: Optional[type] = None):
        """Constructor for :class:`QCodesDBInspector`."""
        super().__init__(parent)

        self._plotWindows: Dict[int, WindowDict] = {}
        self._plotWidgetClass = plotWidgetClass

        self.filepath = dbPath
        self.dbdf: Optional[pandas.DataFrame] = None
        self.monitor = QtCore.QTimer()

        # flag for determining what has been loaded so far.
        # * None: nothing opened yet.
        # * -1: empty DS open.
        # * any value > 0: run ID from the most recent loading.
        self.latestRunId: Optional[int] = None

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

        self.toolbar.addSeparator()

        # toolbar item: plot backend selector
        backendLabel = QtWidgets.QLabel(" Plot backend: ")
        self.toolbar.addWidget(backendLabel)
        self.plotBackendSelector = QtWidgets.QComboBox()
        backends = _get_plot_backends()
        self.plotBackendSelector.addItems(list(backends.keys()))
        self.plotBackendSelector.setToolTip('Choose plotting backend for new plot windows')
        if plotWidgetClass is not None:
            known_name = _backend_name_for_class(plotWidgetClass)
            if known_name is not None:
                self.plotBackendSelector.setCurrentText(known_name)
            else:
                # Unknown class: add it to the selector with its class name
                label = plotWidgetClass.__name__
                self.plotBackendSelector.addItem(label)
                self.plotBackendSelector.setCurrentText(label)
        self.plotBackendSelector.currentTextChanged.connect(self._onBackendChanged)
        self.toolbar.addWidget(self.plotBackendSelector)
        # Sync the class with the initial combo selection
        self._onBackendChanged(self.plotBackendSelector.currentText())

        self.toolbar.addSeparator()

        self.showOnlyStarAction = self.toolbar.addAction(RunList.tag_dict['star'])
        self.showOnlyStarAction.setToolTip('Show only starred runs')
        self.showOnlyStarAction.setCheckable(True)
        self.showOnlyStarAction.triggered.connect(self.updateRunList)
        self.showAlsoCrossAction = self.toolbar.addAction(RunList.tag_dict['cross'])
        self.showAlsoCrossAction.setToolTip('Show also crossed runs')
        self.showAlsoCrossAction.setCheckable(True)
        self.showAlsoCrossAction.triggered.connect(self.updateRunList)

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

        # action: star/unstar the selected run
        self.starAction = QtWidgets.QAction()
        self.starAction.setShortcut('Ctrl+Alt+S')
        self.starAction.triggered.connect(self.starSelectedRun)
        self.addAction(self.starAction)

        # action: cross/uncross the selected run
        self.crossAction = QtWidgets.QAction()
        self.crossAction.setShortcut('Ctrl+Alt+X')
        self.crossAction.triggered.connect(self.crossSelectedRun)
        self.addAction(self.crossAction)

        # sizing
        scaledDpi = rint(self.logicalDpiX() / 96.0)
        self.resize(int(960 * scaledDpi), int(640 * scaledDpi))

        ### Thread workers

        # DB loading. can be slow, so nice to have in a thread.
        self.loadDBProcess = LoadDBProcess()
        self.loadDBThread = QtCore.QThread()
        self.loadDBProcess.moveToThread(self.loadDBThread)
        self.loadDBProcess.pathSet.connect(self.loadDBThread.start)
        self.loadDBProcess.dbdfLoaded.connect(self.DBLoaded)
        self.loadDBProcess.dbdfLoaded.connect(self.loadDBThread.quit)
        self.loadDBProcess.progressUpdated.connect(self.onLoadProgress)
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
            LOGGER.info(f"Opening: {path}")
            self.loadFullDB(path=path)

    def loadFullDB(self, path: Optional[str] = None) -> None:
        if path is not None and path != self.filepath:
            self.filepath = path

            # makes sure we treat a newly loaded file fresh and not as a
            # refreshed one.
            self.latestRunId = None

        if self.filepath is not None:
            if not self.loadDBThread.isRunning():
                self.runList.setOverlayText("Loading database...")
                self.loadDBProcess.setPath(self.filepath, start_run_id=1)

    @Slot(int, int)
    def onLoadProgress(self, current: int, total: int) -> None:
        self.runList.setOverlayText(
            f"Loading database... ({current}/{total} datasets)")

    def DBLoaded(self, dbdf: pandas.DataFrame) -> None:
        if dbdf.size == 0 and self.dbdf is not None:
            LOGGER.debug('DB reloaded with no new data. Skipping update.')
            self.runList.setOverlayText(
                _SELECT_DATE_HINT)
            return None

        if self.latestRunId is not None and self.dbdf is not None and dbdf.size > 0:
            # Incremental load: merge new rows into existing dataframe
            existing_mask = dbdf.index.isin(self.dbdf.index)
            # Update existing rows (e.g., completed_date may have changed)
            if existing_mask.any():
                self.dbdf.update(dbdf.loc[existing_mask])
            # Append all truly-new rows in a single concat
            new_rows = dbdf.loc[~existing_mask]
            if not new_rows.empty:
                self.dbdf = pandas.concat([self.dbdf, new_rows])
        elif dbdf.size > 0:
            self.dbdf = dbdf
        else:
            self.dbdf = dbdf

        self.dbdfUpdated.emit()
        self.dateList.sendSelectedDates()
        LOGGER.debug('DB loaded/refreshed')

        # Set appropriate overlay text after loading completes
        if self.dbdf is None or self.dbdf.size == 0:
            self.runList.setOverlayText(
                "No datasets found in this database.")
        elif self.runList.topLevelItemCount() == 0:
            self.runList.setOverlayText(
                _SELECT_DATE_HINT)

        if self.latestRunId is not None and self.dbdf is not None and self.dbdf.size > 0:
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
            if self.loadDBThread.isRunning():
                return
            if self.dbdf is not None and self.dbdf.size > 0:
                self.latestRunId = int(self.dbdf.index.values.max())
            else:
                self.latestRunId = -1

            # Incremental refresh: only load runs newer than what we have.
            start_run_id = self.latestRunId + 1 if self.latestRunId is not None and self.latestRunId > 0 else 1
            if self.filepath is not None:
                if not self.loadDBThread.isRunning():
                    self.loadDBProcess.setPath(self.filepath, start_run_id=start_run_id)

    @Slot(float)
    def setMonitorInterval(self, val: float) -> None:
        self.monitor.stop()
        if val > 0:
            self.monitor.start(int(val * 1000))

        self.monitorInput.spin.setValue(val)

    @Slot()
    def monitorTriggered(self) -> None:
        LOGGER.debug('Refreshing DB')
        self.refreshDB()

    @Slot()
    def updateRunList(self) -> None:
        if self.dbdf is None:
            return
        selection = self.dbdf.loc[self.dbdf['started_date'].isin(self._selected_dates)].sort_index(ascending=False)
        show_only_star = self.showOnlyStarAction.isChecked()
        show_also_cross = self.showAlsoCrossAction.isChecked()
        # Pandas types cannot infer that this dataframe will be
        # using int as index and Dict[str, str] as keys
        selection_dict = cast(Dict[int, Dict[str,str]], selection.to_dict(orient='index'))
        self.runList.setRuns(selection_dict, show_only_star, show_also_cross)

    ### handling user selections
    @Slot(list)
    def setDateSelection(self, dates: Sequence[str]) -> None:
        if len(dates) > 0:
            assert self.dbdf is not None
            selection = self.dbdf.loc[self.dbdf['started_date'].isin(dates)].sort_index(ascending=False)
            old_dates = self._selected_dates
            # Pandas types cannot infer that this dataframe will be
            # using int as index and Dict[str, str] as keys
            selection_dict = cast(Dict[int, Dict[str,str]], selection.to_dict(orient='index'))
            if not all(date in old_dates for date in dates):
                show_only_star = self.showOnlyStarAction.isChecked()
                show_also_cross = self.showAlsoCrossAction.isChecked()
                self.runList.setRuns(selection_dict, show_only_star, show_also_cross)
            else:
                self.runList.updateRuns(selection_dict)
            self._selected_dates = tuple(dates)
        else:
            self._selected_dates = ()
            self.runList.clear()
            self.runList.setOverlayText(
                _SELECT_DATE_HINT)

    @Slot(int)
    def setRunSelection(self, runId: int) -> None:
        assert self.filepath is not None
        if sys.version_info >= (3, 11):
            ds = load_dataset_from(self.filepath, runId, read_only=True)
        else:
            ds = load_dataset_from(self.filepath, runId)
        snap = None
        if hasattr(ds, 'snapshot'):
            snap = ds.snapshot

        structure = cast(Dict[str, dict], get_ds_structure(ds))
        # cast away typed dict so we can pop a key
        for k, v in structure.items():
            v.pop('values')
        contentInfo = {'Data structure': structure,
                       'Metadata': ds.metadata,
                       'QCoDeS Snapshot': snap}
        self._sendInfo.emit(contentInfo)

    @Slot(int)
    def plotRun(self, runId: int) -> None:
        assert self.filepath is not None
        fc, win = autoplotQcodesDataset(
            pathAndId=(self.filepath, runId),
            plotWidgetClass=self._plotWidgetClass,
        )
        self._plotWindows[runId] = {
            'flowchart': fc,
            'window': win,
        }
        win.showTime()

    @Slot(str)
    def _onBackendChanged(self, backend: str) -> None:
        backends = _get_plot_backends()
        self._plotWidgetClass = backends.get(backend, self._plotWidgetClass)

    def setTag(self, item: QtWidgets.QTreeWidgetItem, tag: str) -> None:
        # set tag in the database
        assert self.filepath is not None
        runId = int(item.text(0))
        if sys.version_info >= (3, 11):
            ds = load_dataset_from(self.filepath, runId, read_only=False)
        else:
            ds = load_dataset_from(self.filepath, runId)
        ds.add_metadata('inspectr_tag', tag)

        # set tag in self.dbdf
        assert self.dbdf is not None
        self.dbdf.at[runId, 'inspectr_tag'] = tag

        # set tag in the GUI
        tag_char = self.runList.tag_dict[tag]
        item.setText(1, tag_char)

        # refresh the RunInfo widget
        self.setRunSelection(runId)

    def tagSelectedRun(self, tag: str) -> None:
        for item in self.runList.selectedItems():
            current_tag_char = item.text(1)
            tag_char = self.runList.tag_dict[tag]
            if current_tag_char == tag_char:  # if already tagged
                self.setTag(item, '')  # clear tag
            else:  # if not tagged
                self.setTag(item, tag)  # set tag

    @Slot()
    def starSelectedRun(self) -> None:
        self.tagSelectedRun('star')

    @Slot()
    def crossSelectedRun(self) -> None:
        self.tagSelectedRun('cross')


class WindowDict(TypedDict):
    flowchart: Flowchart
    window: QCAutoPlotMainWindow


def inspectr(dbPath: Optional[str] = None,
             plotWidgetClass: Optional[type] = None) -> QCodesDBInspector:
    win = QCodesDBInspector(dbPath=dbPath, plotWidgetClass=plotWidgetClass)
    return win


def main(dbPath: Optional[str], log_level: Union[int, str] = logging.WARNING,
         plotWidgetClass: Optional[type] = None) -> None:
    app = QtWidgets.QApplication([])
    plottrlog.enableStreamHandler(True, log_level)

    win = inspectr(dbPath=dbPath, plotWidgetClass=plotWidgetClass)
    win.show()

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        appinstance = QtWidgets.QApplication.instance()
        assert appinstance is not None
        appinstance.exec_()


def script() -> None:
    parser = argparse.ArgumentParser(description='inspectr -- sifting through qcodes data.')
    parser.add_argument('--dbpath', help='path to qcodes .db file',
                        default=None)
    parser.add_argument("--console-log-level",
                        choices=("ERROR", "WARNING", "INFO", "DEBUG"),
                        default="WARNING")
    args = parser.parse_args()
    main(args.dbpath, args.console_log_level)


def script_pyqtgraph() -> None:
    """Entry point for inspectr using the pyqtgraph plotting backend."""
    from plottr.plot.pyqtgraph.autoplot import AutoPlot as PGAutoPlot

    parser = argparse.ArgumentParser(
        description='inspectr -- sifting through qcodes data (pyqtgraph backend).'
    )
    parser.add_argument('--dbpath', help='path to qcodes .db file',
                        default=None)
    parser.add_argument("--console-log-level",
                        choices=("ERROR", "WARNING", "INFO", "DEBUG"),
                        default="WARNING")
    args = parser.parse_args()
    main(args.dbpath, args.console_log_level, plotWidgetClass=PGAutoPlot)
