"""This is a test script for swmr data write/read.
While this complies with the HDF5 instructions, it causes issues on some Windows machines.
Also, it does seem to cause issues with network drives (this is documented by HDF5).
"""

from multiprocessing import Process
import time
from datetime import datetime
from pathlib import Path

import h5py
import numpy as np


# which path to run this on.
filepath = Path(r'Z:\swmr-testing\testdata.h5')
filepath = Path('./testdata.h5')


def mkdata(start, nrows, npts=1):
    numbers = np.arange(start, start+nrows).reshape(nrows, -1) * np.ones(npts)  # broadcasts to (nrows, npts)
    return numbers


def info(sender, msg):
    print(f'{datetime.now()} : {sender} : {msg}')


class Writer(Process):

    ncols = 3
    nrows_per_rep = 1000
    nreps = 100
    delay = 0.01

    def __init__(self):
        super().__init__()

    def run(self):
        filepath.unlink(missing_ok=True)
        arr = mkdata(0, self.nrows_per_rep, self.ncols)
        info('writer', 'starting to write data')

        with h5py.File(str(filepath), 'a', libver='latest') as f:
            g = f.create_group('my_group')
            ds = g.create_dataset('my_dataset', maxshape=(None, self.ncols), data=arr)
            f.swmr_mode = True

            for i in range(self.nreps):
                shp = list(ds.shape)
                arr = mkdata((i+1)*self.nrows_per_rep, self.nrows_per_rep, self.ncols)
                shp[0] += arr.shape[0]
                info('writer', f"Resizing to {tuple(shp)}")
                ds.resize(tuple(shp))
                info('writer', f"Adding data")
                ds[-arr.shape[0]:, ...] = arr
                ds.flush()
                info('writer', f"...Flushed")
                time.sleep(self.delay)


class Reader(Process):

    delay = 0.001
    maxruntime = None
    close_always = True

    def run(self):
        t0 = time.time()
        info('reader', 'starting to read data')

        if not self.close_always:
            f = h5py.File(str(filepath), 'r', libver='latest', swmr=True)
            assert f.swmr_mode

        while True:
            if self.close_always:
                with h5py.File(str(filepath), 'r', libver='latest', swmr=True) as f:
                    assert f.swmr_mode
                    ds = f['my_group/my_dataset']
                    ds.refresh()
                    info('reader', f'shape {ds.shape}')
            else:
                ds = f['my_group/my_dataset']
                ds.refresh()
                info('reader', f'shape {ds.shape}')

            if self.delay is not None:
                time.sleep(self.delay)

            if self.maxruntime is not None and time.time() - t0 > self.maxruntime:
                break

        if not self.close_always:
            f.close()


if __name__ == '__main__':
    writer = Writer()
    reader = Reader()
    reader.maxruntime = None
    reader.delay = 0.01
    reader.close_always = True

    writer.start()
    time.sleep(0.5)
    reader.start()

    writer.join()
    reader.kill()

    with h5py.File(filepath, 'r', libver='latest', swmr=True) as f:
        ds = f['my_group/my_dataset']
        info('main', f'Retrieved shape {ds.shape}')






