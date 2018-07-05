"""
plots.py

Data classes we use throughout the package.
"""

import numpy as np
import pandas as pd
import xarray as xr

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


class DataDictBase(dict):
    """
    Simple data storage class that is based on a regular dictionary.
    The basic structure of data looks like this:
        {
            'data_1' : {
                'axes' : ['ax1', 'ax2'],
                'unit' : 'some unit',
                'values' : [ ... ],
            },
            'ax1' : {
                'axes' : [],
                'unit' : 'some other unit',
                'values' : [ ... ],
            },
            'ax2' : {
                'axes' : [],
                'unit' : 'a third unit',
                'values' : [ ... ],
            },
            ...
        }
    I.e., we define data 'fields', that have unit, values, and we can specify that some data has axes
    (dependencies) specified by other data fields.
    """

    def __init__(self, *arg, **kw):
        super().__init__(self, *arg, **kw)


    def structure(self):
        if self.validate():
            s = {}
            for n, v in self.items():
                s[n] = dict(axes=v['axes'], unit=v['unit'])
            return s

    def label(self, name):
        if self.validate():
            if name not in self:
                raise ValueError("No field '{}' present.".format(name))

            n = name
            if self[name]['unit'] != '':
                n += ' ({})'.format(self[name]['unit'])

            return n

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
    """
    Contains data in 'linear' arrays. I.e., for data field 'z' with axes 'x' and 'y',
    all of 'x', 'y', 'z' have 1D arrays as values with some lenght.
    Each element x[i], y[i], z[i] is one datapoint, with x[i], y[i] being the coordinates.
    """

    def __add__(self, newdata):
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
        if self.structure() == newdata.structure():
            for k, v in newdata.items():
                if isinstance(self[k]['values'], list) and isinstance(v['values'], list):
                    self[k]['values'] += v['values']
                else:
                    self[k]['values'] = np.append(np.array(self[k]['values']), np.array(v['values']))


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