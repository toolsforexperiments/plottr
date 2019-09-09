import numpy as np
import qcodes as qc
from qcodes import initialise_database, load_or_create_experiment

from plottr.data.datadict import DataDict
from plottr.utils import testdata
from plottr.node.tools import linearFlowchart
from plottr.data.qcodes_dataset import (
    datadict_from_path_and_run_id,
    QCodesDSLoader,
    get_ds_structure
)

DBPATH = './test_qc_saveandload.db'


def test_load_2dsoftsweep():
    qc.config.core.db_location = DBPATH
    initialise_database()
    exp = load_or_create_experiment('2d_softsweep', sample_name='no sample')

    N = 5
    m = qc.Measurement(exp=exp)
    m.register_custom_parameter('x', unit='cm')
    m.register_custom_parameter('y')

    # check that unused parameters don't mess with
    m.register_custom_parameter('foo')
    dd_expected = DataDict(x=dict(values=np.array([]), unit='cm'),
                           y=dict(values=np.array([])))
    for n in range(N):
        m.register_custom_parameter(f'z_{n}', setpoints=['x', 'y'])
        dd_expected[f'z_{n}'] = dict(values=np.array([]), axes=['x', 'y'])
    dd_expected.validate()

    with m.run() as datasaver:
        for result in testdata.generate_2d_scalar_simple(3, 3, N):
            row = [(k, v) for k, v in result.items()] + [('foo', 1)]
            datasaver.add_result(*row)
            dd_expected.add_data(**result)

    # retrieve data as data dict
    run_id = datasaver.dataset.captured_run_id
    ddict = datadict_from_path_and_run_id(DBPATH, run_id)
    assert ddict == dd_expected


def test_get_ds_structure():
    qc.config.core.db_location = DBPATH
    initialise_database()
    exp = load_or_create_experiment('2d_softsweep', sample_name='no sample')

    N = 5

    m = qc.Measurement(exp=exp)
    m.register_custom_parameter('x', unit='cm')
    m.register_custom_parameter('y')

    # check that unused parameters don't mess with
    m.register_custom_parameter('foo')

    for n in range(N):
        m.register_custom_parameter(f'z_{n}', setpoints=['x', 'y'])

    with m.run() as datasaver:
        dataset = datasaver.dataset

    # test dataset structure function
    expected_structure = {
        'x': {
            'unit': 'cm',
            'values': []
        },
        'y': {
            'unit': '',
            'values': []
        }
        # note that parameter 'foo' is not expected to be included
        # because it's a "standalone" parameter
    }
    for n in range(N):
        expected_structure.update(
            {f'z_{n}': {
                'unit': '',
                'axes': ['x', 'y'],
                'values': []
                }
            }
        )
    structure = get_ds_structure(dataset)
    assert structure == expected_structure


def test_update_qcloader(qtbot):
    qc.config.core.db_location = DBPATH
    initialise_database()
    exp = load_or_create_experiment('2d_softsweep', sample_name='no sample')

    N = 2
    m = qc.Measurement(exp=exp)
    m.register_custom_parameter('x')
    m.register_custom_parameter('y')
    dd_expected = DataDict(x=dict(values=np.array([])),
                           y=dict(values=np.array([])))
    for n in range(N):
        m.register_custom_parameter(f'z_{n}', setpoints=['x', 'y'])
        dd_expected[f'z_{n}'] = dict(values=np.array([]), axes=['x', 'y'])
    dd_expected.validate()

    # setting up the flowchart
    fc = linearFlowchart(('loader', QCodesDSLoader))
    loader = fc.nodes()['loader']

    def check():
        nresults = ds.number_of_results
        loader.update()
        ddict = fc.output()['dataOut']

        if ddict is not None and nresults > 0:
            z_in = dd_expected.data_vals('z_1')
            z_out = ddict.data_vals('z_1')
            if z_out is not None:
                assert z_in.size == z_out.size
                assert np.allclose(z_in, z_out, atol=1e-15)

    with m.run() as datasaver:
        ds = datasaver.dataset
        run_id = datasaver.dataset.captured_run_id
        loader.pathAndId = DBPATH, run_id

        for result in testdata.generate_2d_scalar_simple(3, 3, N):
            row = [(k, v) for k, v in result.items()]
            datasaver.add_result(*row)
            dd_expected.add_data(**result)
            check()
        check()

    # insert data in small chunks, and check
    # while True:
    #     try:
    #         ninsertions = np.random.randint(0, 5)
    #         for n in range(ninsertions):
    #             _ds.add_result(next(results))
    #     except StopIteration:
    #         _ds.mark_complete()
    #         break
    #     check()
    # check()
