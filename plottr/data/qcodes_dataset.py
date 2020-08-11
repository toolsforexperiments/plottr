"""
qcodes_dataset.py

Dealing with qcodes dataset (the database) data in plottr.
"""
import os
from itertools import chain
from operator import attrgetter
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


def get_ds_info(ds: 'DataSet', get_structure: bool = True) -> Dict[str, Union[str,int]]:
    """
    Get some info on a DataSet in dict.

    if get_structure is True: return the datastructure in that dataset
    as well (key is `structure' then).
    """
    ret: Dict[str, Union[str, int]] = {}
    ret['experiment'] = ds.exp_name
    ret['sample'] = ds.sample_name
    ret['name'] = ds.name

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
    ret['guid'] = ds.guid

    return ret


def load_dataset_from(path: str, run_id: int) -> 'DataSet':
    """
    Loads ``DataSet`` with the given ``run_id`` from a database file that
    is located in in the given ``path``.

    Note that after the call to this function, the database location in the
    qcodes config of the current python process is changed to ``path``.
    """
    initialise_or_create_database_at(path)
    return load_by_id(run_id=run_id)


def get_runs_from_db(path: str, start: int = 0,
                     stop: Union[None, int] = None,
                     get_structure: bool = False):
    """
    Get a db ``overview`` dictionary from the db located in ``path``. The
    ``overview`` dictionary maps ``DataSet.run_id``s to dataset information as
    returned by ``get_ds_info`` functions.

    `start` and `stop` refer to indices of the runs in the db that we want
    to have details on; if `stop` is None, we'll use runs until the end.

    If `get_structure` is True, include info on the run data structure
    in the return dict.
    """
    initialise_or_create_database_at(path)

    datasets = sorted(
        chain.from_iterable(exp.data_sets() for exp in experiments()),
        key=attrgetter('run_id')
    )

    # There is no need for checking whether ``stop`` is ``None`` because if
    # it is the following is simply equivalent to ``datasets[start:]``
    datasets = datasets[start:stop]

    overview = {ds.run_id: get_ds_info(ds, get_structure=get_structure)
                for ds in datasets}
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
            axes = spec.depends_on_
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

    # see https://github.com/python/mypy/issues/1362
    @pathAndId.setter  # type: ignore
    @updateOption('pathAndId')
    def pathAndId(self, val):
        if val != self.pathAndId:
            self._pathAndId = val
            self.nLoadedRecords = 0

    ### processing

    def process(self, **kw):
        if None not in self._pathAndId:
            path, runId = self._pathAndId

            ds = load_dataset_from(path, runId)

            if ds.number_of_results > self.nLoadedRecords:

                guid = ds.guid
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
