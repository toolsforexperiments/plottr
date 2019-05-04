"""
qcodes_dataset.py

Dealing with qcodes dataset (the database) data in plottr.
"""
import os
from sqlite3 import Connection
from typing import Dict, List, Union, Optional

import numpy as np
import pandas as pd

from qcodes.dataset.data_set import DataSet
from qcodes.dataset.sqlite_base import (
    get_dependencies, get_dependents, get_layout,
    get_runs, connect
)
from .datadict import DataDict
from ..node.node import Node, updateOption

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


### Tools for extracting information on runs in a database

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

def get_data_from_ds(ds: DataSet, start: Optional[int] = None,
                     end: Optional[int] = None) -> Dict[str, List[List]]:
    """
    Returns a dictionary in the format {'name' : data}, where data
    is what dataset.get_data('name') returns, i.e., a list of lists, where
    the inner list is the row as inserted into the DB.

    with `start` and `end` only a subset of rows in the DB can be specified.
    """
    names = [n for n, v in ds.paramspecs.items()]
    return {n : np.squeeze(ds.get_data(n, start=start, end=end)) for n in names}


def get_all_data_from_ds(ds: DataSet) -> Dict[str, List[List]]:
    """
    Returns a dictionary in the format {'name' : data}, where data
    is what dataset.get_data('name') returns, i.e., a list of lists, where
    the inner list is the row as inserted into the DB.
    """
    return get_data_from_ds(ds)


def ds_to_datadict(ds: DataDict, start: Optional[int] = None,
                   end: Optional[int] = None) -> DataDict:
    """
    Make a datadict from a qcodes dataset.
    `start` and `end` allow selection of only a subset of rows.
    """
    # data = expand(get_data_from_ds(ds, start=start, end=end))
    data = get_data_from_ds(ds, start=start, end=end)
    struct = get_ds_structure(ds)
    datadict = DataDict(**struct)
    for k, v in data.items():
        datadict[k]['values'] = data[k]

    datadict.validate()
    return datadict


def datadict_from_path_and_run_id(path: str, run_id: int, **kw) -> DataDict:
    ds = DataSet(path_to_db=path, run_id=run_id)
    return ds_to_datadict(ds, **kw)


### qcodes dataset loader node

class QCodesDSLoader(Node):

    nodeName = 'QCodesDSLoader'
    uiClass = None
    useUi = False

    def __init__(self, *arg, **kw):
        self._pathAndId = (None, None)
        self.nLoadedRecords = 0

        super().__init__(*arg, **kw)

    ### Properties

    @property
    def pathAndId(self):
        return self._pathAndId

    @pathAndId.setter
    @updateOption('pathAndId')
    def pathAndId(self, val):
        if val != self.pathAndId:
            self._pathAndId = val
            self.nLoadedRecords = 0

    ### processing

    def process(self, **kw):
        if not None in self._pathAndId:
            path, runId = self._pathAndId
            ds = DataSet(path_to_db=path, run_id=runId)
            if ds.number_of_results > self.nLoadedRecords:
                title = f"{os.path.split(path)[-1]} [{runId}]"
                info = """Started: {}
Finished: {}
DB-File [ID]: {} [{}]""".format(ds.run_timestamp(), ds.completed_timestamp(),
                                path, runId)

                data = ds_to_datadict(ds)
                data.add_meta('title', title)
                data.add_meta('info', info)
                data.add_meta('qcodes_db', path)
                data.add_meta('qcodes_runId', runId)
                data.add_meta('qcodes_completedTS', ds.completed_timestamp())
                data.add_meta('qcodes_runTS', ds.run_timestamp())
                self.nLoadedRecords = ds.number_of_results
                return dict(dataOut=data)
