import time
import os
import json
import copy
import numpy as np
import pandas as pd
import qcodes as qc
from qcodes.dataset.data_set import DataSet
from qcodes.dataset.experiment_container import Experiment
from qcodes.dataset.sqlite_base import (connect, get_dependencies,
                                        get_dependents, get_layout, 
                                        get_runs, _convert_array)

from .client import DataSender


# general methods for dealing with qcodes data
def datasetFromFile(path, runId):
    qc.config['core']['db_location'] = path
    ds = DataSet(path)
    ds.run_id = runId
    return ds


def getDatasetStructure(ds):
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


def getDatasetAsDict(ds):
    struct = getDatasetStructure(ds)
    for n in struct.keys():
        struct[n]['values'] = np.array(ds.get_values(n)).reshape(-1).tolist()
    return struct


def datasetStructureFromFile(path, runId):
    ds = datasetFromFile(path, runId)
    return getDatasetStructure(ds)


def datasetDictFromFile(path, runId):
    ds = datasetFromFile(path, runId)
    return getDatasetAsDict(ds)


def getRunOverview(dbPath):
    try:
        conn = connect(dbPath)
        runs = get_runs(conn)
    except:
        raise

    dsets = {
        'runId' : [r['run_id'] for r in runs],
        'experimentName' : [],
        'sampleName' : [],
        'dataFields' : [],
        'startDate' : [ time.strftime("%Y-%m-%d", time.localtime(r['run_timestamp'])) for r in runs ],
        'startTime' : [ time.strftime("%H:%M:%S", time.localtime(r['run_timestamp'])) for r in runs ],
        'finishedDate' : [ time.strftime("%Y-%m-%d", time.localtime(r['completed_timestamp'])) for r in runs ],
        'finishedTime' : [ time.strftime("%H:%M:%S", time.localtime(r['completed_timestamp'])) for r in runs ],
        'dataRecords' : [],
    }

    qc.config['core']['db_location'] = dbPath

    for runId in dsets['runId']:
        ds = DataSet(dbPath)
        ds.run_id = runId
        exp = Experiment(dbPath)
        exp.exp_id = ds.exp_id

        dsets['experimentName'].append(exp.name)
        dsets['sampleName'].append(exp.sample_name)

        structure = getDatasetStructure(ds)
        dsInfo = ""
        for k, v in structure.items():
            if 'axes' in v:
                axInfo = ""
                for a in v['axes']:
                    axInfo += f"{a}, "
                if len(axInfo) > 2:
                    axInfo = axInfo[:-2]

                dsInfo += f"{k} ({axInfo}), "

        dsSize = ds.number_of_results
        if len(dsInfo) > 2:
            dsInfo = dsInfo[:-2]

        dsets['dataFields'].append(dsInfo)
        dsets['dataRecords'].append(dsSize)

    return dsets


def getRunOverviewDataFrame(runs):
    if isinstance(runs, str):
        ro = getRunOverview(runs)
    else:
        ro = runs

    idx = ro.pop('runId')
    df = pd.DataFrame(ro, index=idx)
    return df


class QcodesDatasetSubscriber(object):

    def __init__(self, dataset, log=False):
        self.ds = dataset
        dbpath = os.path.abspath(qc.config['core']['db_location'])

        self.dataId = "{} # run ID = {}".format(dbpath, self.ds.run_id)
        self.sender = DataSender(self.dataId)
        self.params = [ p.name for p in self.ds.get_parameters() ]
        self.dataStructure = getDatasetStructure(self.ds)

        self.logId = None
        if log:
            self.logId = 0
            self.logDir = './plottr_logs/run-{}'.format(self.ds.run_id)
            os.makedirs(self.logDir)

    def __call__(self, results, length, state):
        newData = dict(zip(self.params, list(zip(*results))))
        data = copy.deepcopy(self.dataStructure)

        # if the paramtype was array we'll have byte encoding now.
        # we need to revert that to numeric lists to be able to 
        # send it via json.
        # we also need to expand the numeric values appropriately.

        # the rule here is the following, in agreement with the qcodes dataset:
        # * we can have either scalar/numeric values in the results, or arrays.
        # * numerics have size 1, per definition
        # * arrays can have arbitrary length, but all arrays must have the same length
        # to extract the data correctly, we must check 1) if arrays are present in the results,
        # 2) what the length is, and 3) if appropriate, expand the numerics such
        # that all results have the same length.
        arrLen = None
        for k, v in newData.items():
            if len(v) > 0 and isinstance(v[0], bytes):
                arrLen = _convert_array(v[0]).size

        for k, v in newData.items():
            if len(v) > 0 and isinstance(v[0], bytes):
                v2 = []
                for x in v:
                    arr = _convert_array(x)
                    v2 += arr.tolist()
                data[k]['values'] = v2
            else:
                if arrLen is not None:
                    _vals = []
                    for x in v:
                        _vals += [x for i in range(arrLen)]
                    data[k]['values'] = _vals
                else:
                    data[k]['values'] = list(v)

        self.sender.data['datasets'] = data
        self.sender.sendData()

        if self.logId is not None:
            fn = os.path.join(self.logDir, 'call-{}.json'.format(self.logId))
            with open(fn, 'w') as f:
                json.dump(dict(newData=newData, 
                               data=data,
                               dataStructure=self.dataStructure,
                               senderData=self.sender.data['datasets']),
                          fp=f, indent=2)
            self.logId += 1
