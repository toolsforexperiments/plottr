"""
qcodes_dataset.py

Dealing with qcodes dataset (the database) data in plottr.
"""

from typing import Dict, Tuple, List, Union, Sequence
import json
import time
import os
from copy import deepcopy

import numpy as np
import pandas as pd
from sqlite3 import Connection

from pyqtgraph.Qt import QtGui, QtCore

import qcodes as qc
from qcodes.dataset.experiment_container import Experiment
from qcodes.dataset.data_set import DataSet
from qcodes.dataset.sqlite_base import (get_dependencies, one, transaction,
                                        get_dependents, get_layout,
                                        get_runs, connect)

from .datadict import DataDict


__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'

# Tools for extracting information on runs in a database

def get_ds_structure(ds):
    """
    Return the structure of the dataset, i.e., a dictionary in the form
        {'parameter' : {
            'unit' : unit,
            'axes' : list of dependencies,
            'values' : [],
            },
        ...
        }
    """

    structure = {}

    # for each data param (non-independent param)
    for dependent_id in get_dependents(ds.conn, ds.run_id):

        # get name etc.
        layout = get_layout(ds.conn, dependent_id)
        name = layout['name']
        structure[name] = {'values' : [], 'unit' : layout['unit'], 'axes' : []}

        # find dependencies (i.e., axes) and add their names/units in the right order
        dependencies = get_dependencies(ds.conn, dependent_id)
        for dep_id, iax in dependencies:
            dep_layout = get_layout(ds.conn, dep_id)
            dep_name = dep_layout['name']
            structure[name]['axes'].insert(iax, dep_name)
            structure[dep_name] = {'values' : [], 'unit' : dep_layout['unit']}

    return structure


def get_ds_info(conn: Connection, run_id: int,
                get_structure: bool = True) -> Dict[str, str]:
    """
    Get some info on a run in dict form from a db connection and runId.

    if get_structure is True: return the datastructure in that dataset
    as well (key is `structure' then).
    """
    ds = DataSet(conn=conn, run_id=run_id)

    ret = {}
    ret['experiment'] = ds.exp_name
    ret['sample'] = ds.sample_name

    _complete_ts = ds.completed_timestamp()
    if _complete_ts is not None:
        ret['completed date'] = _complete_ts[:10]
        ret['completed time'] = _complete_ts[11:]
    else:
        ret['completed date'] = ''
        ret['completed time'] = ''

    _start_ts = ds.run_timestamp()
    ret['started date'] = _start_ts[:10]
    ret['started time'] = _start_ts[11:]

    if get_structure:
        ret['structure'] = get_ds_structure(ds)

    ret['records'] = ds.number_of_results

    return ret


def get_ds_info_from_path(path: str, run_id: int,
                          get_structure: bool = True):
    """
    Convenience function that determines the dataset from `path` and
    `run_id`, then calls `get_ds_info`.
    """

    ds = DataSet(path_to_db=path, run_id=run_id)
    return get_ds_info(ds.conn, run_id, get_structure=get_structure)


def get_runs_from_db(path: str, start: int = 0,
                     stop: Union[None, int] = None,
                     get_structure: bool = False):
    """
    Get a db 'overview' dictionary from the db located in `path`.
    `start` and `stop` refer to indices of the runs in the db that we want
    to have details on; if `stop` is None, we'll use runs until the end.
    if `get_structure` is True, include info on the run data structure
    in the return dict.
    """

    conn = connect(path)
    runs = get_runs(conn)

    if stop is None:
        stop = len(runs)

    runs = runs[start:stop]
    overview = {}

    for run in runs:
        run_id = run['run_id']
        overview[run_id] = get_ds_info(conn, run_id, get_structure=get_structure)

    return overview


def get_runs_from_db_as_dataframe(path, *arg, **kw):
    """
    Wrapper around `get_runs_from_db` that returns the overview
    as pandas dataframe.
    """
    overview = get_runs_from_db(path, *arg, **kw)
    df = pd.DataFrame.from_dict(overview, orient='index')
    return df


# Getting data from a dataset

def get_all_data_from_ds(ds: DataSet) -> Dict[str, List[List]]:
    """
    Returns a dictionary in the format {'name' : data}, where data
    is what dataset.get_data('name') returns, i.e., a list of lists, where
    the inner list is the row as inserted into the DB.
    """
    names = [n for n, v in ds.paramspecs.items()]
    return {n : ds.get_data(n) for n in names}


def expand(data: Dict[str, List[List]],
           copy=True) -> Dict[str, np.ndarray]:
    """
    Expands data to get us everying expanded into columns of the same length.
    To achieve the same length, data will be repeated along the most inner
    axis if necessary.

    Arguments:
        data: dictionary in the form {'name' : [[row1], [row2], ...], ...}.
            the values are thus exactly what dataset.get_data('name') will return.
    """
    if copy:
        data = deepcopy(data)

    inner_len = 1
    for k, v in data.items():
        if len(v) == 0:
            return data

        if type(v[0][0]) not in [list, np.ndarray]:
            continue
        else:
            inner_len = len(v[0][0])
            break

    for k, v in data.items():
        v = np.array(v)
        if inner_len > 1 and v.shape[-1] == 1:
            v = np.repeat(v, inner_len, axis=-1)
        v = v.reshape(-1)
        data[k] = v

    return data


def ds_to_datadict(ds: DataDict) -> DataDict:
    """
    Make a datadict from a qcodes dataset
    """
    data = expand(get_all_data_from_ds(ds))
    struct = get_ds_structure(ds)
    datadict = DataDict(**struct)
    for k, v in data.items():
        datadict[k]['values'] = data[k]

    datadict.validate()
    return datadict


def datadict_from_path_and_run_id(path: str, run_id: int) -> DataDict:
    ds = DataSet(path_to_db=path, run_id=run_id)
    return ds_to_datadict(ds)


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
        print(f'should now launch plotting of {runId}')


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
        self.sendInfo.connect(self.runInfo.setInfo)

        if self.filepath is not None:
            self.loadFullDB(self.filepath)

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
