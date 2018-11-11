import os

from pyqtgraph.Qt import QtGui, QtCore

from .. import log as plottrlog
from ..data.qcodes_dataset import (get_runs_from_db_as_dataframe,
                                   get_ds_info_from_path,)
from .autoplot import autoplotQcodesDataset

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'

### Database inspector tool

def dictToTreeWidgetItems(d):
    items = []
    for k, v in d.items():
        if not isinstance(v, dict):
            item = QtGui.QTreeWidgetItem([str(k), str(v)])
        else:
            item = QtGui.QTreeWidgetItem([k, ''])
            for child in dictToTreeWidgetItems(v):
                item.addChild(child)
        items.append(item)
    return items

class DateList(QtGui.QListWidget):

    datesSelected = QtCore.pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setSelectionMode(QtGui.QListView.ExtendedSelection)
        self.itemSelectionChanged.connect(self.sendSelectedDates)

    @QtCore.pyqtSlot(list)
    def updateDates(self, dates):
        for d in dates:
            if len(self.findItems(d, QtCore.Qt.MatchExactly)) == 0:
                self.insertItem(0, d)

        self.sortItems(QtCore.Qt.DescendingOrder)

    @QtCore.pyqtSlot()
    def sendSelectedDates(self):
        selection = [item.text() for item in self.selectedItems()]
        self.datesSelected.emit(selection)


class RunList(QtGui.QTreeWidget):

    cols = ['Run ID', 'Experiment', 'Sample', 'Started', 'Completed', 'Records']

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
        lst.append(vals.get('started date', '') + ' ' + vals.get('started time', ''))
        lst.append(vals.get('started date', '') + ' ' + vals.get('completed time', ''))
        lst.append(str(vals.get('records', '')))

        item = QtGui.QTreeWidgetItem(lst)
        self.addTopLevelItem(item)

    def setRuns(self, selection):
        self.clear()
        for runId, record in selection.items():
            self.addRun(runId, **record)

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

class QCodesDBInspector(QtGui.QMainWindow):

    dbdfUpdated = QtCore.pyqtSignal()
    sendInfo = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None, dbPath=None):
        super().__init__(parent)

        self._plotWindows = {}

        self.filepath = dbPath

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
        self.toolbar = self.addToolBar('Options')

        # sizing
        self.resize(640, 640)

        # connect signals/slots
        self.dbdfUpdated.connect(self.updateDates)
        self.dbdfUpdated.connect(self.showDBPath)

        self.dateList.datesSelected.connect(self.setDateSelection)
        self.runList.runSelected.connect(self.setRunSelection)
        self.runList.runActivated.connect(self.plotRun)
        self.sendInfo.connect(self.runInfo.setInfo)

        if self.filepath is not None:
            self.loadFullDB(self.filepath)

    def closeEvent(self, event):
        print('Bye now!')

    @QtCore.pyqtSlot()
    def showDBPath(self):
        path = os.path.abspath(self.filepath)
        self.status.showMessage(path)

    def loadFullDB(self, path=None):
        if path is not None and path != self.filepath:
            self.filepath = path

        self.dbdf = get_runs_from_db_as_dataframe(self.filepath)
        self.dbdfUpdated.emit()

    @QtCore.pyqtSlot()
    def updateDates(self):
        dates = list(self.dbdf.groupby('started date').indices.keys())
        self.dateList.updateDates(dates)

    @QtCore.pyqtSlot(list)
    def setDateSelection(self, dates):
        selection = self.dbdf.loc[self.dbdf['started date'].isin(dates)].sort_index(ascending=False)
        self.runList.setRuns(selection.to_dict(orient='index'))

    @QtCore.pyqtSlot(int)
    def setRunSelection(self, runId):
        info = get_ds_info_from_path(self.filepath, runId, get_structure=True)
        structure = info['structure']
        for k, v in structure.items():
            v.pop('values')
        contentInfo = {'data' : structure}
        self.sendInfo.emit(contentInfo)

    @QtCore.pyqtSlot(int)
    def plotRun(self, runId):
        fc, win = autoplotQcodesDataset()
        fc.nodes()['QCodesDSLoader.0'].pathAndId = self.filepath, runId
        self._plotWindows[runId] = {
            'flowchart' : fc,
            'window' : win,
        }

def inspectr(dbPath: str = None):
    win = QCodesDBInspector(dbPath=dbPath)
    return win
