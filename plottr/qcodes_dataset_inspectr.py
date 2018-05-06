import sys
import os
import sqlite3
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (QApplication, QAction,
                             QFrame, QHBoxLayout, QLabel,
                             QMainWindow,QSizePolicy,
                             QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                             QWidget)

from .qcodes_dataset import getRunOverviewDataFrame, datasetDictFromFile
from .client import DataSender


class DatabaseTreeView(QTreeWidget):

    fileDropped = pyqtSignal(str)
    datasetTriggered = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setAcceptDrops(True)
        self.setDefaultDropAction(Qt.CopyAction)

        self.setColumnCount(7)
        self.setHeaderLabels(['Start', 'Experiment', 'Sample',
            'Data fields', 'Size', 'Run ID', 'Finished'])

        self.itemDoubleClicked.connect(self.doubleClickTrigger)

    @pyqtSlot(QTreeWidgetItem, int)
    def doubleClickTrigger(self, item, col):
        try:
            runId = int(item.text(5))
            self.datasetTriggered.emit(runId)
        except ValueError:
            pass

    def populate(self, df):
        self.clear()

        df = df.sort_values(['startDate', 'startTime'])
        gb = df.groupby('startDate')

        for date, idxs in gb.groups.items():
            dateItem = QTreeWidgetItem([date] +  6 * [''])
            for idx in idxs.values:
                row = df[df.index==idx]
                runItem = QTreeWidgetItem([
                    row.startTime.values[0],
                    row.experimentName.values[0],
                    str(row.sampleName.values[0]),
                    row.dataFields.values[0],
                    str(row.dataRecords.values[0]),
                    str(idx),
                    row.finishedDate.values[0] + ' ' + row.finishedTime.values[0],
                ])
                dateItem.addChild(runItem)

            self.addTopLevelItem(dateItem)
            dateItem.setExpanded(True)


    # Drag/Drop Handling
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


class InspectrMain(QMainWindow):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.filepath = None

        self.setWindowTitle('inspectr')
        self.activateWindow()

        self.dataBaseTree = DatabaseTreeView()
        self.centralWidget = self.dataBaseTree
        self.setCentralWidget(self.centralWidget)
        self.centralWidget.setFocus()

        reloadAction = QAction('&Reload', self)
        reloadAction.setShortcut('Ctrl+R')
        reloadAction.triggered.connect(self.reload)

        menu = self.menuBar()
        fileMenu = menu.addMenu('&File')
        fileMenu.addAction(reloadAction)

        self.dataBaseTree.datasetTriggered.connect(self.triggerPlot)
        self.dataBaseTree.fileDropped.connect(self.setFilePath)

    @pyqtSlot()
    def reload(self):
        self.setFilePath(self.filepath)

    @pyqtSlot(str)
    def setFilePath(self, filepath):
        if not filepath:
            return

        self.filepath = os.path.abspath(filepath)
        try:
            self.dbOverview = getRunOverviewDataFrame(filepath)
        except sqlite3.DatabaseError:
            print('Not a SQLite3 database.')
            return

        self.dataBaseTree.populate(self.dbOverview)
        self.setWindowTitle('inspectr - {}'.format(self.filepath))

    @pyqtSlot(int)
    def triggerPlot(self, runId):
        data = datasetDictFromFile(self.filepath, runId)
        sender = DataSender("{} # run ID = {}".format(self.filepath, runId))
        sender.data['datasets'] = data
        sender.sendData()
