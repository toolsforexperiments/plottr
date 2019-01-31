"""
datadict.py :

Data classes we use throughout the plottr package, and tools to work on them.
"""

import copy as cp
from functools import reduce
from typing import List, Tuple, Dict, Sequence, Union, Any

import numpy as np

from plottr.utils import num, misc

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


# TODO: serialization (json...)
# TODO: functionality that returns axes values given a set of slices.
# TODO: an easier way to access data and meta values.
#  maybe with getattr/setattr?
# TODO: direct slicing of full datasets. implement getitem/setitem?


class DataDictBase(dict):
    """
    Simple data storage class that is based on a regular dictionary.

    This base class does not make assumptions about the structure of the
    values. This is implemented in inheriting classes.
    """

    def __init__(self, **kw):
        super().__init__(self, **kw)

    # Assignment and retrieval of data and meta data

    @staticmethod
    def _is_meta_key(key):
        if key[:2] == '__' and key[-2:] == '__':
            return True

    @staticmethod
    def _meta_key_to_name(key):
        if DataDictBase._is_meta_key(key):
            return key[2:-2]
        else:
            raise ValueError(f'{key} is not a meta key.')

    @staticmethod
    def _meta_name_to_key(name):
        return '__' + name + '__'

    def data_items(self):
        """
        Generator for data field items.

        Like dict.items(), but ignores meta data.
        """
        for k, v in self.items():
            if not self._is_meta_key(k):
                yield k, v

    def meta_items(self, data: Union[str, None] = None):
        """
        Generator for meta items.

        Like dict.items(), but yields `only` meta entries.
        The keys returned do not contain the underscores used internally.

        :param data: if ``None`` iterate over global meta data.
                     if it's the name of a data field, iterate over the meta
                     information of that field.

        """
        if data is None:
            for k, v in self.items():
                if self._is_meta_key(k):
                    yield self._meta_key_to_name(k), v

        else:
            for k, v in self[data].items():
                if self._is_meta_key(k):
                    yield self._meta_key_to_name(k), v

    def data_vals(self, key: str) -> Sequence:
        """
        Return the data values of field ``key``.

        Equivalent to ``DataDict['key'].values``.

        :param key: name of the data field
        :return: values of the data field
        """
        if self._is_meta_key(key):
            raise ValueError(f"{key} is a meta key.")
        return self[key]['values']

    def meta_val(self, key: str, data: Union[str, None] = None) -> Any:
        """
        Return the value of meta field ``key`` (given without underscore).

        :param key: name of the meta field
        :param data: ``None`` for global meta; name of data field for data meta.
        :return: the value of the meta information.
        """
        k = self._meta_name_to_key(key)
        if data is None:
            return self[k]
        else:
            return self[data][k]

    def add_meta(self, key: str, value: Any, data: Union[str, None] = None):
        """
        Add meta info to the dataset.

        If the key already exists, meta info will be overwritten.

        :param key: Name of the meta field (without underscores)
        :param value: Value of the meta information
        :param data: if ``None``, meta will be global; otherwise assigned to
                     data field ``data``.

        """
        key = self._meta_name_to_key(key)
        if data is None:
            self[key] = value
        else:
            self[data][key] = value

    def delete_meta(self, key, data=None):
        """
        Remove meta data.

        :param key: name of the meta field to remove.
        :param data: if ``None``, this affects global meta; otherwise remove
                     from data field ``data``.

        """
        key = self._meta_name_to_key(key)
        if data is None:
            del self[key]
        else:
            del self[data][key]

    def clear_meta(self, data: Union[str, None] = None):
        """
        Delete meta information.

        :param data: if this is not None, delete onlymeta information from data
                     field `data`. Else, delete all top-level meta, as well as
                     meta for all data fields.

        """
        if data is None:
            meta_list = [k for k, _ in self.meta_items()]
            for m in meta_list:
                self.delete_meta(m)

            for d, _ in self.data_items():
                data_meta_list = [k for k, _ in self.meta_items(d)]
                for m in data_meta_list:
                    self.delete_meta(m, d)

        else:
            for m, _ in self.meta_items(data):
                self.delete_meta(m, data)

    def extract(self, data: List[str], include_meta: bool = True,
                copy: bool = True, sanitize: bool = True) -> 'DataDictBase':
        """
        Extract data from a dataset.

        Return a new datadict with all fields specified in ``data`` included.
        Will also take any axes fields along that have not been explicitly
        specified.

        :param data: data field or list of data fields to be extracted
        :param include_meta: if ``True``, include the global meta data.
                             data meta will always be included.
        :param copy: if ``True``, data fields will be deep copies of the
                     original.
        :param sanitize: if ``True``, will run DataDictBase.sanitize before
                         returning.
        :return: new DataDictBase containing only requested fields.
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
            ret = ret.sanitize()

        ret.validate()
        return ret

    # info about structure

    @staticmethod
    def same_structure(*data: 'DataDictBase',
                       check_shape: bool = False) -> bool:
        """
        Check if all supplied DataDicts share the same data structure
        (i.e., dependents and axes).

        Ignores meta info and values. Checks also for matching shapes if
        `check_shape` is `True`.

        :param data: the data sets to compare
        :param check_shape: whether to include a shape check in the comparison
        :return: ``True`` if the structure matches for all, else ``False``.
        """
        if len(data) < 2:
            return True

        def empty_structure(d):
            s = d.structure(include_meta=False, add_shape=check_shape)
            for k, v in s.data_items():
                if 'values' in v:
                    del s[k]['values']
            return s

        s0 = empty_structure(data[0])
        for d in data[1:]:
            if d is None:
                return False
            if s0 != empty_structure(d):
                return False

        return True

    def structure(self, add_shape: bool = True,
                  include_meta: bool = True) -> 'DataDictBase':
        """
        Get the structure of the DataDict.

        Return the datadict without values (``value`` omitted in the dict).

        :param add_shape: if ``True`` include a meta field ``shape`` for each
                          data field that contains the shape of the data values.

        :param include_meta: if ``True``, include the meta information in
                             the returned dict, else clear it.

        :return: The DataDictBase containing the structure only.
        """
        if self.validate():
            s = DataDictBase()
            shapes = {}
            for n, v in self.data_items():
                v2 = v.copy()
                v2.pop('values')
                if not add_shape and '__shape__' in v2:
                    v2.pop('__shape__')

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

    def label(self, name: str) -> str:
        """
        Get a label for a data field.

        If a unit is present, this is the name with the unit appended in
        brackets: ``name (unit)``; if no unit is present, just the name.

        :param name: name of the data field
        :return: labelled name
        """
        if self.validate():
            if name not in self:
                raise ValueError("No field '{}' present.".format(name))

            n = name
            if self[name]['unit'] != '':
                n += ' ({})'.format(self[name]['unit'])

            return n

    def axes_are_compatible(self) -> bool:
        """
        Check if all dependent data fields have the same axes.

        This includes axes order.

        :return: ``True`` or ``False``
        """
        axes = []
        for i, d in enumerate(self.dependents()):
            if i == 0:
                axes = self.axes(d)
            else:
                if self.axes(d) != axes:
                    return False
        return True

    def axes(self, data: Union[str, None] = None) -> List[str]:
        """
        Return a list of axes.

        :param data: if ``None``, return all axes present in the dataset,
                     otherwise only the axes of the dependent ``data``.
        :return: the list of axes
        """
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

    def dependents(self) -> List[str]:
        """
        Get all dependents in the dataset.

        :return: a list of the names of dependents (data fields that have axes)
        """
        ret = []
        for n, v in self.data_items():
            if len(v.get('axes', [])) != 0:
                ret.append(n)
        return ret

    def shapes(self) -> Dict[str, Tuple[int, ...]]:
        """
        Get the shapes of all data fields.

        :return: a dictionary of the form ``{key : shape}``, where shape is the
                 np.shape-tuple of the data with name ``key``.

        """
        shapes = {}
        for k, v in self.data_items():
            shapes[k] = np.array(self.data_vals(k)).shape

        return shapes

    # validation and sanitizing

    def validate(self):
        """
        Check the validity of the dataset.

        Checks performed:
            * all axes specified with dependents must exist as data fields.

        Other tasks performed:
            * ``unit`` keys are created if omitted
            * ``shape`` meta information is updated with the correct values
              (only if present already).

        :return: ``True`` if valid.
        :raises: ``ValueError`` if invalid.
        """
        msg = '\n'
        for n, v in self.data_items():

            if 'axes' in v:
                for na in v['axes']:
                    if na not in self:
                        msg += " * '{}' has axis '{}', but no field " \
                               "with name '{}' registered.\n".format(
                            n, na, na)
                    elif na not in self.axes():
                        msg += " * '{}' has axis '{}', but no independent " \
                               "with name '{}' registered.\n".format(
                            n, na, na)
            else:
                v['axes'] = []

            if 'unit' not in v:
                v['unit'] = ''

            vals = v.get('values', [])
            if type(vals) not in [np.ndarray, np.ma.core.MaskedArray]:
                vals = np.array(vals)
            v['values'] = vals

            if '__shape__' in v and not self.__class__ == DataDictBase:
                v['__shape__'] = np.array(v['values']).shape

        if msg != '\n':
            raise ValueError(msg)

        return True

    def remove_unused_axes(self) -> 'DataDictBase':
        """
        Removes axes not associated with dependents.

        :return: cleaned dataset.
        """
        dependents = self.dependents()
        unused = []
        ret = self.copy()

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
            del ret[u]

        return ret

    def sanitize(self) -> 'DataDictBase':
        """
        Clean-up tasks:
        * removes unused axes.

        :return: sanitized dataset.
        """
        return self.remove_unused_axes()

    # axes order tools

    def reorder_axes_indices(self, name: str,
                             **pos: int) -> Tuple[Tuple[int], List[str]]:
        """
        Get the indices that can reorder axes in a given way.

        :param name: name of the data field of which we want to reorder axes
        :param pos: new axes position in the form ``axis_name = new_position``.
                    non-specified axes positions are adjusted automatically.
        :return: the tuple of new indices, and the list of axes names in the
                 new order.

        """
        axlist = self.axes(name)
        order = misc.reorder_indices_from_new_positions(axlist, **pos)
        return order, [axlist[i] for i in order]

    def reorder_axes(self, data_names: Union[str, List[str], None] = None,
                     **pos: int) -> 'DataDictBase':
        """
        Reorder data axes.

        :param data_names: data name(s) for which to reorder the axes
                           if None, apply to all dependents.
        :param pos: new axes position in the form ``axis_name = new_position``.
                    non-specified axes positions are adjusted automatically.

        :return: dataset with re-ordered axes.
        """
        if data_names is None:
            data_names = self.dependents()
        if isinstance(data_names, str):
            data_names = [data_names]

        ret = self.copy()
        for n in data_names:
            neworder, newaxes = self.reorder_axes_indices(n, **pos)
            ret[n]['axes'] = newaxes

        ret.validate()
        return ret

    def copy(self) -> 'DataDictBase':
        """
        Make a copy of the dataset.

        :return: A copy of the dataset.
        """
        return cp.deepcopy(self)

    def astype(self, dtype) -> 'DataDictBase':
        """
        Convert all data values to given dtype.

        :param dtype: np dtype.
        :return: copy of the dataset, with values as given type.
        """
        ret = self.copy()
        for k, v in ret.data_items():
            vals = v['values']
            if type(v['values']) not in [np.ndarray, np.ma.core.MaskedArray]:
                vals = np.array(v['values'])
            ret[k]['values'] = vals.astype(dtype)

        return ret

    def mask_invalid(self) -> 'DataDictBase':
        """
        Mask all invalid data in all values.
        :return: copy of the dataset with invalid entries (nan/None) masked.
        """
        ret = self.copy()
        for d, _ in self.data_items():
            arr = self.data_vals(d)
            vals = np.ma.masked_where(num.is_invalid(arr), arr, copy=True)
            vals.fill_value = np.nan
            ret[d]['values'] = vals

        return ret


class DataDict(DataDictBase):
    """
    The most basic implementation of the DataDict class.

    It only enforces that the number of `records` per data field must be
    equal for all fields. This refers to the most outer dimension in case
    of nested arrays.

    The class further implements simple appending of datadicts through the
    ``DataDict.append`` method, as well as allowing addition of DataDict
    instances.
    """

    def __add__(self, newdata: 'DataDict') -> 'DataDict':
        """
        Adding two datadicts by appending each data array.

        Requires that the datadicts have the same structure.
        Retains the meta information of the first array.

        :param newdata: DataDict to be added.
        :returns: combined DataDict.
        :raises: ``ValueError`` if the structures are incompatible.
        """
        s = self.structure(add_shape=False)
        if DataDictBase.same_structure(self, newdata):
            for k, v in self.data_items():
                val0 = self[k]['values']
                val1 = newdata[k]['values']
                s[k]['values'] = np.append(
                    self[k]['values'],
                    newdata[k]['values'],
                    axis=0
                )
            return s
        else:
            raise ValueError('Incompatible data structures.')

    def append(self, newdata):
        """
        Append a datadict to this one by appending data values.

        :param newdata: DataDict to append.
        :raises: ``ValueError``, if the structures are incompatible.
        """
        if DataDictBase.same_structure(self, newdata):
            for k, v in newdata.data_items():
                if isinstance(self[k]['values'], list) and isinstance(
                        v['values'], list):
                    self[k]['values'] += v['values']
                else:
                    self[k]['values'] = np.append(
                        self[k]['values'],
                        v['values'],
                        axis=0
                    )
        else:
            raise ValueError('Incompatible data structures.')

    # shape information and expansion

    def nrecords(self) -> int:
        """
        :return: The number of records in the dataset.
        """
        self.validate()
        for _, v in self.data_items():
            return len(v['values'])

    def _inner_shapes(self) -> Dict[str, Tuple[int]]:
        shapes = self.shapes()
        return {k: v[1:] for k, v in shapes.items()}

    def is_expanded(self) -> bool:
        """
        Determine if the DataDict is expanded.

        :return: ``True`` if expanded. ``False`` if not.
        """
        ishp = self._inner_shapes()
        if set(ishp.values()) == {tuple()}:
            return True
        else:
            return False

    def is_expandable(self) -> bool:
        """
        Determine if the DataDict can be expanded.

        Expansion flattens all nested data values to a 1D array. For doing so,
        we require that all data fields that have nested/inner dimensions (i.e,
        inside the `records` level) shape the inner shape.
        In other words, all data fields must be of shape (N,) or (N, (shape)),
        where shape is common to all that have a shape not equal to (N,).

        :return: ``True`` if expandable. ``False`` otherwise.
        """
        shp = self._inner_shapes()
        if len(set(shp.values())) == 1:
            return True
        elif len(set(shp.values())) == 2 and tuple() in set(shp.values()):
            return True
        else:
            return False

    def expand(self) -> 'DataDict':
        """
        Expand nested values in the data fields.

        Flattens all value arrays. If nested dimensions
        are present, all data with non-nested dims will be repeated
        accordingly -- each record is repeated to match the size of
        the nested dims.

        :return: The flattened dataset.
        :raises: ``ValueError`` if data is not expandable.
        """
        self.validate()
        if not self.is_expandable():
            raise ValueError('Data cannot be expanded.')
        ret = DataDict(**self.structure(add_shape=False))

        if self.is_expanded():
            return self.copy()

        ishp = self._inner_shapes()
        size = max([np.prod(s) for s in ishp.values()])

        for k, v in self.data_items():
            reps = size // np.prod(ishp[k])
            if reps > 1:
                ret[k]['values'] = \
                    self[k]['values'].repeat(reps, axis=0).reshape(-1)
            else:
                ret[k]['values'] = self[k]['values'].reshape(-1)

        return ret

    # validation and sanitizing

    def validate(self) -> bool:
        """
        Check dataset validity.

        Beyond the checks performed in the base class ``DataDictBase``,
        check whether the number of records is the same for all data fields.

        :return: ``True`` if valid.
        :raises: ``ValueError`` if invalid.
        """
        if super().validate():
            nvals = None
            nvalsrc = None
            msg = '\n'

            for n, v in self.data_items():
                if type(v['values']) not in [np.ndarray,
                                             np.ma.core.MaskedArray]:
                    self[n]['values'] = np.array(v['values'])

                if nvals is None:
                    nvals = len(v['values'])
                    nvalsrc = n
                else:
                    if len(v['values']) != nvals:
                        msg += " * '{}' has length {}, but have found {} in " \
                               "'{}'\n".format(
                            n, len(v['values']), nvals, nvalsrc)

            if msg != '\n':
                raise ValueError(msg)

        return True

    def sanitize(self) -> 'DataDict':
        """
        Clean-up.

        Beyond the tasks of the base class ``DataDictBase``:
        * remove invalid entries as far as reasonable.

        :return: sanitized DataDict
        """
        ret = super().sanitize()
        return ret.remove_invalid_entries()

    def remove_invalid_entries(self) -> 'DataDict':
        """
        Remove all rows that are ``None`` or ``np.nan`` in *all* dependents.

        :return: the cleaned DataDict.
        """
        ishp = self._inner_shapes()
        idxs = []

        ret = self.copy()

        # collect rows that are completely invalid
        for d in self.dependents():

            #  need to discriminate whether there are nested dims or not
            if len(ishp[d]) == 0:
                rows = self.data_vals(d)
            else:
                rows = self.data_vals(d).reshape(-1, np.prod(ishp[d]))

            _idxs = np.array([])

            # get indices of all rows that are fully None
            if len(ishp[d]) == 0:
                _newidxs = np.where(rows == None)[0]
            else:
                _newidxs = np.where(np.all(rows == None, axis=-1))[0]
            _idxs = np.append(_idxs, _newidxs)

            # get indices for all rows that are fully NaN. works only
            # for some dtypes, so except TypeErrors.
            try:
                if len(ishp[d]) == 0:
                    _newidxs = np.where(np.isnan(rows))[0]
                else:
                    _newidxs = np.where(np.all(np.isnan(rows), axis=-1))[0]
                _idxs = np.append(_idxs, _newidxs)
            except TypeError:
                pass

            idxs.append(_idxs)

        if len(idxs) > 0:
            remove_idxs = reduce(np.intersect1d,
                                 tuple(np.array(idxs).astype(int)))
            for k, v in ret.data_items():
                v['values'] = np.delete(v['values'], remove_idxs, axis=0)

        return ret


class MeshgridDataDict(DataDictBase):
    """
    A dataset where the axes form a grid on which the dependent values reside.

    This is a more special case than ``DataDict``, but a very common scenario.
    To support flexible grids, this class requires that all axes specify values
    for each datapoint, rather than a single row/column/dimension.

    For example, if we want to specify a 3-dimensional grid with axes x, y, z,
    the values of x, y, z all need to be 3-dimensional arrays; the same goes
    for all dependents that live on that grid.
    Then, say, x[i,j,k] is the x-coordinate of point i,j,k of the grid.

    This implies that a ``MeshgridDataDict`` can only have a single shape,
    i.e., all data values share the exact same nesting structure.

    For grids where the axes do not depend on each other, the correct values for
    the axes can be obtained from np.meshgrid (hence the name of the class).

    Example: a simple uniform 3x2 grid might look like this; x and y are the
    coordinates of the grid, and z is a function of the two::

        x = [[0, 0],
             [1, 1],
             [2, 2]]

        y = [[0, 1],
             [0, 1],
             [0, 1]]

        z = x * y =
            [[0, 0],
             [0, 1],
             [0, 2]]

    Note: Internally we will typically assume that the nested axes are
    ordered from slow to fast, i.e., dimension 1 is the most outer axis, and
    dimension N of an N-dimensional array the most inner (i.e., the fastest
    changing one). This guarantees, for example, that the default implementation
    of np.reshape has the expected outcome. If, for some reason, the specified
    axes are not in that order (e.g., we might have ``z`` with
    ``axes = ['x', 'y']``, but ``x`` is the fast axis in the data).
    In such a case, the guideline is that at creation of the meshgrid, the data
    should be transposed such that it conforms correctly to the order as given
    in the ``axis = [...]`` specification of the data.
    The function ``datadict_to_meshgrid`` provides options for that.
    """

    def shape(self) -> Union[None, Tuple[int]]:
        """
        Return the shape of the meshgrid.

        :returns: the shape as tuple. None if no data in the set.
        """
        for d, _ in self.data_items():
            return np.array(self.data_vals(d)).shape
        return None

    def validate(self):
        """
        Validation of the dataset.

        Performs the following checks:
        * all dependents must have the same axes
        * all shapes need to be identical

        :return: ``True`` if valid.
        :raises: ``ValueError`` if invalid.
        """
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
            if type(v['values']) not in [np.ndarray, np.ma.core.MaskedArray]:
                self[n]['values'] = np.array(v['values'])

            if shp is None:
                shp = v['values'].shape
                shpsrc = n
            else:
                if v['values'].shape != shp:
                    msg += f" * shapes need to match, but '{n}' has"
                    msg += f" {v['values'].shape}, "
                    msg += f"and '{shpsrc}' has {shp}.\n"

            if msg != '\n':
                raise ValueError(msg)

        return True

    def reorder_axes(self, **pos) -> 'MeshgridDataDict':
        """
        Reorder the axes for all data.

        This includes transposing the data, since we're on a grid.

        :param pos: new axes position in the form ``axis_name = new_position``.
                    non-specified axes positions are adjusted automatically.

        :return: Dataset with re-ordered axes.
        """
        transposed = []
        ret = self.copy()

        for n in self.dependents():
            neworder, newaxes = self.reorder_axes_indices(n, **pos)
            ret[n]['axes'] = newaxes
            ret[n]['values'] = self[n]['values'].transpose(neworder)
            for ax in self.axes(n):
                if ax not in transposed:
                    ret[ax]['values'] = self[ax]['values'].transpose(neworder)
                    transposed.append(ax)

        ret.validate()
        return ret


# Tools for converting between different data types

def guess_shape_from_datadict(data: DataDict) -> \
        Dict[str, Union[None, Tuple[List[str], Tuple[int]]]]:
    """
    Try to guess the shape of the datadict dependents from the axes values.

    :param data: dataset to examine.
    :return: a dictionary with the dependents as keys, and inferred shapes as
             values. value is None, if the shape could not be inferred.
    """

    shapes = {}
    for d in data.dependents():
        axnames = data.axes(d)
        axes = {a: data.data_vals(a) for a in axnames}
        shapes[d] = num.guess_grid_from_sweep_direction(**axes)

    return shapes


def datadict_to_meshgrid(data: DataDict,
                         target_shape: Union[Tuple[int, ...], None] = None,
                         inner_axis_order: Union[None, List[str]] = None,
                         use_existing_shape: bool = False) \
        -> MeshgridDataDict:
    """
    Try to make a meshgrid from a dataset.

    :param data: input DataDict.
    :param target_shape: target shape. if ``None`` we use
                         ``guess_shape_from_datadict`` to infer.
    :param inner_axis_order: if axes of the datadict are not specified in the
                             'C' order (1st the slowest, last the fastest axis)
                             then the 'true' inner order can be specified as
                             a list of axes names, which has to match the
                             specified axes in all but order.
                             The data is then transposed to conform to the
                             specified order.
    :param use_existing_shape: if ``True``, simply use the shape that the data
                               already has. For numpy-array data, this might
                               already be present.
                               if ``False``, flatten and reshape.
    :return: the generated ``MeshgridDataDict``.
    """

    # if the data is empty, return empty MeshgridData
    if len([k for k, _ in data.data_items()]) == 0:
        return MeshgridDataDict()

    if not data.axes_are_compatible():
        raise ValueError('Non-compatible axes, cannot grid that.')

    if not use_existing_shape and data.is_expandable():
        data = data.expand()
    elif use_existing_shape:
        target_shape = data.dependents()[0].shape

    # guess what the shape likely is.
    if target_shape is None:
        shp_specs = guess_shape_from_datadict(data)
        shps = [shape for (order, shape) in shp_specs.values()]
        if len(set(shps)) > 1:
            raise ValueError('Cannot determine unique shape for all data.')

        ret = list(shp_specs.values())[0]
        if ret is None:
            raise ValueError('Shape could not be inferred.')

        # the guess-function returns both axis order as well as shape.
        inner_axis_order, target_shape = ret

    # construct new data
    newdata = MeshgridDataDict(**data.structure(add_shape=False))
    axlist = data.axes(data.dependents()[0])

    for k, v in data.data_items():
        vals = num.array1d_to_meshgrid(v['values'], target_shape, copy=True)

        # if an inner axis order is given, we transpose to transform from that
        # to the specified order.
        if inner_axis_order is not None:
            transpose_idxs = misc.reorder_indices(
                inner_axis_order, axlist)
            vals = vals.transpose(transpose_idxs)

        newdata[k]['values'] = vals

    newdata = newdata.sanitize()
    newdata.validate()
    return newdata


def meshgrid_to_datadict(data: MeshgridDataDict) -> DataDict:
    """
    Make a DataDict from a MeshgridDataDict by reshaping the data.

    :param data: input ``MeshgridDataDict``
    :return: flattened ``DataDict``
    """
    newdata = DataDict(**data.structure(add_shape=False))
    for k, v in data.data_items():
        val = v['values'].copy().reshape(-1)
        newdata[k]['values'] = val

    newdata = newdata.sanitize()
    newdata.validate()
    return newdata
