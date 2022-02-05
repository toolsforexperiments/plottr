"""plottr.data.datadict_storage

Provides file-storage tools for the DataDict class.

Description of the HDF5 storage format
======================================

We use a simple mapping from DataDict to the HDF5 file. Within the file,
a single DataDict is stored in a (top-level) group of the file.
The data fields are datasets within that group.

Global meta data of the DataDict are attributes of the group; field meta data
are attributes of the dataset (incl., the `unit` and `axes` values). The meta
data keys are given exactly like in the DataDict, i.e., incl the double
underscore pre- and suffix.
"""
import os
import time
import datetime
import uuid
from enum import Enum
from typing import Any, Union, Optional, Dict, Type, Collection
from types import TracebackType
from pathlib import Path

import numpy as np
import h5py

from plottr import QtGui, Signal, Slot, QtWidgets, QtCore

from ..node import (
    Node, NodeWidget, updateOption, updateGuiFromNode,
    emitGuiUpdate,
)

from .datadict import DataDict, is_meta_key, DataDictBase

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'

DATAFILEXT = 'ddh5'
TIMESTRFORMAT = "%Y-%m-%d %H:%M:%S"


# FIXME: need correct handling of dtypes and list/array conversion


class AppendMode(Enum):
    """How/Whether to append data to existing data."""
    #: data that is additional compared to already existing data is appended
    new = 0
    #: all data is appended to existing data
    all = 1
    #: data is overwritten
    none = 2


# tools for working on hdf5 objects

def h5ify(obj: Any) -> Any:
    """
    Convert an object into something that we can assign to an HDF5 attribute.

    Performs the following conversions:
    - list/array of strings -> numpy chararray of unicode type

    :param obj: input object
    :return: object, converted if necessary
    """
    if isinstance(obj, list):
        all_string = True
        for elt in obj:
            if not isinstance(elt, str):
                all_string = False
                break
        if not all_string:
            obj = np.array(obj)

    if type(obj) == np.ndarray and obj.dtype.kind == 'U':
        return np.char.encode(obj, encoding='utf8')

    return obj


def deh5ify(obj: Any) -> Any:
    """Convert slightly mangled types back to more handy ones."""
    if type(obj) == bytes:
        return obj.decode()

    if type(obj) == np.ndarray and obj.dtype.kind == 'S':
        return np.char.decode(obj)

    return obj


def set_attr(h5obj: Any, name: str, val: Any) -> None:
    """Set attribute `name` of object `h5obj` to `val`

    Use :func:`h5ify` to convert the object, then try to set the attribute
    to the returned value. If that does not succeed due to a HDF5 typing
    restriction, set the attribute to the string representation of the value.
    """
    try:
        h5obj.attrs[name] = h5ify(val)
    except TypeError:
        newval = str(val)
        h5obj.attrs[name] = h5ify(newval)


def add_cur_time_attr(h5obj: Any, name: str = 'creation',
                      prefix: str = '__', suffix: str = '__') -> None:
    """Add current time information to the given HDF5 object."""

    t = time.localtime()
    tsec = time.mktime(t)
    tstr = time.strftime(TIMESTRFORMAT, t)

    set_attr(h5obj, prefix + name + '_time_sec' + suffix, tsec)
    set_attr(h5obj, prefix + name + '_time_str' + suffix, tstr)


# elementary reading/writing

