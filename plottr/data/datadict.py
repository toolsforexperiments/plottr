"""
datadict.py

Data classes we use throughout the package.
"""

from typing import List, Tuple, Dict, Sequence, Union, Optional
from functools import reduce

import copy as cp
import numpy as np
import pandas as pd
import xarray as xr


__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'

# TODO: serialization (json...)
# TODO: a function that returns axes values given a set of slices or so.
# TODO: treatment of nested dims: expand or flatten-method; detection of nested dims.

class DataDictBase(dict):
    """
    Simple data storage class that is based on a regular dictionary.
    The basic structure of data looks like this:
        {
            'data_1' : {
                'axes' : ['ax1', 'ax2'],
                'unit' : 'some unit',
                'values' : [ ... ],
                'info' : {...}
            },
            'ax1' : {
                'axes' : [],
                'unit' : 'some other unit',
                'values' : [ ... ],
                'info' : {...}
            },
            'ax2' : {
                'axes' : [],
                'unit' : 'a third unit',
                'values' : [ ... ],
                'info' : {...},
            },
            ...
        }
    I.e., we define data 'fields', that have unit, values, and we can specify that some data has axes
    (dependencies) specified by other data fields.

    This base class does not make assumptions about the structure of the values. This is implemented in
    inheriting classes.
    """

    def __init__(self, *arg, **kw):
        super().__init__(self, *arg, **kw)

    def data_items(self):
        for k, v in self.items():
            if k[:2] != '__' and k[-2:] != '__':
                yield k, v

    def meta_items(self):
        for k, v in self.items():
            if k[:2] == '__' and k[-2:] == '__':
                yield k[2:-2], v

    def data_vals(self, key):
        return self[key]['values']

    def data_meta(self, key):
        ret = {}
        for k, v in self[key].items():
            if k[:2] == '__' and k[-2:] == '__':
                ret[k[2:-2]] = v
        return ret

    def add_meta(self, key, value, data=None):
        key = '__' + key + '__'
        if data is None:
            self[key] = value
        else:
            self[data][key] = value

    def meta_val(self, key, data=None):
        key = '__' + key + '__'
        if data is None:
            return self[key]
        else:
            return self[data][key]

    def delete_meta(self, key, data=None):
        key = '__' + key + '__'
        if data is None:
            del self[key]
        else:
            del self[data][key]

    def clear_meta(self, data: Union[str, None] = None):
        """
        Delete meta information. If `data` is not None, delete only
        meta information from data field `data`. Else, delete all
        top-level meta, as well as meta for all data fields.
        """
        if data is None:
            meta_list = [k for k, _ in self.meta_items()]
            for m in meta_list:
                self.delete_meta(m)

            for d, _ in self.data_items():
                for m, _ in self.data_meta(d).items():
                    self.delete_meta(m, d)

        else:
            for m, _ in self.data_meta(data).items():
                self.delete_meta(m, data)


    def extract(self, data: List[str], include_meta: bool = True,
                copy: bool = True, sanitize: bool = True):
        """
        Return a new datadict with all fields specified in `data' included.
        Will also take any axes fields along that have not been explicitly specified.
        """
        if isinstance(data, str):
            data = [data]
        else:
            data = data.copy()

        for d in data:
            for a in self.axes(d):
                if a not in data:
                    data.append(a)

        ret = self.__class__()
        for d in data:
            if copy:
                ret[d] = cp.deepcopy(self[d])
            else:
                ret[d] = self[d]

        if include_meta:
            for k, v in self.meta_items():
                if copy:
                    ret.add_meta(k, cp.deepcopy(v))
                else:
                    ret.add_meta(k, v)

        if sanitize:
            ret.sanitize()

        ret.validate()
        return ret

    # info about structure

    @staticmethod
    def same_structure(*dicts, check_shape=False):
        """
        Check if all supplied datadicts share the same data structure
        (i.e., dependents and axes).
        Ignores meta info and values.
        Checks also for matching shapes if `check_shape' is `True'.
        """
        if len(dicts) < 2:
            return True

        def empty_structure(d):
            s = d.structure(include_meta=False, add_shape=check_shape)
            for k, v in s.data_items():
                if 'values' in v:
                    del s[k]['values']
            return s

        s0 = empty_structure(dicts[0])
        for d in dicts[1:]:
            if d is None:
                return False
            if s0 != empty_structure(d):
                return False

        return True


    def structure(self, add_shape=True, include_meta=True):
        """
        Return the datadict without values ('value' ommitted in the dict).
        if 'add_shape' is true, we add a key '__shape__' that contains the
        shape of each data field.
        if `include_meta' is true, we also take the meta info of the datadict
        along.
        """
        if self.validate():
            s = DataDictBase()
            shapes = {}
            for n, v in self.data_items():
                v2 = v.copy()
                v2.pop('values')
                s[n] = v2
                if add_shape:
                    shapes[n] = np.array(v['values']).shape

            if include_meta:
                for n, v in self.meta_items():
                    s.add_meta(n, v)
            else:
                s.clear_meta()

            for n, shp in shapes.items():
                s.add_meta('shape', shp, data=n)

            return s

    def label(self, name):
        if self.validate():
            if name not in self:
                raise ValueError("No field '{}' present.".format(name))

            n = name
            if self[name]['unit'] != '':
                n += ' ({})'.format(self[name]['unit'])

            return n

    def compatible_axes(self):
        """
        Returns True if all dependent data fields have the same axes, False
        otherwise.
        """
        axes = []
        for i, d in enumerate(self.dependents()):
            if i == 0:
                axes = self.axes(d)
            else:
                if self.axes(d) != axes:
                    return False
        return True


    def axes(self, data=None):
        lst = []
        if data is None:
            for k, v in self.data_items():
                if 'axes' in v:
                    for n in v['axes']:
                        if n not in lst and self[n].get('axes', []) == []:
                            lst.append(n)
        else:
            if isinstance(data, str):
                data = [data]
            for n in data:
                if 'axes' not in self[n]:
                    continue
                for m in self[n]['axes']:
                    if m not in lst and self[m].get('axes', []) == []:
                        lst.append(m)

        return lst

    def dependents(self):
        ret = []
        for n, v in self.data_items():
            if len(v.get('axes', [])) != 0:
                ret.append(n)
        return ret


    def shapes(self) -> Dict[str, Tuple[int, ...]]:
        """
        Return a dictionary of the form {'key' : shape}, where shape is the
        np.shape-tuple of the data with name `key`.
        """
        shapes = {}
        for k, v in self.data_items():
            shapes[k] = np.array(self.data_vals(k)).shape

        return shapes

    # validation and sanitizing

    def validate(self):
        msg = '\n'
        for n, v in self.data_items():
            if 'axes' in v:
                for na in v['axes']:
                    if na not in self.axes():
                        msg += " * '{}' has axis '{}', but no independent with name '{}' registered.\n".format(n, na, na)
            else:
                v['axes'] = []

            if 'unit' not in v:
                v['unit'] = ''

            v['values'] = np.array(v.get('values', []))

            # if 'info' not in v:
            #     v['info'] = {}

            if '__shape__' in v and not self.__class__ == DataDictBase:
                v['__shape__'] = np.array(v['values']).shape

        if msg != '\n':
            raise ValueError(msg)

        return True

    def remove_unused_axes(self):
        dependents = self.dependents()
        unused = []

        for n, v in self.data_items():
            used = False
            if n not in dependents:
                for m in dependents:
                    if n in self[m]['axes']:
                        used = True
            else:
                used = True
            if not used:
                unused.append(n)

        for u in unused:
            del self[u]

    def sanitize(self):
        self.remove_unused_axes()

    # axes order tools

    def new_order(self, name, **kw):
        """
        return the list of axes indices that can be used
        to re-order the axes of the dataset given by name.

        kws are in the form {axes_name = new_position}.
        """
        # check if the given indices are each unique
        used = []
        for n, i in kw.items():
            if i in used:
                raise ValueError('Order indices have to be unique.')
            used.append(i)

        axlist = self[name]['axes']
        neworder = [None for a in axlist]
        oldorder = list(range(len(axlist)))

        for n, newidx in kw.items():
            neworder[newidx] = axlist.index(n)

        for i in neworder:
            if i in oldorder:
                del oldorder[oldorder.index(i)]

        for i in range(len(neworder)):
            if neworder[i] is None:
                neworder[i] = oldorder[0]
                del oldorder[0]

        return tuple(neworder), [self[name]['axes'][i] for i in neworder]


    def reorder_axes(self, data_names=None, **kw):
        """
        Reorder the axes for all data_names. New order is
        determined by kws in the form {axis_name : new_position}.

        if data_names is None, we try all dependents in the dataset.
        """
        if data_names is None:
            data_names = self.dependents()
        if isinstance(data_names, str):
            data_names = [data_names]

        for n in data_names:
            neworder, newaxes = self.new_order(n, **kw)
            self[n]['axes'] = newaxes

        self.validate()


