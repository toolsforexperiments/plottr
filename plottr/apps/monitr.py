""" plottr.monitr -- a GUI tool for monitoring data files.
"""
import sys
import os
import argparse
from typing import List, Optional, Dict, Any
from functools import partial
import importlib
from multiprocessing import Process

from .. import QtCore, QtWidgets, Signal, Slot
from ..data.datadict_storage import all_datadicts_from_hdf5
from ..utils.misc import unwrap_optional

from .ui.Monitr_UI import Ui_MainWindow


class Monitr(QtWidgets.QMainWindow):

    # TODO: keep a list of app processes and monitor them if alive.

    #: Signal(object) -- emitted when a valid data file is selected.
    #: Arguments:
    #:  - a dictionary containing the datadicts found in the file (as top-level groups)
    dataFileSelected = Signal(object)

    def __init__(self, monitorPath: str = '.',
                 refreshInterval: int = 1,
                 parent: Optional[QtWidgets.QMainWindow] = None):

        super().__init__(parent=parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.plotDialogs: Dict[int, dict] = {}
        self.selectedFile: Optional[str] = None
        self.newFiles: List[str] = []

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
    def processFileSelection(self, filePath: str) -> None:
        self.selectedFile = filePath
        groups = all_datadicts_from_hdf5(filePath, structure_only=True)
        self.dataFileSelected.emit(groups)

    @Slot(list)
    def onNewDataFilesFound(self, files: List[str]) -> None:
        if not self.ui.autoPlotNewAction.isChecked():
            return

        self.newFiles += files

    @Slot()
    def plotQueuedFiles(self) -> None:
        if not self.ui.autoPlotNewAction.isChecked():
            return

        # FIXME: sometimes opening a file will never succeed.
        #   we should make sure that we don't try reloading it over and over.
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
    def plotSelected(self, group: str) -> None:
        self.plot(unwrap_optional(self.selectedFile), group)

    def plot(self, filePath: str, group: str) -> None:
        plotApp = 'plottr.apps.autoplot.autoplotDDH5'
        process = launchApp(plotApp, filePath, group)
        if process.pid is not None:
            self.plotDialogs[process.pid] = dict(
                process=process,
                path=filePath,
                group=group,
            )


def script() -> int:
    parser = argparse.ArgumentParser(description='Monitr main application')
    parser.add_argument("path", help="path to monitor for data", default=None)
    parser.add_argument("-r", "--refresh_interval", default=2, type=float,
                        help="interval at which to look for changes in the "
                             "monitored path (in seconds)")
    args = parser.parse_args()

    path = os.path.abspath(args.path)
    if not (os.path.exists(path) and os.path.isdir(path)):
        print('Invalid path.')
        sys.exit()

    app = QtWidgets.QApplication([])
    win = Monitr(path, args.refresh_interval)
    win.show()
    return app.exec_()


def launchApp(appPath: str, filepath: str, group: str, **kwargs: Any) -> Process:
    p = Process(target=_runAppStandalone,
                args=(appPath, filepath, group),
                kwargs=kwargs)
    p.start()
    p.join(timeout=0)
    return p


def _runAppStandalone(appPath: str, filepath: str, group: str, **kwargs: Any) -> Any:
    sep = appPath.split('.')
    modName = '.'.join(sep[:-1])
    funName = sep[-1]
    mod = importlib.import_module(modName)
    fun = getattr(mod, funName)

    app = QtWidgets.QApplication([])
    fc, win = fun(filepath, group, **kwargs)
    win.show()
    return app.exec_()