def _data_file_path(file: Union[str, Path], init_directory: bool = False) -> Path:
    """Get the full filepath of the data file.
    If `init_directory` is True, then create the parent directory."""

    if isinstance(file, str):
        path = Path(file)
    else:
        path = file
    path = path.resolve()
    if path.suffix != f'.{DATAFILEXT}':
        path = Path(path.parent, path.stem + f'.{DATAFILEXT}')
    if init_directory:
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def datadict_to_hdf5(datadict: DataDict,
                     path: str,
                     groupname: str = 'data',
                     append_mode: AppendMode = AppendMode.new) -> None:
    """Write a DataDict to DDH5

    Note: meta data is only written during initial writing of the dataset.
    If we're appending to existing datasets, we're not setting meta
    data anymore.

    :param datadict: datadict to write to disk.
    :param path: path of the file (extension may be omitted)
    :param groupname: name of the top level group to store the data in
    :param append_mode:
        - `AppendMode.none` : delete and re-create group
        - `AppendMode.new` : append rows in the datadict that exceed
            the number of existing rows in the dataset already stored.
            Note: we're not checking for content, only length!
        - `AppendMode.all` : append all data in datadict to file data sets
    """
    filepath = _data_file_path(path, True)
    if not filepath.exists():
        append_mode = AppendMode.none

    with FileOpener(filepath, 'a') as f:
        if append_mode is AppendMode.none:
            init_file(f, groupname)
        assert groupname in f
        grp = f[groupname]

        # add top-level meta data.
        for k, v in datadict.meta_items(clean_keys=False):
            set_attr(grp, k, v)

        for k, v in datadict.data_items():
            data = v['values']
            shp = data.shape
            nrows = shp[0]

            # create new dataset, add axes and unit metadata
            if k not in grp:
                maxshp = tuple([None] + list(shp[1:]))
                ds = grp.create_dataset(k, maxshape=maxshp, data=data)

                # add meta data
                add_cur_time_attr(ds)

                if v.get('axes', []):
                    set_attr(ds, 'axes', v['axes'])
                if v.get('unit', "") != "":
                    set_attr(ds, 'unit', v['unit'])

                for kk, vv in datadict.meta_items(k, clean_keys=False):
                    set_attr(ds, kk, vv)
                ds.flush()

            # if the dataset already exits, append data according to
            # chosen append mode.
            else:
                ds = grp[k]
                dslen = ds.shape[0]

                if append_mode == AppendMode.new:
                    newshp = tuple([nrows] + list(shp[1:]))
                    ds.resize(newshp)
                    ds[dslen:] = data[dslen:]
                elif append_mode == AppendMode.all:
                    newshp = tuple([dslen + nrows] + list(shp[1:]))
                    ds.resize(newshp)
                    ds[dslen:] = data[:]
                ds.flush()


def init_file(f: h5py.File,
              groupname: str = 'data') -> None:

    if groupname in f:
        del f[groupname]
        f.flush()
        grp = f.create_group(groupname)
        add_cur_time_attr(grp)
        f.flush()
    else:
        grp = f.create_group(groupname)
        add_cur_time_attr(grp)
        f.flush()


def datadict_from_hdf5(path: str,
                       groupname: str = 'data',
                       startidx: Union[int, None] = None,
                       stopidx: Union[int, None] = None,
                       structure_only: bool = False,
                       ignore_unequal_lengths: bool = True) -> DataDict:
    """Load a DataDict from file.

    :param path: full filepath without the file extension
    :param groupname: name of hdf5 group
    :param startidx: start row
    :param stopidx: end row + 1
    :param structure_only: if `True`, don't load the data values
    :param ignore_unequal_lengths: if `True`, don't fail when the rows have
        unequal length; will return the longest consistent DataDict possible.
    :return: validated DataDict.
    """
    filepath = _data_file_path(path)
    if not filepath.exists():
        raise ValueError("Specified file does not exist.")

    if startidx is None:
        startidx = 0

    res = {}
    with FileOpener(filepath, 'r') as f:
        if groupname not in f:
            raise ValueError('Group does not exist.')

        grp = f[groupname]
        keys = list(grp.keys())
        lens = [len(grp[k][:]) for k in keys]

        if len(set(lens)) > 1:
            if not ignore_unequal_lengths:
                raise RuntimeError('Unequal lengths in the datasets.')

            if stopidx is None or stopidx > min(lens):
                stopidx = min(lens)
        else:
            if stopidx is None or stopidx > lens[0]:
                stopidx = lens[0]

        for attr in grp.attrs:
            if is_meta_key(attr):
                res[attr] = deh5ify(grp.attrs[attr])

        for k in keys:
            ds = grp[k]
            entry: Dict[str, Union[Collection[Any], np.ndarray]] = dict(values=np.array([]), )

            if 'axes' in ds.attrs:
                entry['axes'] = deh5ify(ds.attrs['axes']).tolist()
            else:
                entry['axes'] = []

            if 'unit' in ds.attrs:
                entry['unit'] = deh5ify(ds.attrs['unit'])

            if not structure_only:
                entry['values'] = ds[startidx:stopidx]

            entry['__shape__'] = ds[:].shape

            # and now the meta data
            for attr in ds.attrs:
                if is_meta_key(attr):
                    _val = deh5ify(ds.attrs[attr])
                    entry[attr] = deh5ify(ds.attrs[attr])

            res[k] = entry

    dd = DataDict(**res)
    dd.validate()
    return dd


