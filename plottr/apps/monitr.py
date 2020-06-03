""" plottr.monitr -- a GUI tool for monitoring data files.
"""
import os
from pprint import pprint
from typing import Dict, Any, Optional
from types import MethodType
from functools import partial, partialmethod

import h5py

from .. import QtCore, QtWidgets, Signal, Slot
from ..data.datadict import DataDict
from ..data.datadict_storage import datadict_from_hdf5

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

        self.monitorPath = os.path.abspath(monitorPath)
        self.refreshInterval = refreshInterval
        self.refreshFiles = partial(self.ui.fileList.loadFromPath, self.monitorPath)

        self.monitor = QtCore.QTimer()
        self.monitor.timeout.connect(self.refreshFiles)
        self.monitor.start(self.refreshInterval * 1000)

    @Slot(str)
    def processFileSelection(self, filePath: str):
        groups = hdf5ContentsOverview(filePath)
        self.dataFileSelected.emit(groups)


def hdf5ContentsOverview(filePath: str) -> Dict[str, DataDict]:
    contents = {}
    with h5py.File(filePath, 'r', swmr=True) as f:
        for k in f.keys():
            if not isinstance(f[k], h5py.Group):
                continue
            try:
                contents[k] = datadict_from_hdf5(
                    filePath, k, structure_only=True)
            except:
                pass
    return contents

