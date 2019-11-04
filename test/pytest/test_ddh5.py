"""Test for datadict hdf5 serialization"""

import numpy as np

from plottr.data import datadict as dd
from plottr.data import datadict_storage as dds
from plottr.node.tools import linearFlowchart

FN = './test_ddh5_data.ddh5'


def _clean_from_file(datafromfile):
    for k, v in datafromfile.data_items():
        assert '__creation_time_sec__' in datafromfile[k]
        assert '__creation_time_str__' in datafromfile[k]
        datafromfile[k].pop('__creation_time_sec__')
        datafromfile[k].pop('__creation_time_str__')

    assert '__creation_time_sec__' in datafromfile
    assert '__creation_time_str__' in datafromfile
    datafromfile.pop('__creation_time_sec__')
    datafromfile.pop('__creation_time_str__')

    return datafromfile


def test_basic_storage_and_retrieval():
    x = np.arange(3)
    y = np.repeat(np.linspace(0, 1, 5).reshape(1, -1), 3, 0)
    z = np.arange(y.size).reshape(y.shape)

    data = dd.DataDict(
        x=dict(values=x, unit='A',
               __info__='careful!',
               __moreinfo__='more words in here'),
        y=dict(values=y, unit='B'),
        z=dict(values=z, axes=['x', 'y'], unit='C'),
        __desc__='some description',
    )
    assert data.validate()

    dds.datadict_to_hdf5(data, FN, append_mode=dds.AppendMode.none)
    datafromfile = dds.datadict_from_hdf5(FN)

    # hdf5 saving added a few extra metas that we need to ignore when
    # comparing
    datafromfile = _clean_from_file(datafromfile)
    assert(data == datafromfile)


def test_appending():
    x = np.arange(3)
    y = np.repeat(np.linspace(0, 1, 5).reshape(1, -1), 3, 0)
    z = np.arange(y.size).reshape(y.shape)

    data = dd.DataDict(
        x=dict(values=x, unit='A',
               __info__='careful!',
               __moreinfo__='more words in here'),
        y=dict(values=y, unit='B'),
        z=dict(values=z, axes=['x', 'y'], unit='C'),
        __desc__='some description',
    )
    assert data.validate()

    dds.datadict_to_hdf5(data, FN, append_mode=dds.AppendMode.none)
    assert _clean_from_file(dds.datadict_from_hdf5(FN)) == data

    data.add_data(
        x=[4],
        y=np.linspace(0, 1, 5).reshape(1, -1),
        z=np.arange(5).reshape(1, -1)
    )
    assert data.validate()

    dds.datadict_to_hdf5(data, FN, append_mode=dds.AppendMode.new)
    assert _clean_from_file(dds.datadict_from_hdf5(FN)) == data

    dds.datadict_to_hdf5(data, FN, append_mode=dds.AppendMode.all)
    ret = _clean_from_file(dds.datadict_from_hdf5(FN))
    assert ret == (data + data)


def test_loader_node(qtbot):
    dds.DDH5Loader.useUi = False

    x = np.arange(3)
    y = np.repeat(np.linspace(0, 1, 5).reshape(1, -1), 3, 0)
    z = np.arange(y.size).reshape(y.shape)

    data = dd.DataDict(
        x=dict(values=x, unit='A',
               __info__='careful!',
               __moreinfo__='more words in here'),
        y=dict(values=y, unit='B'),
        z=dict(values=z, axes=['x', 'y'], unit='C'),
        __desc__='some description',
    )
    assert data.validate()
    dds.datadict_to_hdf5(data, FN, append_mode=dds.AppendMode.new)
    assert _clean_from_file(dds.datadict_from_hdf5(FN)) == data

    fc = linearFlowchart(('loader', dds.DDH5Loader))
    node = fc.nodes()['loader']

    assert fc.outputValues()['dataOut'] is None

    node.filepath = FN
    out = fc.outputValues()['dataOut'].copy()
    out.pop('__title__')
    assert _clean_from_file(out) == data

    data.add_data(x=[3], y=np.linspace(0, 1, 5).reshape(1, -1),
                  z=np.arange(5).reshape(1,- 1))
    dds.datadict_to_hdf5(data, FN, append_mode=dds.AppendMode.new)
    assert _clean_from_file(dds.datadict_from_hdf5(FN)) == data

    out = fc.outputValues()['dataOut'].copy()
    out.pop('__title__')
    assert _clean_from_file(out) != data

    node.update()
    out = fc.outputValues()['dataOut'].copy()
    out.pop('__title__')
    assert _clean_from_file(out) == data
