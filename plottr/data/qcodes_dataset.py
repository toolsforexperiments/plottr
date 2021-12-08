"""
qcodes_dataset.py

Dealing with qcodes dataset (the database) data in plottr.
"""
import os
from itertools import chain
from operator import attrgetter
from typing import Dict, List, Set, Union, TYPE_CHECKING, Any, Tuple, Optional, cast

from typing_extensions import TypedDict

import pandas as pd

from qcodes.dataset.data_set import load_by_id
from qcodes.dataset.experiment_container import experiments
from qcodes.dataset.sqlite.database import initialise_or_create_database_at

from .datadict import DataDictBase, DataDict, combine_datadicts
from ..node.node import Node, updateOption

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'

if TYPE_CHECKING:
    try:
        from qcodes.dataset import DataSetProtocol
    except ImportError:
        from qcodes.dataset.data_set import DataSet as DataSetProtocol
    from qcodes import ParamSpec


def _get_names_of_standalone_parameters(paramspecs: List['ParamSpec']
                                        ) -> Set[str]:
    all_independents = set(spec.name
                           for spec in paramspecs
                           if len(spec.depends_on_) == 0)
    used_independents = set(d for spec in paramspecs for d in spec.depends_on_)
    standalones = all_independents.difference(used_independents)
    return standalones


class IndependentParameterDict(TypedDict):
    unit: str
    label: str
    values: List[Any]


class DependentParameterDict(IndependentParameterDict):
    axes: List[str]


DataSetStructureDict = Dict[str, Union[IndependentParameterDict, DependentParameterDict]]


class DataSetInfoDict(TypedDict):
    experiment: str
    sample: str
    name: str
    completed_date: str
    completed_time: str
    started_date: str
    started_time: str
    structure: Optional[DataSetStructureDict]
    records: int
    guid: str
    inspectr_tag: str


# Tools for extracting information on runs in a database


def get_ds_structure(
        ds: 'DataSetProtocol'
) -> DataSetStructureDict:
    """
    Return the structure of the dataset, i.e., a dictionary in the form
        {
            'dependent_parameter_name': {
                'unit': unit,
                'label': label,
                'axes': list of names of independent parameters,
                'values': []
            },
            'independent_parameter_name': {
                'unit': unit,
                'label': label,
                'values': []
            },
            ...
        }

    Note that standalone parameters (those which don't depend on any other
    parameter and no other parameter depends on them) are not included
    in the returned structure.
    """

    structure: DataSetStructureDict = {}

    paramspecs = ds.get_parameters()

    standalones = _get_names_of_standalone_parameters(paramspecs)

    for spec in paramspecs:
        if spec.name not in standalones:
            if len(spec.depends_on_) > 0:
                structure[spec.name] = DependentParameterDict(unit=spec.unit,
                                                              label=spec.label,
                                                              values=[],
                                                              axes=list(spec.depends_on_))
            else:
                structure[spec.name] = IndependentParameterDict(unit=spec.unit,
                                                                label=spec.label,
                                                                values=[])
    return structure


def get_ds_info(ds: 'DataSetProtocol', get_structure: bool = True) -> DataSetInfoDict:
    """
    Get some info on a DataSet in dict.

    if get_structure is True: return the datastructure in that dataset
    as well (key is `structure' then).
    """
    _complete_ts = ds.completed_timestamp()
    if _complete_ts is not None:
        completed_date = _complete_ts[:10]
        completed_time = _complete_ts[11:]
    else:
        completed_date = ''
        completed_time = ''

    _start_ts = ds.run_timestamp()
    if _start_ts is not None:
        started_date = _start_ts[:10]
        started_time = _start_ts[11:]
    else:
        started_date = ''
        started_time = ''

    if get_structure:
        structure: Optional[DataSetStructureDict] = get_ds_structure(ds)
    else:
        structure = None

    data = DataSetInfoDict(
        experiment=ds.exp_name,
        sample=ds.sample_name,
        name=ds.name,
        completed_date=completed_date,
        completed_time=completed_time,
        started_date=started_date,
        started_time=started_time,
        structure=structure,
        records=ds.number_of_results,
        guid=ds.guid,
        inspectr_tag=ds.metadata.get('inspectr_tag', ''),
    )

    return data


def load_dataset_from(path: str, run_id: int) -> 'DataSetProtocol':
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
                     get_structure: bool = False) -> Dict[int, DataSetInfoDict]:
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