class DataDict(DataDictBase):
    """
    Contains data in 'linear' arrays. I.e., for data field 'z' with axes 'x' and 'y',
    all of 'x', 'y', 'z' have 1D arrays as values with some lenght; the lengths must match.
    Each element x[i], y[i], z[i] is one datapoint, with x[i], y[i] being the coordinates.
    """

    def __add__(self, newdata):
        """
        Adding two datadicts by appending each data array. Returns a new datadict.
        """
        s = self.structure(add_shape=False)
        if DataDictBase.same_structure(self, newdata):
            for k, v in self.data_items():
                val0 = self[k]['values']
                val1 = newdata[k]['values']
                if isinstance(val0, list) and isinstance(val1, list):
                    s[k]['values'] = self[k]['values'] + newdata[k]['values']
                else:
                    s[k]['values'] = np.append(np.array(self[k]['values']), np.array(newdata[k]['values']))
            return s
        else:
            raise ValueError('Incompatible data structures.')

    def append(self, newdata):
        """
        Append a datadict to this one by appending. This in in-place and doesn't return anything.
        """
        if DataDictBase.same_structure(self, newdata):
            for k, v in newdata.data_items():
                if isinstance(self[k]['values'], list) and isinstance(v['values'], list):
                    self[k]['values'] += v['values']
                else:
                    self[k]['values'] = np.append(np.array(self[k]['values']), np.array(v['values']))
        else:
            raise ValueError('Incompatible data structures.')


    # validation and sanitizing

    def validate(self):
        if super().validate():
            nvals = None
            nvalsrc = None
            msg = '\n'

            for n, v in self.data_items():

                # this is probably overly restrictive...
                # if len(v['values'].shape) > 1:
                #     msg += f" * '{n}' is not a 1D array (has shape {v['values'].shape})"

                if nvals is None:
                    nvals = len(v['values'])
                    nvalsrc = n
                else:
                    if len(v['values']) != nvals:
                        msg += " * '{}' has length {}, but have found {} in '{}'\n".format(n, len(v['values']), nvals, nvalsrc)

            if msg != '\n':
                raise ValueError(msg)

        return True


    def sanitize(self):
        super().sanitize()
        self.remove_invalid_entries()


    def remove_invalid_entries(self):
        """
        Remove all rows that are `None' or `np.nan' in *all* dependents.
        """
        idxs = []
        for d in self.dependents():
            _idxs = np.array([])
            _idxs = np.append(_idxs, np.where(self.data_vals(d) == None)[0])
            try:
                _idxs = np.append(_idxs, np.where(np.isnan(self.data_vals(d)))[0])
            except TypeError:
                pass
            idxs.append(_idxs)

        if len(idxs) > 0:
            remove_idxs = reduce(np.intersect1d, tuple(np.array(idxs).astype(int)))
            for k, v in self.data_items():
                v['values'] = np.delete(v['values'], remove_idxs)


