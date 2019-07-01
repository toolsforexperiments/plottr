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

from typing import Any, Union

import numpy as np
import h5py

from .datadict import DataDict, is_meta_key


DATAFILEXT = '.dd.h5'


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

    set_attr(h5obj, prefix+name+'_time_sec'+suffix, tsec)
    set_attr(h5obj, prefix+name+'_time_str'+suffix, tstr)


def init_file(filepath: str, groupname: str, reset: bool = True):
    """Init a new file.

    create the folder structure, if necessary, and create the group `groupname`
    at the top level. Will not delete content in the file except if a group
    of the specified name already exists.

    :param filepath: full file path
    :param groupname: top level group name
    :param reset: if True, will delete group if it already exists in the file.
    """
    folder, path = os.path.split(filepath)
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

    if not os.path.exists(filepath):
        with h5py.File(filepath, 'w', libver='latest') as _:
            pass

    with h5py.File(filepath, 'a', libver='latest') as f:
        if reset and groupname in f:
            del f[groupname]
            f.flush()

        if groupname not in f:
            g = f.create_group(groupname)
            add_cur_time_attr(g)

        f.flush()


def datadict_to_hdf5(datadict: DataDict, basepath: str,
                     groupname: str = 'data', append_mode: str = 'new',
                     swmr_mode: bool = True):
    """Write a DataDict to DDH5

    Note: meta data is only written during initial writing of the dataset.
    If we're appending to existing datasets, we're not setting meta
    data anymore.

    :param datadict: datadict to write to disk.
    :param basepath: path of the file, without extension.
    :param groupname: name of the top level group to store the data in
    :param append_mode:
        - 'new': only rows that are new in the datadict and not yet in the
          file will be appended
        - 'all': all contents of the datadict will be appended.
        - None: if group exists already in the file, all content will be
          deleted.
    :param swmr_mode: use HDF5 SWMR mode on the file when appending.
    """
    if append_mode not in ['new', 'all', None]:
        raise ValueError("append_mode must be one of 'new', 'all', None")

    if len(basepath) > len(DATAFILEXT) and \
            basepath[-len(DATAFILEXT):] == DATAFILEXT:
        filepath = basepath
        basepath = basepath[:-len(DATAFILEXT)]
    else:
        filepath = basepath + DATAFILEXT

    init_file(filepath, groupname, reset=append_mode is None)

    with h5py.File(filepath, 'a', libver='latest') as f:
        grp = f[groupname]

        # add top-level meta data.
        for k, v in datadict.meta_items(clean_keys=False):
            set_attr(grp, k, v)

        # if we want to use swmr, we need to make sure that we're not
        # creating any more objects (see hdf5 docs).
        if swmr_mode:
            allexist = True
            for k, v in datadict.data_items():
                if k not in grp:
                    allexist = False
            if allexist:
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
                dslen = len(ds.value)

                if append_mode == 'new':
                    newshp = tuple([nrows] + list(shp[1:]))
                    ds.resize(newshp)
                    ds[dslen:] = data[dslen:]
                elif append_mode == 'all':
                    newshp = tuple([dslen+nrows] + list(shp[1:]))
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
        lens = [len(grp[k].value) for k in keys]

        if len(set(lens)) > 1:
            if not ignore_unequal_lengths:
                raise RuntimeError('Unequal lengths in the datasets.')

            if stopidx is None or stopidx > min(lens):
                stopidx = min(lens)
        else:
            if stopidx is None or stopidx > lens[0]:
                stopidx = lens[0]

        for k in keys:
            try:
                ds = grp[k]
                entry = dict(values=np.array([]),)

                if 'axes' in ds.attrs:
                    entry['axes'] = deh5ify(ds.attrs['axes']).tolist()
                else:
                    entry['axes'] = []

                if 'unit' in ds.attrs:
                    entry['unit'] = deh5ify(ds.attrs['unit'])

                if not structure_only:
                    entry['values'] = ds.value[startidx:stopidx]

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