def all_datadicts_from_hdf5(path: str, **kwargs: Any) -> Dict[str, Any]:
    filepath = _data_file_path(path)
    if not os.path.exists(filepath):
        raise ValueError("Specified file does not exist.")

    ret = {}
    with FileOpener(filepath, 'r') as f:
        keys = [k for k in f.keys()]
    for k in keys:
        ret[k] = datadict_from_hdf5(path=path, groupname=k, **kwargs)
    return ret


# File access with locking

class FileOpener:
    """Class for opening files while respecting file system locks."""

    def __init__(self, path: Path,
                 mode: str = 'r',
                 timeout: float = 10.,
                 test_delay: float = 0.1):
        self.path = path

        if mode not in ['r', 'w', 'w-', 'a']:
            raise ValueError("Only 'r', 'w', 'w-', 'a' modes are supported.")
        self.mode = mode
        self.timeout = timeout
        self.test_delay = test_delay

        self.file: Optional[h5py.File] = None

    def __enter__(self) -> h5py.File:
        self.file = self.open_when_unlocked()
        return self.file

    def __exit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 exc_traceback: Optional[TracebackType]) -> None:
        assert self.file is not None
        self.file.close()

    def open_when_unlocked(self) -> h5py.File:
        t0 = time.time()
        while True:
            try:
                f = h5py.File(str(self.path), self.mode)
                return f
            except (OSError, PermissionError, RuntimeError):
                pass
            time.sleep(self.test_delay)  # don't overwhelm the FS by very fast repeated calls.
            if time.time() - t0 > self.timeout:
                raise RuntimeError('Waiting for file unlock timeout')


# Node for monitoring #

class DDH5LoaderWidget(NodeWidget):

    def __init__(self, node: Node):
        super().__init__(node=node)
        assert self.node is not None

        self.fileinput = QtWidgets.QLineEdit()
        self.groupinput = QtWidgets.QLineEdit('data')
        self.reload = QtWidgets.QPushButton('Reload')

        self.optSetters = {
            'filepath': self.fileinput.setText,
            'groupname': self.groupinput.setText,
        }
        self.optGetters = {
            'filepath': self.fileinput.text,
            'groupname': self.groupinput.text,
        }

        flayout = QtWidgets.QFormLayout()
        flayout.addRow('File path:', self.fileinput)
        flayout.addRow('Group:', self.groupinput)

        vlayout = QtWidgets.QVBoxLayout()
        vlayout.addLayout(flayout)
        vlayout.addWidget(self.reload)

        self.setLayout(vlayout)

        self.fileinput.textEdited.connect(
            lambda x: self.signalOption('filepath')
        )
        self.groupinput.textEdited.connect(
            lambda x: self.signalOption('groupname')
        )
        self.reload.pressed.connect(self.node.update)


