"""This is a test script for concurrent data write/read using a lock file.
"""

from multiprocessing import Process
import time
from datetime import datetime
from pathlib import Path

import h5py
import numpy as np


# which path to run this on.
# filepath = Path(r'Z:\swmr-testing\testdata.h5')
filepath = Path('./testdata.h5')


def mkdata(start, nrows, npts=1):
    numbers = np.arange(start, start+nrows).reshape(nrows, -1) * np.ones(npts)  # broadcasts to (nrows, npts)
    return numbers


def info(sender, msg):
    print(f'{datetime.now()} : {sender} : {msg}')


class FileOpener:

    def __init__(self, path, mode='r'):
        self.path = path
        self.mode = mode

        self.timeout = 10
        self.file = None
        self.test_delay = 0.1

    def __enter__(self):
        self.file = self.open_when_unlocked()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.file.close()

    def open_when_unlocked(self):
        t0 = time.time()
        while True:
            try:
                f = h5py.File(self.path, self.mode)
                return f
            except (OSError, PermissionError, RuntimeError):
                info(f'file opener ({self.mode})', 'waiting for file to be unlocked')

            time.sleep(self.test_delay)  # don't overwhelm the FS by very fast repeated calls.

            if time.time() - t0 > self.timeout:
                raise RuntimeError('waiting for file unlock timed out')


class Writer(Process):

    ncols = 3
    nrows_per_rep = 1000
    nreps = 100
    delay = 0.01

    def __init__(self):
        super().__init__()

    def run(self):
        data = mkdata(0, self.nrows_per_rep * self.nreps, self.ncols)
        info('writer', 'starting')
        info('writer', f"prepared data has shape {data.shape}")

        with FileOpener(str(filepath), 'w-') as fo:
            g = fo.file.create_group('my_group')

        for i in range(self.nreps):
            arr = data[i*self.nrows_per_rep:(i+1)*self.nrows_per_rep, ...]

            with FileOpener(str(filepath), 'a') as fo:
                f = fo.file
                g = f['my_group']
                if 'my_dataset' in g.keys():
                    ds = g['my_dataset']
                    shp = list(ds.shape)
                    shp[0] += arr.shape[0]
                    info('writer', f"Resizing to {tuple(shp)}")
                    ds.resize(tuple(shp))
                    info('writer', f"Adding data")
                    ds[-arr.shape[0]:, ...] = arr
                else:
                    info('writer', 'create dataset with first data')
                    ds = g.create_dataset('my_dataset', maxshape=tuple([None] + list(arr.shape)[1:]), data=arr)

            info('writer', f"... data written")
            time.sleep(self.delay)


class Reader(Process):

    delay = 0.001
    maxruntime = None

    def run(self):
        t0 = time.time()
        info('reader', 'Starting')

        while True:
            if not filepath.exists():
                continue

            with FileOpener(str(filepath), 'r') as fo:
                f = fo.file
                try:
                    ds = f['my_group/my_dataset']
                    info('reader', f'shape {ds.shape}')
                except KeyError:  # happens when we want to start reading before the first data has arrived.
                    pass

            if self.delay is not None:
                time.sleep(self.delay)

            if self.maxruntime is not None and time.time() - t0 > self.maxruntime:
                break


if __name__ == '__main__':
    filepath.unlink(missing_ok=True)

    writer = Writer()
    writer.delay = 0.001
    writer.ncols = 1000

    reader = Reader()
    reader.delay = 1

    writer.start()
    time.sleep(1)
    reader.start()

    writer.join()
    reader.kill()

    refdata = mkdata(0, writer.nrows_per_rep*writer.nreps, writer.ncols)

    with h5py.File(filepath, 'r') as f:
        ds = f['my_group/my_dataset']
        info('main', f'loaded data shape: {ds.shape}')
        assert np.array_equal(refdata, ds[:])