class MeshgridDataDict(DataDictBase):

    def shape(self):
        """
        Return the shape of the meshgrid.
        """
        for d, _ in self.data_items():
            return self.data_vals(d).shape
        return None

    def validate(self):
        if not super().validate():
            return False

        msg = '\n'

        axes = None
        axessrc = ''
        for d in self.dependents():
            if axes is None:
                axes = self.axes(d)
            else:
                if axes != self.axes(d):
                    msg += f" * All dependents must have the same axes, but "
                    msg += f"{d} has {self.axes(d)} and {axessrc} has {axes}\n"

        shp = None
        shpsrc = ''
        for n, v in self.data_items():
            if shp is None:
                shp = v['values'].shape
                shpsrc = n
            else:
                if v['values'].shape != shp:
                    msg += f" * shapes need to match, but '{n}' has {v['values'].shape}, "
                    msg += f"and '{shpsrc}' has {shp}.\n"

        if msg != '\n':
            raise ValueError(msg)

        return True


    def reorder_axes(self, **kw):
        """
        Reorder the axes for all data.
        This includes transposing the data, since we're on a grid.
        """
        transposed = []
        for n in self.dependents():
            neworder, newaxes = self.new_order(n, **kw)
            self[n]['axes'] = newaxes
            self[n]['values'] = self[n]['values'].transpose(neworder)
            for ax in self.axes(n):
                if ax not in transposed:
                    self[ax]['values'] = self[ax]['values'].transpose(neworder)
                    transposed.append(ax)

        self.validate()


