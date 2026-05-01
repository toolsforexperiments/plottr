import numpy as np
import pytest
from packaging import version

import qcodes as qc
from qcodes import load_or_create_experiment, initialise_or_create_database_at

from plottr.data.datadict import DataDict
from plottr.utils import testdata
from plottr.node.tools import linearFlowchart
from plottr.data.qcodes_dataset import (
    QCodesDSLoader,
    get_ds_structure,
    get_ds_info,
    get_runs_from_db,
    ds_to_datadict)


@pytest.fixture(scope='function')
def empty_db_path(tmp_path):
    db_path = str(tmp_path / 'some.db')
    initialise_or_create_database_at(db_path)
    yield db_path


@pytest.fixture
def experiment(empty_db_path):
    exp = load_or_create_experiment('2d_softsweep', sample_name='no sample')
    yield exp
    exp.conn.close()


@pytest.fixture
def database_with_three_datasets(empty_db_path):
    """Fixture of a database file with 3 DataSets"""
    exp1 = load_or_create_experiment('get_runs_from_db', sample_name='qubit')
    m1 = qc.Measurement(exp=exp1)

    m1.register_custom_parameter('x', unit='cm')
    m1.register_custom_parameter('y')
    m1.register_custom_parameter('foo')
    for n in range(2):
        m1.register_custom_parameter(f'z_{n}', setpoints=['x', 'y'])

    with m1.run() as datasaver:
        dataset11 = datasaver.dataset

    with m1.run() as datasaver:
        datasaver.add_result(('x', 1.), ('y', 2.), ('z_0', 42.), ('z_1', 0.2))

        dataset12 = datasaver.dataset

    exp2 = load_or_create_experiment('give_em', sample_name='now')
    m2 = qc.Measurement(exp=exp2)

    m2.register_custom_parameter('a')
    m2.register_custom_parameter('b', unit='mm')
    m2.register_custom_parameter('c', setpoints=['a', 'b'])

    with m2.run() as datasaver:
        datasaver.add_result(('a', 1.), ('b', 2.), ('c', 42.))
        datasaver.add_result(('a', 4.), ('b', 5.), ('c', 77.))
        dataset2 = datasaver.dataset

    datasets = (dataset11, dataset12, dataset2)

    yield empty_db_path, datasets

    for ds in datasets:
        ds.conn.close()
    exp1.conn.close()
    exp2.conn.close()


def test_load_2dsoftsweep(experiment):
    N = 5
    m = qc.Measurement(exp=experiment)
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
    ddict = ds_to_datadict(datasaver.dataset)
    assert ddict == dd_expected


@pytest.mark.skipif(version.parse(qc.__version__)
                    < version.parse("0.20.0"),
                    reason="Requires QCoDes 0.20.0 or later")
def test_load_2dsoftsweep_known_shape(experiment):
    N = 1
    m = qc.Measurement(exp=experiment)
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

    shape = (3, 3)

    m.set_shapes({'z_0': shape})

    with m.run() as datasaver:
        for result in testdata.generate_2d_scalar_simple(*shape, N):
            row = [(k, v) for k, v in result.items()] + [('foo', 1)]
            datasaver.add_result(*row)
            dd_expected.add_data(**result)

    dd_expected['x']['values'] = dd_expected['x']['values'].reshape(*shape)
    dd_expected['y']['values'] = dd_expected['y']['values'].reshape(*shape)
    dd_expected['z_0']['values'] = dd_expected['z_0']['values'].reshape(*shape)

    # retrieve data as data dict
    ddict = ds_to_datadict(datasaver.dataset)
    assert ddict == dd_expected


def test_get_ds_structure(experiment):
    N = 5

    m = qc.Measurement(exp=experiment)
    m.register_custom_parameter('x', unit='cm',label='my_x_param')
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
            'label': 'my_x_param',
            'values': []
        },
        'y': {
            'unit': '',
            'label': '',
            'values': []
        }
        # note that parameter 'foo' is not expected to be included
        # because it's a "standalone" parameter
    }
    for n in range(N):
        expected_structure.update(
            {f'z_{n}': {
                'unit': '',
                'label': '',
                'axes': ['x', 'y'],
                'values': []
                }
            }
        )
    structure = get_ds_structure(dataset)
    assert structure == expected_structure


