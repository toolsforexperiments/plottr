import numpy as np
import qcodes as qc
from qcodes import ParamSpec, new_data_set
from qcodes.dataset.database import initialise_database
from qcodes.dataset.experiment_container import load_or_create_experiment

from plottr.data.datadict import DataDict
from plottr.utils import testdata
from plottr.node.tools import linearFlowchart
from plottr.data.qcodes_dataset import (
    datadict_from_path_and_run_id,
    QCodesDSLoader
)

DBPATH = './test_qc_saveandload.db'


def test_load_2dsoftsweep():
    qc.config.core.db_location = DBPATH
    initialise_database()
    exp = load_or_create_experiment('2d_softsweep', sample_name='no sample')

    N = 5
    m = qc.Measurement(exp=exp)
    m.register_custom_parameter('x')
    m.register_custom_parameter('y')
    dd_expected = DataDict(x=dict(values=np.array([])),
                           y=dict(values=np.array([])))
    for n in range(N):
        m.register_custom_parameter(f'z_{n}', setpoints=['x', 'y'])
        dd_expected[f'z_{n}'] = dict(values=np.array([]), axes=['x', 'y'])
    dd_expected.validate()

    with m.run() as datasaver:
        for result in testdata.generate_2d_scalar_simple(3, 3, N):
            row = [(k, v) for k, v in result.items()]
            datasaver.add_result(*row)
            dd_expected.add_data(**result)

    # retrieve data as data dict
    run_id = datasaver.dataset.captured_run_id
    ddict = datadict_from_path_and_run_id(DBPATH, run_id)
    assert ddict == dd_expected


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
    fc = linearFlowchart(('loader', QCodesDSLoader))
    loader = fc.nodes()['loader']
    loader.pathAndId = DBPATH, run_id

    def check():
        nresults = _ds.number_of_results
        loader.update()
        ddict = fc.output()['dataOut']

        if ddict is not None and nresults > 0:
            z_in = zz.reshape(-1)[:nresults]
            z_out = ddict.data_vals('z')
            if z_out is not None:
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