class DDH5Loader(Node):

    nodeName = 'DDH5Loader'
    uiClass = DDH5LoaderWidget
    useUi = True

    setProcessOptions = Signal(str, str)

    def __init__(self, name: str):
        self._filepath: Optional[str] = None
        self._groupname: str = 'data'

        super().__init__(name)

        self.nLoadedRecords = 0

        self.loadingThread = QtCore.QThread()
        self.loadingWorker = _Loader(self.filepath, self.groupname)
        self.loadingWorker.moveToThread(self.loadingThread)
        self.loadingThread.started.connect(self.loadingWorker.loadData)
        self.loadingWorker.dataLoaded.connect(self.onThreadComplete)
        self.loadingWorker.dataLoaded.connect(lambda x: self.loadingThread.quit())
        self.setProcessOptions.connect(self.loadingWorker.setPathAndGroup)

    @property
    def filepath(self) -> Optional[str]:
        return self._filepath

    @filepath.setter  # type: ignore[misc]
    @updateOption('filepath')
    def filepath(self, val: str) -> None:
        self._filepath = val

    @property
    def groupname(self) -> str:
        return self._groupname

    @groupname.setter  # type: ignore[misc]
    @updateOption('groupname')
    def groupname(self, val: str) -> None:
        self._groupname = val

    # Data processing #

    def process(self, dataIn: Optional[DataDictBase] = None) -> Optional[Dict[str, Any]]:

        # TODO: maybe needs an optional way to read only new data from file? -- can make that an option

        # this is the flow when process is called due to some trigger
        if self._filepath is None or self._groupname is None:
            return None
        if not os.path.exists(self._filepath):
            return None

        if not self.loadingThread.isRunning():
            self.loadingWorker.setPathAndGroup(self.filepath, self.groupname)
            self.loadingThread.start()
        return None

    @Slot(object)
    def onThreadComplete(self, data: Optional[DataDict]) -> None:
        if data is None:
            return None

        title = f"{self.filepath}"
        data.add_meta('title', title)
        nrecords = data.nrecords()
        assert nrecords is not None
        self.nLoadedRecords = nrecords
        self.setOutput(dataOut=data)

        # this makes sure that we analyze the data and emit signals for changes
        super().process(dataIn=data)


class _Loader(QtCore.QObject):

    nRetries = 5
    retryDelay = 0.01

    dataLoaded = Signal(object)

    def __init__(self, filepath: Optional[str], groupname: Optional[str]) -> None:
        super().__init__()
        self.filepath = filepath
        self.groupname = groupname

    def setPathAndGroup(self, filepath: Optional[str], groupname: Optional[str]) -> None:
        self.filepath = filepath
        self.groupname = groupname

    def loadData(self) -> bool:
        if self.filepath is None or self.groupname is None:
            self.dataLoaded.emit(None)
            return True

        data = datadict_from_hdf5(self.filepath, groupname=self.groupname)
        self.dataLoaded.emit(data)
        return True


