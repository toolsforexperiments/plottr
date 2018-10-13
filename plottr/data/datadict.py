"""
datadict.py

Data classes we use throughout the package.
"""

import copy
import numpy as np
import pandas as pd
import xarray as xr


__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'

# TODO:
# * add possibility for metadata, say for keys in the format __key__
#   (then should have dataItems() and metaItems() or so)
# * serialization (json...)
# * support for data where axes can themselves depend on other
# * support for automatically creating imaginary data
# * the notion of compatibility here is too naive i think.
#   maybe i need to refine that a bit.


def togrid(data, names=None, make_copy=True, sanitize=True,
           allow_incompatible=False):
    """
    Place data onto a grid, i.e., that data has the shape of a meshgrid of its axes.
    The axes stay 1-d.
    If the input data is already on a grid, return existing grid
    (potentially copied and/or sanitized).

    Parameters:
    -----------
    data : DataDict (or child thereof)
        input data

    names : list of strings or None (None)
        will be passed on to data.get_grid

    make_copy : bool (True)
        if true, return a copy of the data.

    sanitize : bool (True)
        if true, remove unused data fields/axes.

    allow_incompatible : bool (False)
        if False, input data must have compatible axes.

    Returns:
    --------
    GridDataDict with resulting data.

    """
    if data in [None, {}]:
        return DataDict()

    if isinstance(data, GridDataDict):
        if make_copy:
            data = copy.copy(data)

    elif isinstance(data, DataDict):
        data = data.get_grid(names)
        data.validate()

    else:
        raise ValueError("Data has unrecognized type '{}'. Need a form of DataDict.".format(type(data)))

    if sanitize and names is not None:
        remove = []
        for n, v in data.items():
            if n not in names and n in data.dependents():
                remove.append(n)
        for r in remove:
            del data[r]

    if not allow_incompatible:
        axes = []
        n0 = None
        for n in data.dependents():
            if len(axes) == 0:
                axes = data[n]['axes']
                n0 = n
            else:
                if data[n]['axes'] != axes:
                    err = "Gridding multiple data sets requires compatible axes. "
                    err += "Found axes '{}' for '{}', but '{}' for '{}'.".format(axes, n0, data[n]['axes'], n)
                    raise ValueError(err)

    if sanitize:
        data.remove_unused_axes()

    data.validate()
    return data



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


    def data(self, key):
        return self[key]['values']

    def structure(self, meta=True):
        """
        Return the datadict without values ('value' ommitted in the dict).
        if 'meta' is true, we add a key 'shape' in 'info' that contains the
        shape of each data field.
        """
        if self.validate():
            s = DataDictBase()
            for n, v in self.items():
                s[n] = dict(axes=v['axes'], unit=v['unit'], info={})
                if meta:
                    s[n]['info']['shape'] = np.array(v['values']).shape

            s.validate()
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
                axes = self.axes_list(d)
            else:
                if self.axes_list(d) != axes:
                    return False
        return True


    def axes_list(self, selectedData=None):
        lst = []
        if selectedData is None:
            for k, v in self.items():
                if 'axes' in v:
                    for n in v['axes']:
                        if n not in lst:
                            lst.append(n)
        else:
            if isinstance(selectedData, str):
                selectedData = [selectedData]
            for n in selectedData:
                if 'axes' not in self[n]:
                    continue
                for m in self[n]['axes']:
                    if m not in lst:
                        lst.append(m)

        return lst

    def dependents(self):
        if self.validate():
            ret = []
            for n, v in self.items():
                if len(v.get('axes', [])) != 0:
                    ret.append(n)
            return ret

    def validate(self):
        msg = '\n'
        for n, v in self.items():
            if 'axes' in v:
                for na in v['axes']:
                    if na not in self:
                        msg += " * '{}' has axis '{}', but no data with name '{}' registered.\n".format(n, na, na)
            else:
                v['axes'] = []

            if 'unit' not in v:
                v['unit'] = ''

            if 'values' not in v:
                v['values'] = []

            if 'info' not in v:
                v['info'] = {}

        if msg != '\n':
            raise ValueError(msg)

        return True

    def remove_unused_axes(self):
        dependents = self.dependents()
        unused = []

        for n, v in self.items():
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


