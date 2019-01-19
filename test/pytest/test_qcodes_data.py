import numpy as np
import qcodes as qc
from qcodes import ParamSpec, new_data_set
from qcodes.dataset.database import initialise_database
from qcodes.dataset.experiment_container import load_or_create_experiment

from plottr.apps.tools import make_sequential_flowchart
from plottr.data.qcodes_dataset import (
    datadict_from_path_and_run_id,
    QCodesDSLoader
)

DBPATH = './test_qc_saveandload.db'


def test_load_2dsoftsweep():
    qc.config.core.db_location = DBPATH
    initialise_database()
    exp = load_or_create_experiment('2d_softsweep', sample_name='no sample')

    # define some test data
    x = np.linspace(0, 1., 5)
    y = np.linspace(0, 1., 5)
    xx, yy = np.meshgrid(x, y, indexing='ij')
    zz = np.random.rand(*xx.shape)

    # put data into a new dataset
    ds = new_data_set('2d_softsweep',
                      specs=[ParamSpec('x', 'numeric', unit='A'),
                             ParamSpec('y', 'numeric', unit='B'),
                             ParamSpec('z', 'numeric', unit='C',
                                       depends_on=['x', 'y']), ], )

    def get_next_result():
        for x, y, z in zip(xx.reshape(-1), yy.reshape(-1), zz.reshape(-1)):
            yield dict(x=x, y=y, z=z)

    results = get_next_result()
    for r in results:
        ds.add_result(r)
    ds.mark_complete()

    # retrieve data as data dict
    run_id = ds.run_id
    ddict = datadict_from_path_and_run_id(DBPATH, run_id)

    assert np.all(np.isclose(ddict.data_vals('z'), zz.reshape(-1), atol=1e-15))
    assert np.all(np.isclose(ddict.data_vals('x'), xx.reshape(-1), atol=1e-15))
    assert np.all(np.isclose(ddict.data_vals('y'), yy.reshape(-1), atol=1e-15))


def test_update_qcloader(qtbot):
    qc.config.core.db_location = DBPATH
    initialise_database()
    exp = load_or_create_experiment('2d_softsweep', sample_name='no sample')

    # define test data
    x = np.linspace(0, 1., 5)
    y = np.linspace(0, 1., 5)
    xx, yy = np.meshgrid(x, y, indexing='ij')
    zz = np.random.rand(*xx.shape)

    def get_2dsoftsweep_results():
        for x, y, z in zip(xx.reshape(-1), yy.reshape(-1), zz.reshape(-1)):
            yield dict(x=x, y=y, z=z)

    # create data set
    _ds = new_data_set('2d_softsweep', exp_id=exp.exp_id,
                       specs=[ParamSpec('x', 'numeric', unit='A'),
                              ParamSpec('y', 'numeric', unit='B'),
                              ParamSpec('z', 'numeric', unit='C',
                                        depends_on=['x', 'y']), ], )

    run_id = _ds.run_id
    results = get_2dsoftsweep_results()

    # setting up the flowchart
    nodes, fc = make_sequential_flowchart([QCodesDSLoader])
    loader = nodes[0]
    loader.pathAndId = DBPATH, run_id

    def check():
        nresults = _ds.number_of_results
        loader.update()
        ddict = fc.output()['dataOut']

        z_in = zz.reshape(-1)[:nresults]
        z_out = ddict.data_vals('z')
        assert z_in.size == z_out.size
        assert np.allclose(z_in, z_out, atol=1e-15)

    # insert data in small chunks, and check
    while True:
        try:
            ninsertions = np.random.randint(0, 5)
            for n in range(ninsertions):
                _ds.add_result(next(results))
        except StopIteration:
            _ds.mark_complete()
            break
        check()
    check()