def test_get_ds_info(experiment):
    N = 5

    m = qc.Measurement(exp=experiment)

    m.register_custom_parameter('x', unit='cm')
    m.register_custom_parameter('y')
    m.register_custom_parameter('foo')
    for n in range(N):
        m.register_custom_parameter(f'z_{n}', setpoints=['x', 'y'])

    with m.run() as datasaver:
        dataset = datasaver.dataset

        ds_info_with_empty_timestamps = get_ds_info(dataset,
                                                    get_structure=False)
        assert ds_info_with_empty_timestamps['completed_date'] == ''
        assert ds_info_with_empty_timestamps['completed_time'] == ''

    # timestamps are difficult to test for, so we will cheat here and
    # instead of hard-coding timestamps we will just get them from the dataset
    # The same applies to the guid as it contains the timestamp
    started_ts = dataset.run_timestamp()
    completed_ts = dataset.completed_timestamp()

    expected_ds_info = {
        'experiment': '2d_softsweep',
        'sample': 'no sample',
        'completed_date': completed_ts[:10],
        'completed_time': completed_ts[11:],
        'started_date': started_ts[:10],
        'started_time': started_ts[11:],
        'name': 'results',
        'structure': None,
        'records': 0,
        'guid': dataset.guid,
        'inspectr_tag': ''
    }

    ds_info = get_ds_info(dataset, get_structure=False)

    assert ds_info == expected_ds_info

    expected_ds_info_with_structure = expected_ds_info.copy()
    expected_ds_info_with_structure['structure'] = get_ds_structure(dataset)

    ds_info_with_structure = get_ds_info(dataset)

    assert ds_info_with_structure == expected_ds_info_with_structure


def test_get_runs_from_db(database_with_three_datasets):
    db_path, datasets = database_with_three_datasets

    # Prepare an expected overview of the created database
    expected_overview = {ds.run_id: get_ds_info(ds, get_structure=False)
                         for ds in datasets}

    # Get the actual overview of the created database
    overview = get_runs_from_db(db_path)  # get_structure=False is the default

    # Finally, assert
    assert overview == expected_overview

    # Prepare an expected overview of the created database WITH STRUCTURE
    expected_overview_with_structure = {
        ds.run_id: get_ds_info(ds, get_structure=True)
        for ds in datasets
    }

    # Get the actual overview of the created database WITH STRUCTURE
    overview_with_structure = get_runs_from_db(db_path, get_structure=True)

    # Finally, assert WITH STRUCTURE
    assert overview_with_structure == expected_overview_with_structure


def test_update_qcloader(qtbot, empty_db_path):
    db_path = empty_db_path

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
        loader.pathAndId = db_path, run_id

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


# -- Records counter tests (qcodes_db_overview) --

def _make_qcodes_db_with_runs(db_path: str, n_runs: int = 1) -> str:
    """Helper: create a QCodes DB with n_runs simple numeric datasets."""
    try:
        from qcodes.parameters import ParamSpecBase
    except ImportError:
        from qcodes.dataset.descriptions.param_spec import ParamSpecBase
    from qcodes.dataset.descriptions.dependencies import InterDependencies_

    initialise_or_create_database_at(db_path)
    exp = load_or_create_experiment("test_exp", sample_name="test_sample")
    p_x = ParamSpecBase("x", "numeric")
    p_y = ParamSpecBase("y", "numeric")
    interdeps = InterDependencies_(dependencies={p_y: (p_x,)})

    for r in range(n_runs):
        ds = qc.new_data_set(f"run_{r + 1}")
        ds.set_interdependencies(interdeps)
        ds.mark_started()
        for i in range(10):
            ds.add_results([{p_x.name: float(i), p_y.name: float(i ** 2)}])
        ds.mark_completed()
    return db_path


