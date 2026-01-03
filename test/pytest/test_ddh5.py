"""Test for datadict hdf5 serialization"""

from pathlib import Path
from multiprocessing import Process
import time
from shutil import rmtree

import numpy as np

from build.lib.plottr import qtsleep
from plottr.data import datadict as dd
from plottr.data import datadict_storage as dds
from plottr.node.tools import linearFlowchart


FILEPATH = Path('./test_ddh5_data.ddh5')


def _clean_from_file(datafromfile):
    for k, v in datafromfile.data_items():
        assert '__creation_time_sec__' in datafromfile[k]
        assert '__creation_time_str__' in datafromfile[k]
        datafromfile[k].pop('__creation_time_sec__')
        datafromfile[k].pop('__creation_time_str__')

        assert '__shape__' in datafromfile[k]
        datafromfile[k].pop('__shape__')

    assert '__creation_time_sec__' in datafromfile
    assert '__creation_time_str__' in datafromfile
    datafromfile.pop('__creation_time_sec__')
    datafromfile.pop('__creation_time_str__')

    # those only exist when working with the writer
    try:
        datafromfile.pop('__close_time_sec__')
        datafromfile.pop('__close_time_str__')
        datafromfile.pop('__last_change_time_sec__')
        datafromfile.pop('__last_change_time_str__')
    except KeyError:
        pass

    for axis, data in datafromfile.data_items():
        if "label" in data:
            datafromfile[axis].pop("label")

    return datafromfile

# Test the FileOpener.


def test_file_lock_creation_and_deletion():
    lock_path = FILEPATH.parent.joinpath("~" + str(FILEPATH.stem) + '.lock')
    try:
        with dds.FileOpener(FILEPATH, 'a') as f:
            assert lock_path.is_file()
            raise RuntimeError('crashing on purpose')
    except RuntimeError:
        pass
    assert not lock_path.is_file()

    FILEPATH.unlink()


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

    dds.datadict_to_hdf5(data, str(FILEPATH), append_mode=dds.AppendMode.none)
    datafromfile = dds.datadict_from_hdf5(str(FILEPATH))

    # hdf5 saving added a few extra metas that we need to ignore when
    # comparing
    datafromfile = _clean_from_file(datafromfile)
    assert(data == datafromfile)

    FILEPATH.unlink()


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

    dds.datadict_to_hdf5(data, str(FILEPATH), append_mode=dds.AppendMode.none)
    assert _clean_from_file(dds.datadict_from_hdf5(str(FILEPATH))) == data

    data.add_data(
        x=[4],
        y=np.linspace(0, 1, 5).reshape(1, -1),
        z=np.arange(5).reshape(1, -1)
    )
    assert data.validate()

    dds.datadict_to_hdf5(data, str(FILEPATH), append_mode=dds.AppendMode.new)
    assert _clean_from_file(dds.datadict_from_hdf5(str(FILEPATH))) == data

    dds.datadict_to_hdf5(data, str(FILEPATH), append_mode=dds.AppendMode.all)
    ret = _clean_from_file(dds.datadict_from_hdf5(str(FILEPATH)))
    assert ret == (data + data)

    FILEPATH.unlink()


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
    dds.datadict_to_hdf5(data, str(FILEPATH), append_mode=dds.AppendMode.new)
    assert _clean_from_file(dds.datadict_from_hdf5(str(FILEPATH))) == data

    fc = linearFlowchart(('loader', dds.DDH5Loader))
    node = fc.nodes()['loader']

    assert fc.outputValues()['dataOut'] is None

    with qtbot.waitSignal(node.loadingWorker.dataLoaded, timeout=1000) as blocker:
        node.filepath = str(FILEPATH)

    # wait a bit to make sure the output is set.
    qtsleep(0.1)

    out = fc.outputValues()['dataOut'].copy()
    out.pop('__title__')
    assert _clean_from_file(out) == data

    data.add_data(x=[3], y=np.linspace(0, 1, 5).reshape(1, -1),
                  z=np.arange(5).reshape(1, -1))
    dds.datadict_to_hdf5(data, str(FILEPATH), append_mode=dds.AppendMode.new)
    assert _clean_from_file(dds.datadict_from_hdf5(str(FILEPATH))) == data

    out = fc.outputValues()['dataOut'].copy()
    out.pop('__title__')
    assert not _clean_from_file(out) == data

    with qtbot.waitSignal(node.loadingWorker.dataLoaded, timeout=1000) as blocker:
        node.update()
    out = fc.outputValues()['dataOut'].copy()
    out.pop('__title__')
    assert _clean_from_file(out) == data

    FILEPATH.unlink()


# tests for the writer class and concurrent w/r access

def _mkdatachunk(start, nrows, npts=1):
    numbers = np.arange(start, start+nrows).reshape(nrows, -1) * np.ones(npts)  # broadcasts to (nrows, npts)
    return numbers


def test_writer():
    dataset = dd.str2dd("x[a.u.]; y[a.u.](x)")
    with dds.DDH5Writer(dataset, basedir='./TESTDATA') as writer:
        for i in range(10):
            x = _mkdatachunk(i, 1, 1)
            y = x**2
            writer.add_data(x=x, y=y)

    dataset_from_file = dds.datadict_from_hdf5(writer.filepath)
    assert '__last_change_time_sec__' in dataset_from_file
    assert '__last_change_time_str__' in dataset_from_file
    assert '__close_time_sec__' in dataset_from_file
    assert '__close_time_str__' in dataset_from_file
    assert _clean_from_file(dataset_from_file) == dataset

    rmtree('./TESTDATA')


class _Writer(Process):

    ncols = 100
    nrows_per_rep = 1000
    nreps = 100
    delay = 0.01
    filepath = './TESTDATA/data.ddh5'

    def mkdata(self):
        return _mkdatachunk(0, self.nrows_per_rep * self.nreps, self.ncols)

    def run(self):
        data = self.mkdata()
        with dds.DDH5Writer(dd.str2dd("x[W]; y[T](x)"), filepath=self.filepath) as writer:
            self.filepath = writer.filepath
            for i in range(self.nreps):
                chunk = data[i*self.nrows_per_rep:(i+1)*self.nrows_per_rep, ...]
                writer.add_data(
                    x=chunk,
                    y=chunk**2,
                )
                time.sleep(self.delay)


def test_writer_with_large_data():
    writer = _Writer()

    ref_data = writer.mkdata()
    ref_dataset = dd.DataDict(
        x=dict(values=ref_data, unit='W'),
        y=dict(values=ref_data**2, unit='T', axes=['x']),
    )
    ref_dataset['__dataset.name__'] = ''

    writer.start()
    writer.join()

    dataset_from_file = dds.datadict_from_hdf5(writer.filepath)
    assert(_clean_from_file(dataset_from_file) == ref_dataset)

    rmtree(str(Path(writer.filepath).parent))


def test_concurrent_write_and_read():
    writer = _Writer()

    ref_data = writer.mkdata()
    ref_dataset = dd.DataDict(
        x=dict(values=ref_data, unit='W'),
        y=dict(values=ref_data**2, unit='T', axes=['x']),
    )
    ref_dataset['__dataset.name__'] = ''

    writer.start()
    while writer.is_alive():
        time.sleep(2)
        data_from_file = dds.datadict_from_hdf5(writer.filepath, structure_only=True)
        assert(data_from_file.structure(include_meta=False))

    dataset_from_file = dds.datadict_from_hdf5(writer.filepath)
    assert(_clean_from_file(dataset_from_file) == ref_dataset)

    rmtree(str(Path(writer.filepath).parent))