class DDH5Writer(object):
    """Context manager for writing data to DDH5.
    Based on typical needs in taking data in an experimental physics lab.

    Example usage::
        >>> data = DataDict(
        ...     x = dict(unit='x_unit'),
        ...     y = dict(unit='y_unit', axes=['x'])
        ... )
        ... with DDH5Writer('./data/', data, name='Test') as writer:
        ...     for x in range(10):
        ...         writer.add_data(x=x, y=x**2)
        Data location: ./data/2020-06-05/2020-06-05T102345_d11541ca-Test/data.ddh5

    :param basedir: The root directory in which data is stored.
        :meth:`.create_file_structure` is creating the structure inside this root and
        determines the file name of the data. The default structure implemented here is
        ``<root>/YYYY-MM-DD/YYYY-mm-dd_THHMMSS_<ID>-<name>/<filename>.ddh5``,
        where <ID> is a short identifier string and <name> is the value of parameter `name`.
        To change this, re-implement :meth:`.data_folder` and/or
        :meth:`.create_file_structure`.
    :param datadict: initial data object. Must contain at least the structure of the
        data to be able to use :meth:`add_data` to add data.
    :param groupname: name of the top-level group in the file container. An existing
        group of that name will be deleted.
    :param name: name of this dataset. Used in path/file creation and added as meta data.
    :param filename: filename to use. defaults to 'data.ddh5'.
    """

    # TODO: need an operation mode for not keeping data in memory.
    # TODO: a mode for working with pre-allocated data

    def __init__(self,
                 datadict: DataDict,
                 basedir: str = '.',
                 groupname: str = 'data',
                 name: Optional[str] = None,
                 filename: str = 'data',
                 filepath: Optional[str] = None):
        """Constructor for :class:`.DDH5Writer`"""

        self.basedir = Path(basedir)
        self.datadict = datadict
        self.inserted_rows = 0

        if name is None:
            name = ''
        self.name = name

        self.groupname = groupname
        self.filename = Path(filename)

        self.filepath: Optional[Path] = None
        if filepath is not None:
            self.filepath = Path(filepath)

        self.datadict.add_meta('dataset.name', name)

    def __enter__(self) -> "DDH5Writer":
        if self.filepath is None:
            self.filepath = _data_file_path(self.data_file_path(), True)
        print('Data location: ', self.filepath)

        nrecords: Optional[int] = self.datadict.nrecords()
        if nrecords is not None and nrecords > 0:
            datadict_to_hdf5(self.datadict,
                             str(self.filepath),
                             groupname=self.groupname,
                             append_mode=AppendMode.none)
            self.inserted_rows = nrecords
        return self

    def __exit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 exc_traceback: Optional[TracebackType]) -> None:
        assert self.filepath is not None
        with FileOpener(self.filepath, 'a') as f:
            add_cur_time_attr(f[self.groupname], name='close')

    def data_folder(self) -> Path:
        """Return the folder, relative to the data root path, in which data will
        be saved.

        Default format:
        ``<basedir>/YYYY-MM-DD/YYYY-mm-ddTHHMMSS_<ID>-<name>``.
        In this implementation we use the first 8 characters of a UUID as ID.
        """
        ID = str(uuid.uuid1()).split('-')[0]
        parent = f"{datetime.datetime.now().replace(microsecond=0).isoformat().replace(':', '')}_{ID}"
        if self.name:
            parent += f'-{self.name}'
        path = Path(time.strftime("%Y-%m-%d"), parent)
        return path

    def data_file_path(self) -> Path:
        """Determine the filepath of the data file.

        :returns: the filepath of the data file.
        """
        data_folder_path = Path(self.basedir, self.data_folder())
        appendix = ''
        idx = 2
        while data_folder_path.exists():
            appendix = f'-{idx}'
            data_folder_path = Path(self.basedir,
                                    str(self.data_folder())+appendix)
            idx += 1

        return Path(data_folder_path, self.filename)

    def add_data(self, **kwargs: Any) -> None:
        """Add data to the file (and the internal `DataDict`).

        Requires one keyword argument per data field in the `DataDict`, with
        the key being the name, and value the data to add. It is required that
        all added data has the same number of 'rows', i.e., the most outer dimension
        has to match for data to be inserted faithfully.
        If some data is scalar and others are not, then the data should be reshaped
        to (1, ) for the scalar data, and (1, ...) for the others; in other words,
        an outer dimension with length 1 is added for all.
        """
        self.datadict.add_data(**kwargs)

        if self.inserted_rows > 0:
            mode = AppendMode.new
        else:
            mode = AppendMode.none
        nrecords = self.datadict.nrecords()
        if nrecords is not None and nrecords > 0:
            datadict_to_hdf5(self.datadict, str(self.filepath),
                             groupname=self.groupname,
                             append_mode=mode)

            assert self.filepath is not None
            with FileOpener(self.filepath, 'a') as f:
                add_cur_time_attr(f, name='last_change')
                add_cur_time_attr(f[self.groupname], name='last_change')
