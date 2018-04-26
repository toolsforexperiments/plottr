import qcodes as qc
from qcodes.dataset.sqlite_base import get_dependencies, get_dependents, get_layout

from .client import DataSender

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

class QcodesDatasetSubscriber(object):

    def __init__(self, dataset):
        self.ds = dataset

        exp_id = self.ds.exp_id
        exp = qc.load_experiment(exp_id)

        self.dataId = "{} | {} | run ID = {}".format(exp.name, exp.sample_name, self.ds.run_id)
        self.sender = DataSender(self.dataId)
        self.params = [ p.name for p in self.ds.get_parameters() ]
        self.dataStructure = get_dataset_structure(self.ds)

    def __call__(self, results, length, state):
        newData = dict(zip(self.params, list(zip(*results))))
        for k, v in newData.items():
            self.dataStructure[k]['values'] = v

        self.sender.data['datasets'] = self.dataStructure
        self.sender.sendData()
