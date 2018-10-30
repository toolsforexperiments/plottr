import numpy as np
import json
import time
import qcodes as qc
from qcodes.dataset.experiment_container import Experiment
from qcodes.dataset.data_set import DataSet
from qcodes.dataset.sqlite_base import (get_dependencies, one, transaction,
                                        get_dependents, get_layout)
from .datadict import DataDict

class DataSetDict(DataDict):

    @staticmethod
    def get_run_timestamp(ds):
        sql = """
        SELECT run_timestamp
        FROM
        runs
        WHERE
        run_id= ?
        """
        c = transaction(ds.conn, sql, ds.run_id)
        run_timestamp = one(c, 'run_timestamp')
        return run_timestamp

    @staticmethod
    def get_completed_timestamp(ds):
        sql = """
        SELECT completed_timestamp
        FROM
        runs
        WHERE
        run_id= ?
        """
        c = transaction(ds.conn, sql, ds.run_id)
        timestamp = one(c, 'completed_timestamp')
        return timestamp

    @staticmethod
    def get_dataset_structure(ds):
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

    def __init__(self, filepath=None, run_id=None, *arg, **kw):
        if filepath is None:
            filepath = qc.config['core']['db_location']
        self._filepath = filepath
        self._run_id = run_id

        if self._run_id is None:
            super().__init__(*arg, **kw)
        else:
            if len(arg) > 0 or len(kw) > 0:
                raise ValueError("Cannot specify both run_id and initial data.")
            super().__init__()
            self.from_dataset()

    def _exp(self):
        exp = Experiment(self._filepath)
        exp.exp_id = self._ds().exp_id
        return exp

    def _ds(self):
        ds = DataSet(self._filepath)
        ds.run_id = self._run_id
        return ds

    def from_dataset(self):
        ds = self._ds()
        self.clear()
        for k, v in DataSetDict.get_dataset_structure(ds).items():
            self[k] = v

        for k in self.keys():
            self[k]['values'] = np.array(ds.get_data(k)).reshape(-1)

        self.fill_dataset_info()

    def get_snapshot(self):
        ds = self._ds()
        try:
            s = ds.get_metadata('snapshot')
            return json.loads(s)
        except:
            return {}

    def fill_dataset_info(self):
        self.ds_info = {}

        self.ds_info['filepath'] = self._filepath
        self.ds_info['run_id'] = self._run_id
        self.ds_info['exp_name'] = self._exp().name
        self.ds_info['sample_name'] = self._exp().sample_name
        self.ds_info['run_timestamp'] = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(self.get_run_timestamp(self._ds())))
        self.ds_info['completed_timestamp'] = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(self.get_completed_timestamp(self._ds())))

    def dslabel_short(self):
        return "{} ({}) [{}]".format(
            self.ds_info['filepath'],
            self.ds_info['run_id'],
            self.ds_info['run_timestamp'],
        )

    def dslabel_long(self):
        return "{} ({}) [{} : {}] [{}]".format(
            self.ds_info['filepath'],
            self.ds_info['run_id'],
            self.ds_info['exp_name'],
            self.ds_info['sample_name'],
            self.ds_info['run_timestamp'],
        )
