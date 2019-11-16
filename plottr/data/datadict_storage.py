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
from enum import Enum
from typing import Any, Union

import numpy as np
import h5py

from plottr import QtGui, Signal, Slot

from ..node import (
    Node, NodeWidget, updateOption, updateGuiFromNode,
    emitGuiUpdate,
)

from .datadict import DataDict, is_meta_key

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'

DATAFILEXT = '.ddh5'

AppendMode = Enum('AppendMode', names='new all none')


def h5ify(obj: Any) -> Any:
    """
    Convert an object into something that we can assing to an HDF5 attribute.

    Performs the following conversions:
    - list/array of strings -> numpy chararray of unicode type

    :param obj: input object
    :return: object, converted if necessary
    """
    if type(obj) == list:
        obj = np.array(obj)

    if type(obj) == np.ndarray and obj.dtype == np.dtype('<U1'):
        return np.chararray.encode(obj, encoding='utf8')

    return obj


def deh5ify(obj: Any) -> Any:
    """Convert slightly mangled types back to more handy ones."""
    if type(obj) == bytes:
        return obj.decode()

    if type(obj) == np.ndarray and obj.dtype == np.dtype('S1'):
        return np.chararray.decode(obj)

    return obj


def set_attr(h5obj: Any, name: str, val: Any):
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
                      prefix: str = '__', suffix: str = '__'):
    """Add current time information to the given HDF5 object."""

    t = time.localtime()
    tsec = time.mktime(t)
    tstr = time.strftime("%Y-%m-%d %H:%M:%S", t)

    set_attr(h5obj, prefix + name + '_time_sec' + suffix, tsec)
    set_attr(h5obj, prefix + name + '_time_str' + suffix, tstr)


def init_file(filepath: str):
    """Init a new file.

    create the folder structure, if necessary, and the file.

    :param filepath: full file path
    """
    folder, path = os.path.split(filepath)
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

    if not os.path.exists(filepath):
        with h5py.File(filepath, 'w', libver='latest') as _:
            pass


def datadict_to_hdf5(datadict: DataDict, basepath: str,
                     groupname: str = 'data',
                     append_mode: AppendMode = AppendMode.new,
                     swmr_mode: bool = True):
    """Write a DataDict to DDH5

    Note: meta data is only written during initial writing of the dataset.
    If we're appending to existing datasets, we're not setting meta
    data anymore.

    :param datadict: datadict to write to disk.
    :param basepath: path of the file, without extension.
    :param groupname: name of the top level group to store the data in
    :param append_mode:
        - `AppendMode.none` : delete and re-create group
        - `AppendMode.new` : append rows in the datadict that exceed
            the number of existing rows in the dataset already stored.
            Note: we're not checking for content, only length!
        - `AppendMode.all` : append all data in datadict to file data sets
    :param swmr_mode: use HDF5 SWMR mode on the file when appending.
    """

    if len(basepath) > len(DATAFILEXT) and \
            basepath[-len(DATAFILEXT):] == DATAFILEXT:
        filepath = basepath
        basepath = basepath[:-len(DATAFILEXT)]
    else:
        filepath = basepath + DATAFILEXT

    if not os.path.exists(filepath):
        init_file(filepath)

    with h5py.File(filepath, 'a', libver='latest') as f:
        if append_mode == AppendMode.none and groupname in f:
            del f[groupname]
            f.flush()
            grp = f.create_group(groupname)
            add_cur_time_attr(grp)

        elif groupname not in f:
            grp = f.create_group(groupname)
            add_cur_time_attr(grp)

        else:
            grp = f[groupname]

        # if we want to use swmr, we need to make sure that we're not
        # creating any more objects (see hdf5 docs).
        allexist = True
        for k, v in datadict.data_items():
            if k not in grp:
                allexist = False

        # add top-level meta data.
        if not allexist:
            for k, v in datadict.meta_items(clean_keys=False):
                set_attr(grp, k, v)

        if allexist and swmr_mode:
            f.swmr_mode = True

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

                if v.get('axes', []) != []:
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

        f.flush()


