"""Test for datadict hdf5 serialization"""

import numpy as np

from plottr.data import datadict as dd
from plottr.data import datadict_storage as dds


FN = './test_ddh5_data'


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

    dds.datadict_to_hdf5(data, './test_data', append_mode=dds.AppendMode.none)
    datafromfile = dds.datadict_from_hdf5('./test_data')

    # hdf5 saving added a few extra metas that we need to ignore when
    # comparing
    for k, v in datafromfile.data_items():
        datafromfile[k].pop('__creation_time_sec__')
        datafromfile[k].pop('__creation_time_str__')
    datafromfile.pop('__creation_time_sec__')
    datafromfile.pop('__creation_time_str__')

    assert(data == datafromfile)