class TestRecordsCounter:
    """Verify records counter shows actual data point count."""

    def test_counts_result_rows(self, tmp_path):
        """Overview should count rows from the results table."""
        import sqlite3
        from plottr.data.qcodes_db_overview import get_db_overview

        db_path = str(tmp_path / "test.db")
        _make_qcodes_db_with_runs(db_path, n_runs=3)
        overview = get_db_overview(db_path)
        conn = sqlite3.connect(db_path)

        for run_id, info in overview.items():
            row = conn.execute(
                "SELECT result_table_name FROM runs WHERE run_id=?",
                (run_id,)
            ).fetchone()
            if row and row[0]:
                try:
                    actual = conn.execute(
                        f'SELECT COUNT(*) FROM "{row[0]}"'
                    ).fetchone()[0]
                except Exception:
                    continue
                assert info['records'] == actual, \
                    f"Run {run_id}: overview={info['records']}, actual={actual}"
        conn.close()

    def test_records_from_shapes(self):
        """Shape info in run_description should produce correct count."""
        import json
        from plottr.data.qcodes_db_overview import _records_from_run_description

        desc = json.dumps({"version": 3, "shapes": {"dep1": [100, 50]}})
        assert _records_from_run_description(desc) == 5000
        assert _records_from_run_description(json.dumps({"version": 3})) == 0
        assert _records_from_run_description(None) == 0
        assert _records_from_run_description("") == 0


# -- Dataset refresh tests (inspectr incremental load) --

class TestDatasetRefresh:
    """Verify incremental DB refresh detects new runs."""

    def test_incremental_overview(self, tmp_path):
        """get_db_overview with start_run_id should find newly added runs."""
        from plottr.data.qcodes_db_overview import get_db_overview
        try:
            from qcodes.parameters import ParamSpecBase
        except ImportError:
            from qcodes.dataset.descriptions.param_spec import ParamSpecBase
        from qcodes.dataset.descriptions.dependencies import InterDependencies_

        db_path = str(tmp_path / "test.db")
        _make_qcodes_db_with_runs(db_path, n_runs=2)

        assert set(get_db_overview(db_path).keys()) == {1, 2}
        assert len(get_db_overview(db_path, start_run_id=2)) == 0

        # Add a third run
        initialise_or_create_database_at(db_path)
        exp = load_or_create_experiment("test_exp2", sample_name="s2")
        p_x = ParamSpecBase("x", "numeric")
        p_y = ParamSpecBase("y", "numeric")
        interdeps = InterDependencies_(dependencies={p_y: (p_x,)})
        ds = qc.new_data_set("run_3")
        ds.set_interdependencies(interdeps)
        ds.mark_started()
        ds.add_results([{p_x.name: 1.0, p_y.name: 2.0}])
        ds.mark_completed()

        assert 3 in get_db_overview(db_path, start_run_id=2)

    def test_inspectr_refresh(self, qtbot, tmp_path):
        """QCodesDBInspector.refreshDB should detect new runs."""
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from plottr.apps.inspectr import QCodesDBInspector
        try:
            from qcodes.parameters import ParamSpecBase
        except ImportError:
            from qcodes.dataset.descriptions.param_spec import ParamSpecBase
        from qcodes.dataset.descriptions.dependencies import InterDependencies_

        db_path = str(tmp_path / "test.db")
        _make_qcodes_db_with_runs(db_path, n_runs=1)

        inspector = QCodesDBInspector(dbPath=db_path)
        qtbot.addWidget(inspector)

        def initial_load_done():
            return inspector.dbdf is not None and inspector.dbdf.size > 0
        qtbot.waitUntil(initial_load_done, timeout=5000)
        assert list(inspector.dbdf.index) == [1]

        # Add run 2
        initialise_or_create_database_at(db_path)
        p_x = ParamSpecBase("x", "numeric")
        p_y = ParamSpecBase("y", "numeric")
        interdeps = InterDependencies_(dependencies={p_y: (p_x,)})
        ds = qc.new_data_set("run_2")
        ds.set_interdependencies(interdeps)
        ds.mark_started()
        ds.add_results([{p_x.name: 1.0, p_y.name: 2.0}])
        ds.mark_completed()

        inspector.refreshDB()
        def refresh_done():
            return (inspector.dbdf is not None and 2 in inspector.dbdf.index)
        qtbot.waitUntil(refresh_done, timeout=5000)
        assert 2 in inspector.dbdf.index