def datadict_from_hdf5(basepath: str, groupname: str = 'data',
                       startidx: Union[int, None] = None,
                       stopidx: Union[int, None] = None,
                       structure_only: bool = False,
                       ignore_unequal_lengths: bool = True,
                       swmr_mode: bool = True) -> DataDict:
    """Load a DataDict from file.

    :param basepath: full filepath without the file extension
    :param groupname: name of hdf5 group
    :param startidx: start row
    :param stopidx: end row + 1
    :param structure_only: if `True`, don't load the data values
    :param ignore_unequal_lengths: if `True`, don't fail when the rows have
        unequal length; will return the longest consistent DataDict possible.
    :param swmr_mode: if `True`, open HDF5 file in SWMR mode.
    :return: validated DataDict.
    """

    if len(basepath) > len(DATAFILEXT) and \
            basepath[-len(DATAFILEXT):] == DATAFILEXT:
        filepath = basepath
        basepath = basepath[:-len(DATAFILEXT)]
    else:
        filepath = basepath + DATAFILEXT

    if not os.path.exists(filepath):
        raise ValueError("Specified file does not exist.")

    if startidx is None:
        startidx = 0

    res = {}
    with h5py.File(filepath, 'r', libver='latest', swmr=swmr_mode) as f:
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
            try:
                ds = grp[k]
                entry = dict(values=np.array([]), )

                if 'axes' in ds.attrs:
                    entry['axes'] = deh5ify(ds.attrs['axes']).tolist()
                else:
                    entry['axes'] = []

                if 'unit' in ds.attrs:
                    entry['unit'] = deh5ify(ds.attrs['unit'])

                if not structure_only:
                    entry['values'] = ds[startidx:stopidx]

                # and now the meta data
                for attr in ds.attrs:
                    if is_meta_key(attr):
                        entry[attr] = deh5ify(ds.attrs[attr])

            except:
                raise

            res[k] = entry

    dd = DataDict(**res)
    dd.validate()
    return dd


# Node for monitoring #

class DDH5LoaderWidget(NodeWidget):

    def __init__(self, node: Node = None):
        super().__init__(node=node)

        self.fileinput = QtGui.QLineEdit()
        self.groupinput = QtGui.QLineEdit('data')
        self.reload = QtGui.QPushButton('Reload')

        self.optSetters = {
            'filepath': self.fileinput.setText,
            'groupname': self.groupinput.setText,
        }
        self.optGetters = {
            'filepath': self.fileinput.text,
            'groupname': self.groupinput.text,
        }

        flayout = QtGui.QFormLayout()
        flayout.addRow('File path:', self.fileinput)
        flayout.addRow('Group:', self.groupinput)

        vlayout = QtGui.QVBoxLayout()
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

    def __init__(self, name: str):
        self._filepath = None
        self._groupname = None

        super().__init__(name)

        self.groupname = 'data'
        self.nLoadedRecords = 0

    # Properties #

    @property
    def filepath(self):
        return self._filepath

    @filepath.setter
    @updateOption('filepath')
    def filepath(self, val):
        self._filepath = val

    @property
    def groupname(self):
        return self._groupname

    @groupname.setter
    @updateOption('groupname')
    def groupname(self, val):
        self._groupname = val

    # Data processing #

    def process(self, dataIn=None):
        if self._filepath is None or self._groupname is None:
            return None
        if not os.path.exists(self._filepath):
            return None

        data = datadict_from_hdf5(self._filepath, groupname=self.groupname)
        title = f"{self.filepath}"
        data.add_meta('title', title)
        self.nLoadedRecords = data.nrecords()

        if super().process(dataIn=data) is None:
            return None

        return dict(dataOut=data)


class DDH5Writer(object):

    def __init__(self, basedir, datadict):
        self.basedir = basedir
        self.datadict = datadict
        self.basepath = None
        self.inserted_rows = 0

    def __enter__(self):
        folder = os.path.join(
            self.basedir,
            time.strftime("%Y-%m-%d"),
        )
        os.makedirs(folder, exist_ok=True)
        filebase = time.strftime("%Y-%m-%d_")

        files = os.listdir(folder)
        datafiles = [f for f in files if
                     ((os.path.splitext(f)[1] == DATAFILEXT)
                      and (f[:len(filebase)] == filebase))]

        if len(datafiles) > 0:
            datafiles.sort()
            idx = int(os.path.splitext(datafiles[-1])[0][-3:]) + 1
            suffix = f"{idx:03}"
        else:
            suffix = '001'

        self.basepath = os.path.join(folder, filebase + suffix)
        print('Datafile: ', self.basepath)

        if self.datadict.nrecords() > 0:
            datadict_to_hdf5(self.datadict, self.basepath,
                             append_mode=AppendMode.none)
            self.inserted_rows = self.datadict.nrecords()

        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        pass

    def add_data(self, **kw):
        self.datadict.add_data(**kw)

        if self.inserted_rows > 0:
            mode = AppendMode.new
        else:
            mode = AppendMode.none

        if self.datadict.nrecords() > 0:
            datadict_to_hdf5(self.datadict, self.basepath,
                             append_mode=mode)
