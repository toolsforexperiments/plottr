""" plottr.monitr -- a GUI tool for monitoring data files.
"""
import os
import time
from typing import Dict, Any, Optional, List
from types import MethodType
from functools import partial, partialmethod

import h5py

from .. import QtCore, QtWidgets, Signal, Slot
from ..data.datadict import DataDict
from ..data.datadict_storage import datadict_from_hdf5, all_datadicts_from_hdf5
from ..apps.autoplot import autoplotDDH5

from .ui.Monitr_UI import Ui_MainWindow


class Monitr(QtWidgets.QMainWindow):

    #: Signal(object) -- emitted when a valid data file is selected.
    #: Arguments:
    #:  - a dictionary containing the datadicts found in the file (as top-level groups)
    dataFileSelected = Signal(object)

    def __init__(self, monitorPath: str = '.', refreshInterval: int = 1,
                 parent=None):

        super().__init__(parent=parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.plotDialogs = {}
        self.selectedFile = None
        self.newFiles = []

        self.monitorPath = os.path.abspath(monitorPath)
        self.refreshInterval = refreshInterval
        self.refreshFiles = partial(self.ui.fileList.loadFromPath, self.monitorPath,
                                    emitNew=True)
        self.ui.fileList.loadFromPath(self.monitorPath, emitNew=False)

        self.monitor = QtCore.QTimer()
        self.monitor.timeout.connect(self.refreshFiles)
        self.monitor.timeout.connect(self.plotQueuedFiles)
        self.monitor.start(self.refreshInterval * 1000)

    @Slot(str)
    def processFileSelection(self, filePath: str):
        self.selectedFile = filePath
        groups = all_datadicts_from_hdf5(filePath, structure_only=True)
        self.dataFileSelected.emit(groups)

    @Slot(list)
    def onNewDataFilesFound(self, files: List[str]):
        if not self.ui.autoPlotNewAction.isChecked():
            return

        self.newFiles += files

    @Slot()
    def plotQueuedFiles(self):
        if not self.ui.autoPlotNewAction.isChecked():
            return

        removeFiles = []
        for f in self.newFiles:
            try:
                contents = all_datadicts_from_hdf5(f, structure_only=True)
            except OSError:
                contents = {}

            if len(contents) > 0:
                for grp in contents.keys():
                    self.plot(f, grp)
                removeFiles.append(f)

        for f in removeFiles:
            self.newFiles.remove(f)

    @Slot(str)
    def plotSelected(self, group: str):
        self.plot(self.selectedFile, group)

    def plot(self, filePath: str, group: str):
        fc, win = autoplotDDH5(filePath, group)
        plotId = time.time()
        while plotId in self.plotDialogs:
            plotId += 1e-6
        self.plotDialogs[plotId] = dict(
            flowchart=fc,
            window=win,
            path=filePath,
            group=group,
        )
        win.windowClosed.connect(lambda: self.onPlotClose(plotId))
        win.show()

    def onPlotClose(self, plotId: float):
        self.plotDialogs[plotId]['flowchart'].deleteLater()
        self.plotDialogs[plotId]['window'].deleteLater()
        self.plotDialogs.pop(plotId, None)