# Tools for converting between different data types

def guess_shape_from_datadict(data: DataDict) -> Dict[str, Tuple[int]]:
    """
    Try to guess the shape of the datadict dependents from the unique values of
    their axes.
    """

    # TODO: should fail when grid is obviously not very good (too many unique values...)

    shapes = {}
    for d in data.dependents():
        shp = []
        axes = data.axes(d)
        for a in axes:
            # need to make sure we remove invalids before determining unique vals.
            cleaned_data = data.data_vals(a)
            cleaned_data = cleaned_data[cleaned_data != None]
            try:
                cleaned_data = cleaned_data[~np.isnan(cleaned_data)]
            except TypeError:
                # means it's not float. that's ok.
                pass

            shp.append(np.unique(cleaned_data).size)

        shapes[d] = tuple(shp)

    return shapes

def array1d_to_meshgrid(arr: Sequence, target_shape: Tuple[int],
                        copy: bool = True) -> np.ndarray:
    """
    try to reshape `arr' to target shape.
    If target shape is larger than the array, fill with invalids
    (`nan' for float and complex dtypes, `None' otherwise).
    If target shape is smaller than the array, cut off the end.
    """
    if not isinstance(arr, np.ndarray):
        arr = np.array(arr)
    if copy:
        arr = arr.copy()

    newsize = np.prod(target_shape)
    if newsize < arr.size:
        arr = arr[:newsize]
    elif newsize > arr.size:
        if arr.dtype in [np.float, np.complex]:
            fill = np.zeros(newsize - arr.size) * np.nan
        else:
            fill = np.array((newsize - arr.size) * [None])
        arr = np.append(arr, fill)

    return arr.reshape(target_shape)


def datadict_to_meshgrid(data: DataDict, target_shape: Union[Tuple[int], None] = None,
                         copy: bool = True, sanitize: bool = True) -> MeshgridDataDict:
    """
    Try to make a meshgrid from `data'. If no target shape is supplied, we try to guess.
    """
    # TODO: support for cues inside the data set about the shape.
    # TODO: maybe it could make sense to include a method to sort the meshgrid axes.

    # if the data is empty, return empty MeshgridData
    if len([k for k, _ in data.data_items()]) == 0:
        return None

    # guess what the shape likely is.
    if not data.compatible_axes():
        raise ValueError('Non-compatible axes, cannot grid that.')

    if target_shape is None:
        shps = guess_shape_from_datadict(data)
        if len(set(shps.values())) > 1:
            raise RuntimeError('Cannot determine unique shape for all data.')

        target_shape = list(shps.values())[0]

    newdata = MeshgridDataDict(**data.structure(add_shape=False))
    for k, v in data.data_items():
        newdata[k]['values'] = array1d_to_meshgrid(v['values'], target_shape, copy=copy)

    if sanitize:
        newdata.sanitize()
    newdata.validate()
    return newdata


def meshgrid_to_datadict(data: MeshgridDataDict, copy: bool = True,
                         sanitize: bool = True) -> DataDict:
    """
    Make a DataDict from a MeshgridDataDict by simply reshaping the data.
    """
    newdata = DataDict(**data.structure(add_shape=False))
    for k, v in data.data_items():
        val = v['values'].reshape(-1)
        if copy:
            val = val.copy()
        newdata[k]['values'] = val

    if sanitize:
        newdata.sanitize()
    newdata.validate()
    return newdata