class DataDict(DataDictBase):
    # TODO:
    # * method to detect/remove duplicate coordinates.
    # *

    """
    Contains data in 'linear' arrays. I.e., for data field 'z' with axes 'x' and 'y',
    all of 'x', 'y', 'z' have 1D arrays as values with some lenght; the lengths must match.
    Each element x[i], y[i], z[i] is one datapoint, with x[i], y[i] being the coordinates.
    """

    def __add__(self, newdata):
        """
        Adding two datadicts by appending each data array. Returns a new datadict.
        """
        s = self.structure()
        if s == newdata.structure():
            for k, v in self.items():
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
        if self.structure() == newdata.structure():
            for k, v in newdata.items():
                if isinstance(self[k]['values'], list) and isinstance(v['values'], list):
                    self[k]['values'] += v['values']
                else:
                    self[k]['values'] = np.append(np.array(self[k]['values']), np.array(v['values']))
        else:
            raise ValueError('Incompatible data structures.')


    def validate(self):
        if super().validate():
            nvals = None
            nvalsrc = None
            msg = '\n'

            for n, v in self.items():
                if nvals is None:
                    nvals = len(v['values'])
                    nvalsrc = n
                else:
                    if len(v['values']) != nvals:
                        msg += " * '{}' has length {}, but have found {} in '{}'\n".format(n, len(v['values']), nvals, nvalsrc)

            if msg != '\n':
                raise ValueError(msg)

        return True

    def _value_dict(self, use_units=False):
        if self.validate():
            ret = {}
            for k, v in self.items():
                name = k
                if use_units and v['unit'] != '':
                    name += ' ({})'.format(v['unit'])
                ret[name] = v['values']

            return ret

    def to_dataframe(self):
        return pd.DataFrame(self._value_dict())

    def to_multiindex_dataframes(self, use_units=False):
        if self.validate():
            dfs = {}
            for n, v in self.items():
                if not len(v['axes']):
                    continue

                vals = v['values']
                axvals = []
                axnames = []
                for axname in v['axes']:
                    axvals.append(self[axname]['values'])
                    _axname = axname
                    if use_units and self[axname]['unit'] != '':
                        _axname += ' ({})'.format(self[axname]['unit'])
                    axnames.append(_axname)

                mi = pd.MultiIndex.from_tuples(list(zip(*axvals)), names=axnames)

                _name = n
                if use_units and self[n]['unit'] != '':
                    _name += ' ({})'.format(self[n]['unit'])
                df = pd.DataFrame({_name : v['values']}, mi)
                dfs[n] = df

            return dfs

    def to_xarray(self, name):
        df = self.to_multiindex_dataframes()[name]
        arr = xr.DataArray(df)

        for idxn in arr.indexes:
            idx = arr.indexes[idxn]

            if idxn not in self:
                if isinstance(idx, pd.MultiIndex):
                    arr = arr.unstack(idxn)
                else:
                    arr = arr.squeeze(idxn).drop(idxn)

        return arr

    def get_grid(self, name=None, mask_nan=True):
        if name is None:
            name = self.dependents()
        if isinstance(name, str):
            name = [name]

        ret = GridDataDict()

        for n in name:
            arr = self.to_xarray(n)

            for idxn in arr.indexes:
                vals = arr.indexes[idxn].values

                if idxn in ret and vals.shape != ret[idxn]['values'].shape:
                    raise ValueError(
                        "'{}' used in different shapes. Arrays cannot be used as data and axis in a single grid data set.".format(idxn)
                    )

                ret[idxn] = dict(
                    values=vals,
                    unit=self[idxn]['unit']
                    )

            if mask_nan and len(np.where(np.isnan(arr.values))[0]) > 0:
                v = np.ma.masked_where(np.isnan(arr.values), arr.values)
            else:
                v = arr.values
            ret[n] = dict(
                values=v,
                axes=self[n]['axes'],
                unit=self[n]['unit'],
                )

        return ret


class GridDataDict(DataDictBase):
    # TODO:
    # * implement append and add. could solve by de-gridding, then re-gridding; but that might be slow.
    """
    Contains data in a grid form.
    In this case each field that is used as an axis contains only unique values,
    and the shape of a data field is (nx, ny, ...), where nx, ny, ... are the lengths
    of its x, y, ... axes.
    """

    def validate(self):
        if super().validate():
            msg = '\n'

            for n, v in self.items():
                if len(v['axes']) > 0:
                    shp = v['values'].shape
                    axlens = []
                    for ax in v['axes']:
                        axvals = self[ax]['values']

                        if not isinstance(self[ax]['values'], np.ndarray):
                            self[ax]['values'] = np.array(self[ax]['values'])

                        if len(self[ax]['values'].shape) > 1:
                            msg += " * '{}' used as an axis, but does not have 1D data".format(ax)

                        axlens.append(self[ax]['values'].size)

                    if shp != tuple(axlens):
                        msg += " * '{}' has shape {}, but axes lengths are {}.".format(n, shp, tuple(axlens))

            if msg != '\n':
                raise ValueError(msg)

        return True
