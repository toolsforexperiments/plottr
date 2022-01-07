import time
from datetime import datetime
from multiprocessing import Process

import numpy as np
import h5py
import pytest

from plottr.data.datadict import DataDict, str2dd
from plottr.data.datadict_storage import datadict_to_hdf5, datadict_from_hdf5, AppendMode, DDH5Writer, all_datadicts_from_hdf5


filebase = './testdata'
filepath = filebase + '.ddh5'


def mkdata(start, nrows, npts=1):
    shape = (nrows, npts)
    numbers = np.arange(start, start+nrows).reshape(nrows, -1) * np.ones(npts)
    return {'x': numbers, 'y': numbers**2}


def init_file():
    dataset = str2dd("x[a.u.]; y[a.u.](x)")
    dataset.add_data(**mkdata(0, 1))
    datadict_to_hdf5(dataset, filebase, append_mode=AppendMode.none)
    return dataset


def test_swmr_read():
    init_file()
    data_from_file_1 = datadict_from_hdf5(filebase)

    with h5py.File(filepath, mode='a', libver='latest') as f:
        f.swmr_mode = True
        data_from_file_2 = datadict_from_hdf5(filebase, swmr_mode=True)
    assert data_from_file_1 == data_from_file_2


def test_swmr_write_while_reading():
    dataset = init_file()
    with h5py.File(filepath, mode='r', libver='latest', swmr=True) as f:
        dataset.add_data(**mkdata(1, 2))
        with pytest.raises(OSError):
            datadict_to_hdf5(dataset, filebase, append_mode=AppendMode.new)


def run_writer(nrows=10, nreps=1, delay=0.1, npts=10000):
    dataset = str2dd("x[a.u.]; y[a.u.](x)")
    with DDH5Writer(dataset, filepath=filepath) as writer:
        for i in range(nreps):
            print(f'{datetime.now()}: adding rows {i*nrows}:{(i+1)*nrows}')
            writer.add_data(**mkdata(i*nrows, nrows, npts))
            time.sleep(delay)


def test_reading_with_writer():
    p = Process(target=run_writer, args=(10000, 1000, 0.001, 3))
    p.start()
    p.join(timeout=0)
    time.sleep(1)
    print(f'{datetime.now()}: starting monitoring')
    while p.is_alive():
        data = datadict_from_hdf5(filepath)
        print(f"{datetime.now()}: loaded {data.nrecords()} rows")
        # print(f'{datetime.now()}: loaded data: {data.shapes()}')
    # print(data)


if __name__ == '__main__':
    # test_swmr_read()
    # test_swmr_write_while_reading()
    test_reading_with_writer()



