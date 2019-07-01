"""plottr.data.datadict_storage

Provides file-storage tools for the DataDict class.
"""

import os
import numpy as np
import h5py


def h5ify(obj):
    if type(obj) == list or type(obj) == np.ndarray:
        if len(obj) > 0 and type(obj[0]) == str:
            return np.chararray.encode(np.array(obj, dtype='U'),
                                       encoding='utf8')
    return obj


def set_attr(h5obj, name, val):
    try:
        h5obj.attrs[name] = h5ify(val)
    except TypeError:
        newval = str(val)
        h5obj.attrs[name] = h5ify(newval)


def datadict_to_hdf5(datadict, filepath, groupname, append_if_exists=True):
    with h5py.File(filepath, 'a', libver='latest') as f:
        f.swmr_mode = True
        grp = f[groupname]

        if not append_if_exists:
            for k in grp:
                del grp[k]

        for k, v in datadict.data_items():
            data = v['values']
            shp = data.shape
            nrows = shp[0]


def datadict_from_hdf5(filepath, groupname, startidx=None, stopidx=None,
                       structure_only=False, ignore_unequal_lengths=True):
    pass


class DataDictWriter(object):

    def __init__(self, datadict, basepath, name='data', reset=False):
        self.basepath = basepath
        self.datafp = self.basepath + ".h5"
        self.name = name
        self.datadict = datadict

        self.init_file(reset=reset)

    def init_file(self, reset):
        folder, path = os.path.split(self.datafp)
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)

        if not os.path.exists(self.datafp):
            with h5py.File(self.datafp, 'w', libver='latest') as _:
                pass

        with h5py.File(self.datafp, 'a', libver='latest') as f:
            if reset and self.name in f:
                del f[self.name]
                f.flush()

            if self.name not in f:
                f.create_group(self.name)

    def write(self):
        with h5py.File(self.datafp, 'a', libver='latest') as f:
            f.swmr_mode = True
            grp = f[self.name]

            for k, v in self.datadict.data_items():
                data = v['values']
                shp = data.shape
                nrows = shp[0]

                if k not in grp:
                    maxshp = tuple([None] + list(shp[1:]))
                    ds = grp.create_dataset(k, maxshape=maxshp, data=data)
                    if v.get('axes', []) != []:
                        set_attr(ds, 'axes', v['axes'])
                    if v.get('unit', "") != "":
                        set_attr(ds, 'unit', v['unit'])

                else:
                    ds = grp[k]
                    dslen = len(ds.value)
                    newshp = tuple([nrows] + list(shp[1:]))
                    ds.resize(newshp)
                    ds[dslen:] = data[dslen:]

                for kk, vv in v.items():
                    if kk in ['value', 'axes', 'unit']:
                        continue
                    set_attr(ds, kk, vv)
                ds.flush()

            data_keys = [k for k, v in self.datadict.data_items()]
            for k, v in self.datadict.items():
                if k not in data_keys:
                    set_attr(grp, k, v)

            f.flush()


class DataDictReader(object):

    def __init__(self, basepath, name='data', datadict=None):
        self.basepath = basepath
        self.datafp = self.basepath + ".h5"
        self.name = name
        self.datadict = datadict

    def read(self):
        pass