def get_runs_from_db_as_dataframe(path: str) -> pd.DataFrame:
    """
    Wrapper around `get_runs_from_db` that returns the overview
    as pandas dataframe.
    """
    overview = get_runs_from_db(path)
    df = pd.DataFrame.from_dict(overview, orient='index')
    return df


# Extracting data

def ds_to_datadicts(ds: 'DataSetProtocol') -> Dict[str, DataDict]:
    """
    Make DataDicts from a qcodes DataSet.

    :param ds: qcodes dataset
    :returns: dictionary with one item per dependent.
              key: name of the dependent
              value: DataDict containing that dependent and its
                     axes.
    """
    ret = {}
    has_cache = hasattr(ds, 'cache')
    if has_cache:
        pdata = ds.cache.data()
    else:
        # qcodes < 0.17
        pdata = ds.get_parameter_data()
    for p, spec in ds.paramspecs.items():
        if spec.depends_on != '':
            axes = spec.depends_on_
            data = dict()
            data[p] = dict(unit=spec.unit, label=spec.label, axes=axes, values=pdata[p][p])
            for ax in axes:
                axspec = ds.paramspecs[ax]
                data[ax] = dict(unit=axspec.unit, label=axspec.label, values=pdata[p][ax])
            ret[p] = DataDict(**data)
            ret[p].validate()

    return ret


def ds_to_datadict(ds: 'DataSetProtocol') -> DataDictBase:
    ddicts = ds_to_datadicts(ds)
    ddict = combine_datadicts(*[v for k, v in ddicts.items()])
    return ddict


### qcodes dataset loader node

class QCodesDSLoader(Node):
    nodeName = 'QCodesDSLoader'
    uiClass = None
    useUi = False

    def __init__(self, *arg: Any, **kw: Any):
        self._pathAndId: Tuple[Optional[str], Optional[int]] = (None, None)
        self.nLoadedRecords = 0
        self._dataset: Optional[DataSetProtocol] = None

        super().__init__(*arg, **kw)

    ### Properties

    @property
    def pathAndId(self) -> Tuple[Optional[str], Optional[int]]:
        return self._pathAndId

    # see https://github.com/python/mypy/issues/1362
    @pathAndId.setter  # type: ignore
    @updateOption('pathAndId')
    def pathAndId(self, val: Tuple[Optional[str], Optional[int]]) -> None:
        if val != self.pathAndId:
            self._pathAndId = val
            self.nLoadedRecords = 0
            self._dataset = None

    def process(self, dataIn: Optional[DataDictBase] = None) -> Optional[Dict[str, Any]]:
        if dataIn is not None:
            raise RuntimeError("QCodesDSLoader.process does not take a dataIn argument")
        if None not in self._pathAndId:
            path, runId = cast(Tuple[str, int], self._pathAndId)

            if self._dataset is None:
                self._dataset = load_dataset_from(path, runId)

            if self._dataset.number_of_results > self.nLoadedRecords:

                guid = self._dataset.guid

                experiment_name = self._dataset.exp_name
                sample_name = self._dataset.sample_name
                dataset_name = self._dataset.name

                run_timestamp = self._dataset.run_timestamp()
                completed_timestamp = self._dataset.completed_timestamp()

                title = f"{os.path.split(path)[-1]} | " \
                        f"run ID: {runId} | GUID: {guid}" \
                        "\n" \
                        f"{sample_name} | {experiment_name} | {dataset_name}"

                info = f"""Started: {run_timestamp}
Finished: {completed_timestamp}
DB-File [ID]: {path} [{runId}]"""

                data = ds_to_datadict(self._dataset)

                data.add_meta('qcodes_experiment_name', experiment_name)
                data.add_meta('qcodes_sample_name', sample_name)
                data.add_meta('qcodes_dataset_name', dataset_name)

                data.add_meta('title', title)
                data.add_meta('info', info)

                data.add_meta('qcodes_guid', guid)
                data.add_meta('qcodes_db', path)
                data.add_meta('qcodes_runId', runId)
                data.add_meta('qcodes_completedTS', completed_timestamp)
                data.add_meta('qcodes_runTS', run_timestamp)
                qcodes_shape = getattr(self._dataset.description, "shapes", None)
                data.add_meta('qcodes_shape', qcodes_shape)

                self.nLoadedRecords = self._dataset.number_of_results

                return dict(dataOut=data)

        return None
