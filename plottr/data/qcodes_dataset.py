"""
qcodes_dataset.py

Dealing with qcodes dataset (the database) data in plottr.
"""
import os
from sqlite3 import Connection
from typing import Dict, List, Set, Union, TYPE_CHECKING

import pandas as pd

from qcodes.dataset.data_set import load_by_id
from qcodes.dataset.experiment_container import experiments
from qcodes.dataset.sqlite.database import initialise_or_create_database_at

from .datadict import DataDictBase, DataDict, combine_datadicts
from ..node.node import Node, updateOption

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'

if TYPE_CHECKING:
    from qcodes.dataset.data_set import DataSet
    from qcodes import ParamSpec


def _get_names_of_standalone_parameters(paramspecs: List['ParamSpec']
                                        ) -> Set[str]:
    all_independents = set(spec.name
                           for spec in paramspecs
                           if len(spec.depends_on_) == 0)
    used_independents = set(d for spec in paramspecs for d in spec.depends_on_)
    standalones = all_independents.difference(used_independents)
    return standalones


# Tools for extracting information on runs in a database

def get_ds_structure(ds: 'DataSet'):
    """
    Return the structure of the dataset, i.e., a dictionary in the form
        {
            'dependent_parameter_name': {
                'unit': unit,
                'axes': list of names of independent parameters,
                'values': []
            },
            'independent_parameter_name': {
                'unit': unit,
                'values': []
            },
            ...
        }

    Note that standalone parameters (those which don't depend on any other
    parameter and no other parameter depends on them) are not included
    in the returned structure.
    """

    structure = {}

    paramspecs = ds.get_parameters()

    standalones = _get_names_of_standalone_parameters(paramspecs)

    for spec in paramspecs:
        if spec.name not in standalones:
            structure[spec.name] = {'unit': spec.unit, 'values': []}
            if len(spec.depends_on_) > 0:
                structure[spec.name]['axes'] = list(spec.depends_on_)

    return structure


def get_ds_info(conn: Connection, run_id: int,
                get_structure: bool = True) -> Dict[str, str]:
    """
    Get some info on a run in dict form from a db connection and runId.

    if get_structure is True: return the datastructure in that dataset
    as well (key is `structure' then).
    """
    ds = load_by_id(run_id=run_id, conn=conn)

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
    if _start_ts is not None:
        ret['started date'] = _start_ts[:10]
        ret['started time'] = _start_ts[11:]
    else:
        ret['started date'] = ''
        ret['started time'] = ''

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
    initialise_or_create_database_at(path)
    ds = load_by_id(run_id=run_id)
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
    initialise_or_create_database_at(path)

    run_ids = list(sorted(ds.run_id
                          for exp in experiments()
                          for ds in exp.data_sets()))

    if stop is None:
        stop = len(run_ids)

    run_ids = run_ids[start:stop]

    overview = {}

    for run_id in run_ids:
        ds = load_by_id(run_id)
        overview[run_id] = get_ds_info(ds.conn, run_id,
                                       get_structure=get_structure)

    return overview


def get_runs_from_db_as_dataframe(path):
    """
    Wrapper around `get_runs_from_db` that returns the overview
    as pandas dataframe.
    """
    overview = get_runs_from_db(path)
    df = pd.DataFrame.from_dict(overview, orient='index')
    return df


# Extracting data

def ds_to_datadicts(ds: 'DataSet') -> Dict[str, DataDict]:
    """
    Make DataDicts from a qcodes DataSet.

    :param ds: qcodes dataset
    :returns: dictionary with one item per dependent.
              key: name of the dependent
              value: DataDict containing that dependent and its
                     axes.
    """
    ret = {}
    pdata = ds.get_parameter_data()
    for p, spec in ds.paramspecs.items():
        if spec.depends_on != '':
            axes = spec.depends_on_ # .split(', ')
            data = dict()
            data[p] = dict(unit=spec.unit, axes=axes, values=pdata[p][p])
            for ax in axes:
                axspec = ds.paramspecs[ax]
                data[ax] = dict(unit=axspec.unit, values=pdata[p][ax])
            ret[p] = DataDict(**data)
            ret[p].validate()

    return ret


def ds_to_datadict(ds: 'DataSet') -> DataDictBase:
    ddicts = ds_to_datadicts(ds)
    ddict = combine_datadicts(*[v for k, v in ddicts.items()])
    return ddict


def datadict_from_path_and_run_id(path: str, run_id: int) -> DataDictBase:
    """
    Load a qcodes dataset as a DataDict.

    :param path: file path of the qcodes .db file.
    :param run_id: run_id of the dataset.
    :return: DataDict containing the data.
    """
    initialise_or_create_database_at(path)
    ds = load_by_id(run_id=run_id)
    return ds_to_datadict(ds)


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
        if None not in self._pathAndId:
            path, runId = self._pathAndId

            initialise_or_create_database_at(path)
            ds = load_by_id(run_id=runId)

            guid = ds.guid
            if ds.number_of_results > self.nLoadedRecords:
                title = f"{os.path.split(path)[-1]} | " \
                        f"run ID: {runId} | GUID: {guid}"
                info = """Started: {}
Finished: {}
GUID: {}
DB-File [ID]: {} [{}]""".format(ds.run_timestamp(), ds.completed_timestamp(),
                                guid, path, runId)

                data = ds_to_datadict(ds)
                data.add_meta('title', title)
                data.add_meta('info', info)
                data.add_meta('qcodes_guid', guid)
                data.add_meta('qcodes_db', path)
                data.add_meta('qcodes_runId', runId)
                data.add_meta('qcodes_completedTS', ds.completed_timestamp())
                data.add_meta('qcodes_runTS', ds.run_timestamp())
                self.nLoadedRecords = ds.number_of_results
                return dict(dataOut=data)
