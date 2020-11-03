import pytest
import numpy as np

import qcodes as qc
from qcodes import load_or_create_experiment, initialise_or_create_database_at

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


@pytest.fixture
def dataset_with_shape(empty_db_path):
    """Fixture of a database file a shaped and an unshapeed dataset"""
    exp = load_or_create_experiment('get_runs_from_db', sample_name='qubit')
    m1 = qc.Measurement(exp=exp)

    m1.register_custom_parameter('x', unit='cm')
    m1.register_custom_parameter('y')
    for n in range(2):
        m1.register_custom_parameter(f'z_{n}', setpoints=['x', 'y'])

    shapes = (10, 5)
    m1.set_shapes({'z_0': shapes})

    with m1.run() as datasaver:
        for x in np.linspace(0, 1, shapes[0]):
            for y in np.linspace(4, 6, shapes[1]):
                datasaver.add_result(('x', x),
                                     ('y', y),
                                     ('z_0', x+y),
                                     ('z_1', x**2+y))
        dataset = datasaver.dataset

    yield dataset

    dataset.conn.close()
    exp.conn.close()

