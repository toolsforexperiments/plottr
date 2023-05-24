"""
datadict.py :

Data classes we use throughout the plottr package, and tools to work on them.
"""
import warnings
import copy as cp
import re
import pandas as pd
import numpy as np
from functools import reduce
from typing import List, Tuple, Dict, Sequence, Union, Any, Iterator, Optional, TypeVar

from plottr.utils import num, misc


__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


# TODO: functionality that returns axes values given a set of slices.
# TODO: an easier way to access data and meta values.
#       maybe with getattr/setattr?
# TODO: direct slicing of full datasets. implement getitem/setitem?
# TODO: feature to compare if datadicts are equal not fully tested yet.


def is_meta_key(key: str) -> bool:
    """Checks if ``key`` is meta information.

    :param key: The ``key`` we are checking.
    :return: ``True`` if it is, ``False`` if it isn't.
    """
    if key[:2] == '__' and key[-2:] == '__':
        return True
    else:
        return False


def meta_key_to_name(key: str) -> str:
    """
    Converts a meta data key to just the name.
    E.g: for ``key``: "__meta__" returns "meta"

    :param key: The key that is being converted
    :return: The name of the key.
    :raises: ``ValueError`` if the ``key`` is not a meta key.


    """

    if is_meta_key(key):
        return key[2:-2]
    else:
        raise ValueError(f'{key} is not a meta key.')


def meta_name_to_key(name: str) -> str:
    """
    Converts ``name`` into a meta data key. E.g: "meta" gets converted to "__meta__"

    :param name: The name that is being converted.
    :return: The meta data key based on ``name``.
    """
    return '__' + name + '__'


T = TypeVar('T', bound='DataDictBase')


class GriddingError(ValueError):
    pass


class DataDictBase(dict):
    """
    Simple data storage class that is based on a regular dictionary.

    This base class does not make assumptions about the structure of the
    values. This is implemented in inheriting classes.
    """

    def __init__(self, **kw: Any):
        super().__init__(self, **kw)

    def __eq__(self, other: object) -> bool:
        """Check for content equality of two datadicts."""
        if not isinstance(other, DataDictBase):
            return False
        else:
            return datasets_are_equal(self, other)

    def __repr__(self) -> str:
        ret = ""
        for i, dn in enumerate(self.dependents()):
            if i > 0:
                ret += "\n"
            ret += f"{self.label(dn)}: {self[dn]['values'].shape}"
            for ax in self.axes(dn):
                ret += f"\n  \u2319 {self.label(ax)}: {self[ax]['values'].shape}"
        return ret

    # Assignment and retrieval of data and meta data

    @staticmethod
    def _is_meta_key(key: str) -> bool:
        return is_meta_key(key)

    @staticmethod
    def _meta_key_to_name(key: str) -> str:
        return meta_key_to_name(key)

    @staticmethod
    def _meta_name_to_key(name: str) -> str:
        return meta_name_to_key(name)

    @staticmethod
    def to_records(**data: Any) -> Dict[str, np.ndarray]:
        """Convert data to records that can be added to the ``DataDict``.
        All data is converted to np.array, and reshaped such that the first dimension of all resulting
        arrays have the same length (chosen to be the smallest possible number
        that does not alter any shapes beyond adding a length-1 dimension as
        first dimension, if necessary).

        If a data field is given as ``None``, it will be converted to ``numpy.array([numpy.nan])``.

        :param data: keyword arguments for each data field followed by data.
        :returns: Dictionary with properly shaped data.
        """
        records: Dict[str, np.ndarray] = {}

        seqtypes = (np.ndarray, tuple, list)
        nantypes = (type(None), )

        for k, v in data.items():
            if isinstance(v, seqtypes):
                records[k] = np.array(v)
            elif isinstance(v, nantypes):
                records[k] = np.array([np.nan])
            else:
                records[k] = np.array([v])

        possible_nrecords = {}
        for k, v in records.items():
            possible_nrecords[k] = [1, v.shape[0]]

        commons = []
        for k, v in possible_nrecords.items():
            for n in v:
                if n in commons:
                    continue
                is_common = True
                for kk, vv in possible_nrecords.items():
                    if n not in vv:
                        is_common = False
                if is_common:
                    commons.append(n)

        nrecs = max(commons)

        for k, v in records.items():
            shp = v.shape
            if nrecs == 1 and shp[0] > 1:
                newshp = tuple([1] + list(shp))
                records[k] = v.reshape(newshp)
        return records

    def data_items(self) -> Iterator[Tuple[str, Dict[str, Any]]]:
        """
        Generator for data field items.

        Like dict.items(), but ignores meta data.

        :return: Generator yielding first the key of the data field and second its value.
        """
        for k, v in self.items():
            if not self._is_meta_key(k):
                yield k, v

    def meta_items(self, data: Union[str, None] = None,
                   clean_keys: bool = True) -> Iterator[Tuple[str, Dict[str, Any]]]:
        """
        Generator for meta items.

        Like dict.items(), but yields `only` meta entries.
        The keys returned do not contain the underscores used internally.

        :param data: If ``None`` iterate over global meta data.
                     If it's the name of a data field, iterate over the meta
                     information of that field.
        :param clean_keys: If `True`, remove the underscore pre/suffix.
        :return: Generator yielding first the key of the data field and second its value.

        """
        if data is None:
            for k, v in self.items():
                if self._is_meta_key(k):
                    if clean_keys:
                        n = self._meta_key_to_name(k)
                    else:
                        n = k
                    yield n, v

        else:
            for k, v in self[data].items():
                if self._is_meta_key(k):
                    if clean_keys:
                        n = self._meta_key_to_name(k)
                    else:
                        n = k
                    yield n, v

    def data_vals(self, key: str) -> np.ndarray:
        """
        Return the data values of field ``key``.

        Equivalent to ``DataDict['key'].values``.

        :param key: Name of the data field.
        :return: Values of the data field.
        """
        if self._is_meta_key(key):
            raise ValueError(f"{key} is a meta key.")
        return self[key].get('values', np.array([]))

    def has_meta(self, key: str) -> bool:
        """Check whether meta field exists in the dataset.

        :return: ``True`` if it exists, ``False`` if it doesn't.
        """
        k = self._meta_name_to_key(key)
        if k in self:
            return True
        else:
            for key, field_dict in self.data_items():
                if k in field_dict:
                    return True
            return False

    def meta_val(self, key: str, data: Union[str, None] = None) -> Any:
        """
        Return the value of meta field ``key`` (given without underscore).

        :param key: Name of the meta field.
        :param data: ``None`` for global meta; name of data field for data meta.
        :return: The value of the meta information.
        """
        k = self._meta_name_to_key(key)
        if data is None:
            return self[k]
        else:
            return self[data][k]

    def add_meta(self, key: str, value: Any, data: Union[str, None] = None) -> None:
        """
        Add meta info to the dataset.

        If the key already exists, meta info will be overwritten.

        :param key: Name of the meta field (without underscores).
        :param value: Value of the meta information.
        :param data: If ``None``, meta will be global; otherwise assigned to
                     data field ``data``.

        """
        key = self._meta_name_to_key(key)
        if data is None:
            self[key] = value
        else:
            self[data][key] = value

    set_meta = add_meta

    def delete_meta(self, key: str, data: Union[str, None] = None) -> None:
        """
        Deletes specific meta data.

        :param key: Name of the meta field to remove.
        :param data: If ``None``, this affects global meta; otherwise remove
                     from data field ``data``.

        """
        key = self._meta_name_to_key(key)
        if data is None:
            del self[key]
        else:
            del self[data][key]

    def clear_meta(self, data: Union[str, None] = None) -> None:
        """
        Deletes all meta data.

        :param data: If not ``None``, delete all meta only from specified data field ``data``.
                     Else, deletes all top-level meta, as well as meta for all data fields.

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
            data_meta_list = [m for m, _ in self.meta_items(data)]
            for m in data_meta_list:
                self.delete_meta(m, data)

    def extract(self: T, data: List[str], include_meta: bool = True,
                copy: bool = True, sanitize: bool = True) -> T:
        """
        Extract data from a dataset.

        Return a new datadict with all fields specified in ``data`` included.
        Will also take any axes fields along that have not been explicitly
        specified. Will return empty if ``data`` consists of only axes fields.

        :param data: Data field or list of data fields to be extracted.
        :param include_meta: If ``True``, include the global meta data.
                             data meta will always be included.
        :param copy: If ``True``, data fields will be `deep copies <https://docs.python.org/3/library/copy.html>`__
                     of the original.
        :param sanitize: If ``True``, will run DataDictBase.sanitize before
                         returning.
        :return: New DataDictBase containing only requested fields.
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
    def same_structure(*data: T,
                       check_shape: bool = False) -> bool:
        """
        Check if all supplied DataDicts share the same data structure
        (i.e., dependents and axes).

        Ignores meta data and values. Checks also for matching shapes if
        `check_shape` is `True`.

        :param data: The data sets to compare.
        :param check_shape: Whether to include shape check in the comparison.
        :return: ``True`` if the structure matches for all, else ``False``.
        """
        if len(data) < 2:
            return True

        def empty_structure(d: T) -> T:
            s = misc.unwrap_optional(d.structure(include_meta=False, add_shape=check_shape))
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

    def structure(self: T, add_shape: bool = False,
                  include_meta: bool = True,
                  same_type: bool = False,
                  remove_data: Optional[List[str]] = None) -> Optional[T]:
        """
        Get the structure of the DataDict.

        Return the datadict without values (`value` omitted in the dict).

        :param add_shape: Deprecated -- ignored.
        :param include_meta: If `True`, include the meta information in
                             the returned dict.
        :param same_type: If `True`, return type will be the one of the
                          object this is called on. Else, DataDictBase.
        :param remove_data: any data fields listed will be removed from
                            the result, also when listed in any axes.

        :return: The DataDict containing the structure only. The exact type
                     is the same as the type of ``self``.

        """
        if add_shape:
            warnings.warn("'add_shape' is deprecated and will be ignored",
                          DeprecationWarning)
        add_shape = False

        if remove_data is None:
            remove_data = []

        if self.validate():
            s = self.__class__()
            for n, v in self.data_items():
                if n not in remove_data:
                    v2 = v.copy()
                    v2.pop('values')
                    s[n] = cp.deepcopy(v2)
                    if 'axes' in s[n]:
                        for r in remove_data:
                            if r in s[n]['axes']:
                                i = s[n]['axes'].index(r)
                                s[n]['axes'].pop(i)

            if include_meta:
                for n, v in self.meta_items():
                    s.add_meta(n, v)
            else:
                s.clear_meta()

            if same_type:
                s = self.__class__(**s)

            return s
        return None
    

    def nbytes(self, name: Optional[str]=None) -> Optional[int]:
        """Get the size of data.
        
        :param name: Name of the data field. if none, return size of 
            entire datadict.
        :return: size in bytes.
        """
        if self.validate():
            if name is None:
                return sum([v['values'].size * v['values'].itemsize 
                            for _, v in self.data_items()])
            else:
                return self.data_vals(name).size * self.data_vals(name).itemsize
        
        return None


    def label(self, name: str) -> Optional[str]:
        """
        Get the label for a data field. If no label is present returns the
        name of the data field as the label. If a unit is present, it will
        be appended at the end in brackets: "label (unit)".

        :param name: Name of the data field.
        :return: Labelled name.
        """
        if self.validate():
            if name not in self:
                raise ValueError("No field '{}' present.".format(name))
            
            if self[name]['label'] != '':
                n = self[name]['label']
            else:
                n = name

            if self[name]['unit'] != '':
                n += ' ({})'.format(self[name]['unit'])

            return n
        return None

    def axes_are_compatible(self) -> bool:
        """
        Check if all dependent data fields have the same axes.

        This includes axes order.

        :return: ``True`` or ``False``.
        """
        axes = []
        for i, d in enumerate(self.dependents()):
            if i == 0:
                axes = self.axes(d)
            else:
                if self.axes(d) != axes:
                    return False
        return True

    def axes(self, data: Union[Sequence[str], str, None] = None) -> List[str]:
        """
        Return a list of axes.

        :param data: if ``None``, return all axes present in the dataset,
                     otherwise only the axes of the dependent ``data``.
        :return: The list of axes.
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
                dataseq: Sequence[str] = (data,)
            else:
                dataseq = data
            for n in dataseq:
                if 'axes' not in self[n]:
                    continue
                for m in self[n]['axes']:
                    if m not in lst and self[m].get('axes', []) == []:
                        lst.append(m)

        return lst

    def dependents(self) -> List[str]:
        """
        Get all dependents in the dataset.

        :return: A list of the names of dependents.
        """
        ret = []
        for n, v in self.data_items():
            if len(v.get('axes', [])) != 0:
                ret.append(n)
        return ret

    def shapes(self) -> Dict[str, Tuple[int, ...]]:
        """
        Get the shapes of all data fields.

        :return: A dictionary of the form ``{key : shape}``, where shape is the
                 np.shape-tuple of the data with name ``key``.

        """
        shapes = {}
        for k, v in self.data_items():
            shapes[k] = np.array(self.data_vals(k)).shape

        return shapes

    # validation and sanitizing

    def validate(self) -> bool:
        """
        Check the validity of the dataset.

        Checks performed:
            * All axes specified with dependents must exist as data fields.

        Other tasks performed:
            * ``unit`` keys are created if omitted.
            * ``label`` keys are created if omitted.
            * ``shape`` meta information is updated with the correct values
              (only if present already).

        :return: ``True`` if valid, ``False`` if invalid.
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

            if 'label' not in v:
                v['label'] = ''

            vals = v.get('values', [])
            if type(vals) not in [np.ndarray, np.ma.core.MaskedArray]:
                vals = np.array(vals)
            v['values'] = vals

        if msg != '\n':
            raise ValueError(msg)

        return True

    def remove_unused_axes(self: T) -> T:
        """
        Removes axes not associated with dependents.

        :return: Cleaned dataset.
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

    def sanitize(self: T) -> T:
        """
        Clean-up tasks:
            * Removes unused axes.

        :return: Sanitized dataset.
        """
        return self.remove_unused_axes()

    # axes order tools

    def reorder_axes_indices(self, name: str,
                             **pos: int) -> Tuple[Tuple[int, ...], List[str]]:
        """
        Get the indices that can reorder axes in a given way.

        :param name: Name of the data field of which we want to reorder axes.
        :param pos: New axes position in the form ``axis_name = new_position``.
                    Non-specified axes positions are adjusted automatically.
        :return: The tuple of new indices, and the list of axes names in the
                 new order.

        """
        axlist = self.axes(name)
        order = misc.reorder_indices_from_new_positions(axlist, **pos)
        return order, [axlist[i] for i in order]

    def reorder_axes(self: T, data_names: Union[str, Sequence[str], None] = None,
                     **pos: int) -> T:
        """
        Reorder data axes.

        :param data_names: Data name(s) for which to reorder the axes.
                           If None, apply to all dependents.
        :param pos: New axes position in the form ``axis_name = new_position``.
                    Non-specified axes positions are adjusted automatically.

        :return: Dataset with re-ordered axes.
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

    def copy(self: T) -> T:
        """
        Make a copy of the dataset.

        :return: A copy of the dataset.
        """
        return cp.deepcopy(self)

    def astype(self: T, dtype: np.dtype) -> T:
        """
        Convert all data values to given dtype.

        :param dtype: np dtype.
        :return: Copy of the dataset, with values as given type.
        """
        ret = self.copy()
        for k, v in ret.data_items():
            vals = v['values']
            if type(v['values']) not in [np.ndarray, np.ma.core.MaskedArray]:
                vals = np.array(v['values'])
            ret[k]['values'] = vals.astype(dtype)

        return ret

    def mask_invalid(self: T) -> T:
        """
        Mask all invalid data in all values.
        :return: Copy of the dataset with invalid entries (nan/None) masked.
        """
        ret = self.copy()
        for d, _ in self.data_items():
            arr = self.data_vals(d)
            vals = np.ma.masked_where(num.is_invalid(arr), arr, copy=True)
            try:
                vals.fill_value = np.nan
            except TypeError:
                vals.fill_value = -9999
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

        # FIXME: remove shape
        s = misc.unwrap_optional(self.structure(add_shape=False))
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

    def append(self, newdata: "DataDict") -> None:
        """
        Append a datadict to this one by appending data values.

        :param newdata: DataDict to append.
        :raises: ``ValueError``, if the structures are incompatible.
        """
        if not DataDictBase.same_structure(self, newdata):
            raise ValueError('Incompatible data structures.')

        newvals = {}
        for k, v in newdata.data_items():
            if isinstance(self[k]['values'], list) and isinstance(
                    v['values'], list):
                newvals[k] = self[k]['values'] + v['values']
            else:
                newvals[k] = np.append(
                    self[k]['values'],
                    v['values'],
                    axis=0
                )

        # only actually
        for k, v in newvals.items():
            self[k]['values'] = v

    def add_data(self, **kw: Any) -> None:
        # TODO: fill non-given data with nan or none
        """
        Add data to all values. new data must be valid in itself.

        This method is useful to easily add data without needing to specify
        meta data or dependencies, etc.

        :param kw: one array per data field (none can be omitted).
        """
        dd = misc.unwrap_optional(self.structure(same_type=True))
        for name, _ in dd.data_items():
            if name not in kw:
                kw[name] = None

        records = self.to_records(**kw)
        for name, datavals in records.items():
            dd[name]['values'] = datavals

        if dd.validate():
            nrecords = self.nrecords()
            if nrecords is not None and nrecords > 0:
                self.append(dd)
            else:
                for key, val in dd.data_items():
                    self[key]['values'] = val['values']
            self.validate()

    # shape information and expansion

    def nrecords(self) -> Optional[int]:
        """
        Gets the number of records in the dataset.

        :return: The number of records in the dataset.
        """
        self.validate()
        for _, v in self.data_items():
            return len(v['values'])
        return None

    def _inner_shapes(self) -> Dict[str, Tuple[int, ...]]:
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
        struct = misc.unwrap_optional(self.structure(add_shape=False))
        ret = DataDict(**struct)

        if self.is_expanded():
            return self.copy()

        ishp = self._inner_shapes()
        size = max([int(np.prod(s)) for s in ishp.values()])

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

    def sanitize(self) -> "DataDict":
        """
        Clean-up.

        Beyond the tasks of the base class ``DataDictBase``:
            * remove invalid entries as far as reasonable.

        :return: sanitized DataDict.
        """
        ret = super().sanitize()
        return ret.remove_invalid_entries()

    def remove_invalid_entries(self) -> 'DataDict':
        """
        Remove all rows that are ``None`` or ``np.nan`` in *all* dependents.

        :return: The cleaned DataDict.
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
                datavals = self.data_vals(d)
                rows = datavals.reshape(-1, int(np.prod(ishp[d])))

            _idxs: np.ndarray = np.array([])

            # get indices of all rows that are fully None
            if len(ishp[d]) == 0:
                _newidxs = np.atleast_1d(np.asarray(rows is None)).nonzero()[0]
            else:
                _newidxs = np.atleast_1d(np.asarray(np.all(rows is None, axis=-1))).nonzero()[0]
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
    Implementation of DataDictBase meant to be used for when the axes form
    a grid on which the dependent values reside.

    It enforces that all dependents have the same axes and all shapes need to be identical.
    """

    def shape(self) -> Union[None, Tuple[int, ...]]:
        """
        Return the shape of the meshgrid.

        :returns: The shape as tuple. ``None`` if no data in the set.
        """
        for d, _ in self.data_items():
            return np.array(self.data_vals(d)).shape
        return None

    def validate(self) -> bool:
        """
        Validation of the dataset.

        Performs the following checks:
        * All dependents must have the same axes.
        * All shapes need to be identical.

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

        data_items = dict(self.data_items())

        for n, v in data_items.items():
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

            if 'axes' in v:
                for axis_num, na in enumerate(v['axes']):
                    # check that the data of the axes matches its use
                    # if data present
                    axis_data = data_items[na]['values']

                    # for the data to be a valid meshgrid, we need to have an increase/decrease along each
                    # axis that contains data.
                    if axis_data.size > 0:
                        # if axis length is 1, then we cannot infer anything about grids yet

                        try:
                            if axis_data.shape[axis_num] > 1:
                                steps = np.unique(np.sign(np.diff(axis_data, axis=axis_num)))
                                if 0 in steps:
                                    msg += (f"Malformed data: {na} is expected to be {axis_num}th "
                                            "axis but has no variation along that axis.\n")
                                if steps.size > 1:
                                    msg += (f"Malformed data: axis {na} is not monotonous.\n")
                        
                        # can happen if we have bad shapes. but that should already have been caught.
                        except IndexError:
                            pass

            if '__shape__' in v:
                v['__shape__'] = shp

            if msg != '\n':
                raise ValueError(msg)

        return True

    def reorder_axes(self, data_names: Union[str, Sequence[str], None] = None,
                     **pos: int) -> 'MeshgridDataDict':
        """
        Reorder the axes for all data.

        This includes transposing the data, since we're on a grid.

        :param data_names: Which dependents to include. if None are given,
                           all dependents are included.
        :param pos: New axes position in the form ``axis_name = new_position``.
                    non-specified axes positions are adjusted automatically.

        :return: Dataset with re-ordered axes.
        """
        if data_names is None:
            data_names = self.dependents()
        if isinstance(data_names, str):
            data_names = [data_names]

        transposed = []
        ret: "MeshgridDataDict" = self.copy()

        for n in data_names:
            neworder, newaxes = self.reorder_axes_indices(n, **pos)
            ret[n]['axes'] = newaxes
            ret[n]['values'] = self[n]['values'].transpose(neworder)
            for ax in self.axes(n):
                if ax not in transposed:
                    ret[ax]['values'] = self[ax]['values'].transpose(neworder)
                    transposed.append(ax)

        ret.validate()
        return ret
    
    def mean(self, axis: str) -> 'MeshgridDataDict':
        """Take the mean over the given axis.
        
        :param axis: which axis to take the average over.
        :return: data, averaged over ``axis``.
        """
        return _mesh_mean(self, axis)
    
    def slice(self, **kwargs: Dict[str, Union[slice, int]]) -> 'MeshgridDataDict':
        """Return a N-d slice of the data.

        :param kwargs: slicing information in the format ``axis: spec``, where
            ``spec`` can be a ``slice`` object, or an integer (usual slicing 
            notation).
        :return: sliced data (as a copy)
        """
        return _mesh_slice(self, **kwargs)
    
    def squeeze(self) -> None:
        """Remove size-1 dimensions."""
        raise NotImplementedError


def _mesh_mean(data: MeshgridDataDict, ax: str) -> MeshgridDataDict:
    """Average gridded data over one axis.
    
    :param data: input data
    :param ax: axis over which the average is performed; this dimension
        is removed from the result.
    :return: averaged data
    """
    iax = data.axes().index(ax)
    new_data = data.structure(remove_data=[ax])
    assert isinstance(new_data, MeshgridDataDict)

    for d, v in data.data_items():
        if d in new_data:
            new_data[d]['values'] = data.data_vals(d).mean(axis=iax)
    new_data.validate()
    return new_data


def _mesh_slice(data: MeshgridDataDict, **kwargs: Dict[str, Union[slice, int]]) -> MeshgridDataDict:
    """Return a N-d slice of the data.
    
    :param data: input data
    :param kwargs: slicing information in the format ``axis = spec``, where
        ``spec`` can be a ``slice`` object, or an integer (usual slicing 
        notation).
    :return: sliced data
    """
    slices: List[Any] = [np.s_[::] for a in data.axes()]
    for ax, val in kwargs.items():
        i = data.axes().index(ax)
        slices[i] = val
    ret = data.structure()
    assert isinstance(ret, MeshgridDataDict)

    for d, _ in data.data_items():
        ret[d]['values'] = data[d]['values'][tuple(slices)]
    ret.validate()
    return ret


# Tools for converting between different data types

def guess_shape_from_datadict(data: DataDict) -> \
        Dict[str, Union[None, Tuple[List[str], Tuple[int, ...]]]]:
    """
    Try to guess the shape of the datadict dependents from the axes values.

    :param data: Dataset to examine.
    :return: A dictionary with the dependents as keys, and inferred shapes as
             values. Value is ``None``, if the shape could not be inferred.
    """

    shapes = {}
    for d in data.dependents():
        axnames = data.axes(d)
        axes: Dict[str, np.ndarray] = {}
        for a in axnames:
            axdata = data.data_vals(a)
            axes[a] = axdata
        shapes[d] = num.guess_grid_from_sweep_direction(**axes)

    return shapes


def datadict_to_meshgrid(data: DataDict,
                         target_shape: Union[Tuple[int, ...], None] = None,
                         inner_axis_order: Union[None, Sequence[str]] = None,
                         use_existing_shape: bool = False) \
        -> MeshgridDataDict:
    """
    Try to make a meshgrid from a dataset.

    :param data: Input DataDict.
    :param target_shape: Target shape. If ``None`` we use
        ``guess_shape_from_datadict`` to infer.
    :param inner_axis_order: If axes of the datadict are not specified in the
        'C' order (1st the slowest, last the fastest axis) then the
        'true' inner order can be specified as a list of axes names, which has
        to match the specified axes in all but order. The data is then
        transposed to conform to the specified order.

        .. note::
            If this is given, then ``target_shape`` needs to be given in
            in the order of this inner_axis_order. The output data will keep the
            axis ordering specified in the `axes` property.

    :param use_existing_shape: if ``True``, simply use the shape that the data
        already has. For numpy-array data, this might already be present.
        If ``False``, flatten and reshape.
    :raises: GriddingError (subclass of ValueError) if the data cannot be gridded.
    :returns: The generated ``MeshgridDataDict``.
    """

    # if the data is empty, return empty MeshgridData
    if len([k for k, _ in data.data_items()]) == 0:
        return MeshgridDataDict()

    if not data.axes_are_compatible():
        raise GriddingError('Non-compatible axes, cannot grid that.')

    if not use_existing_shape and data.is_expandable():
        data = data.expand()
    elif use_existing_shape:
        target_shape = list(data.shapes().values())[0]

    # guess what the shape likely is.
    if target_shape is None:
        shp_specs = guess_shape_from_datadict(data)
        shps = set(order_shape[1] if order_shape is not None
                   else None for order_shape in shp_specs.values())
        if len(shps) > 1:
            raise GriddingError('Cannot determine unique shape for all data.')
        ret = list(shp_specs.values())[0]
        if ret is None:
            raise GriddingError('Shape could not be inferred.')
        # the guess-function returns both axis order as well as shape.
        inner_axis_order, target_shape = ret

    # construct new data
    newdata = MeshgridDataDict(**misc.unwrap_optional(data.structure(add_shape=False)))
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

    :param data: Input ``MeshgridDataDict``.
    :return: Flattened ``DataDict``.
    """
    newdata = DataDict(**misc.unwrap_optional(data.structure(add_shape=False)))
    for k, v in data.data_items():
        val = v['values'].copy().reshape(-1)
        newdata[k]['values'] = val

    newdata = newdata.sanitize()
    newdata.validate()
    return newdata


# Tools for manipulating and transforming data

def _find_replacement_name(ddict: DataDictBase, name: str) -> str:
    """
    Find a replacement name for a data field that already exists in a
    datadict.

    Appends '-<index>' to the name.

    :param ddict: Datadict that contains the already existing field.
    :param name: The name that needs to be replaced.
    :return: A suitable replacement.
    """
    if name not in ddict:
        return name
    else:
        idx = 0
        newname = name + f"_{idx}"
        while newname in ddict:
            idx += 1
            newname = name + f"_{idx}"
        return newname


def combine_datadicts(*dicts: DataDict) -> Union[DataDictBase, DataDict]:
    """
    Try to make one datadict out of multiple.

    Basic rules:

    - We try to maintain the input type.
    - Return type is 'downgraded' to DataDictBase if the contents are not
      compatible (i.e., different numbers of records in the inputs).

    :returns: Combined data.
    """

    # TODO: deal correctly with MeshGridData when combined with other types
    # TODO: should we strictly copy all values?
    # TODO: we should try to consolidate axes as much as possible. Currently
    #   axes in the return can be separated even if they match (caused
    #   by earlier mismatches)

    ret = None
    rettype = None

    for d in dicts:
        if ret is None:
            ret = d.copy()
            rettype = type(d)

        else:

            # if we don't have a well defined number of records anymore,
            # need to revert the type to DataDictBase
            if hasattr(d, 'nrecords') and hasattr(ret, 'nrecords'):
                if d.nrecords() != ret.nrecords():
                    rettype = DataDictBase
            else:
                rettype = DataDictBase
            ret = rettype(**ret)

            # First, parse the axes in the to-be-added ddict.
            # if dimensions with same names are present already in the current
            # return ddict and are not compatible with what's to be added,
            # rename the incoming dimension.
            ax_map = {}
            for d_ax in d.axes():
                if d_ax in ret.axes():
                    if num.arrays_equal(d.data_vals(d_ax), ret.data_vals(d_ax)):
                        ax_map[d_ax] = d_ax
                    else:
                        newax = _find_replacement_name(ret, d_ax)
                        ax_map[d_ax] = newax
                        ret[newax] = d[d_ax]
                elif d_ax in ret.dependents():
                    newax = _find_replacement_name(ret, d_ax)
                    ax_map[d_ax] = newax
                    ret[newax] = d[d_ax]
                else:
                    ax_map[d_ax] = d_ax
                    ret[d_ax] = d[d_ax]

            for d_dep in d.dependents():
                if d_dep in ret:
                    newdep = _find_replacement_name(ret, d_dep)
                else:
                    newdep = d_dep

                dep_axes = [ax_map[ax] for ax in d[d_dep]['axes']]
                ret[newdep] = d[d_dep]
                ret[newdep]['axes'] = dep_axes

    if ret is None:
        ret = DataDict()
    else:
        ret.validate()

    return ret


def datastructure_from_string(description: str) -> DataDict:
    r"""Construct a DataDict from a string description.

    Examples:
        * ``"data[mV](x, y)"`` results in a datadict with one dependent ``data`` with unit ``mV`` and
          two independents, ``x`` and ``y``, that do not have units.

        * ``"data_1[mV](x, y); data_2[mA](x); x[mV]; y[nT]"`` results in two dependents,
          one of them depening on ``x`` and ``y``, the other only on ``x``.
          Note that ``x`` and ``y`` have units. We can (but do not have to) omit them when specifying
          the dependencies.

        * ``"data_1[mV](x[mV], y[nT]); data_2[mA](x[mV])"``. Same result as the previous example.

    Rules:
        We recognize descriptions of the form ``field1[unit1](ax1, ax2, ...); field1[unit2](...); ...``.

        * Field names (like ``field1`` and ``field2`` above) have to start with a letter, and may contain
          word characters.
        * Field descriptors consist of the name, optional unit (presence signified by square brackets),
          and optional dependencies (presence signified by round brackets).
        * Dependencies (axes) are implicitly recognized as fields (and thus have the same naming restrictions as field
          names).
        * Axes are separated by commas.
        * Axes may have a unit when specified as dependency, but besides the name, square brackets, and commas no other
          characters are recognized within the round brackets that specify the dependency.
        * In addition to being specified as dependency for a field,
          axes may be specified also as additional field without dependency,
          for instance to specify the unit (may simplify the string). For example,
          ``z1[x, y]; z2[x, y]; x[V]; y[V]``.
        * Units may only consist of word characters.
        * Use of unexpected characters will result in the ignoring the part that contains the symbol.
        * The regular expression used to find field descriptors is:
          ``((?<=\A)|(?<=\;))[a-zA-Z]+\w*(\[\w*\])?(\(([a-zA-Z]+\w*(\[\w*\])?\,?)*\))?``
    """

    description = description.replace(" ", "")

    data_name_pattern = r"[a-zA-Z]+\w*(\[\w*\])?"
    pattern = r"((?<=\A)|(?<=\;))" + data_name_pattern + r"(\((" + data_name_pattern + r"\,?)*\))?"
    r = re.compile(pattern)

    data_fields = []
    while (r.search(description)):
        match = r.search(description)
        if match is None: break
        data_fields.append(description[slice(*match.span())])
        description = description[match.span()[1]:]

    dd: Dict[str, Any] = dict()

    def analyze_field(df: str) -> Tuple[str, Optional[str], Optional[List[str]]]:
        has_unit = True if '[' in df and ']' in df else False
        has_dependencies = True if '(' in df and ')' in df else False

        name: str = ""
        unit: Optional[str] = None
        axes: Optional[List[str]] = None

        if has_unit:
            name = df.split('[')[0]
            unit = df.split('[')[1].split(']')[0]
            if has_dependencies:
                axes = df.split('(')[1].split(')')[0].split(',')
        elif has_dependencies:
            name = df.split('(')[0]
            axes = df.split('(')[1].split(')')[0].split(',')
        else:
            name = df

        if axes is not None and len(axes) == 0:
            axes = None
        return name, unit, axes

    for df in data_fields:
        name, unit, axes = analyze_field(df)

        # double specifying is only allowed for independents.
        # if an independent is specified multiple times, units must not collide
        # (but units do not have to be specified more than once)
        if name in dd:
            if 'axes' in dd[name] or axes is not None:
                raise ValueError(f'{name} is specified more than once.')
            if 'unit' in dd[name] and unit is not None and dd[name]['unit'] != unit:
                raise ValueError(f'conflicting units for {name}')

        dd[name] = dict()
        if unit is not None:
            dd[name]['unit'] = unit

        if axes is not None:
            for ax in axes:
                ax_name, ax_unit, ax_axes = analyze_field(ax)

                # we do not allow nested dependencies.
                if ax_axes is not None:
                    raise ValueError(f'{ax_name} is independent, may not have dependencies')

                # we can add fields implicitly from dependencies.
                # independents may be given both implicitly and explicitly, but only
                # when units don't collide.
                if ax_name not in dd:
                    dd[ax_name] = dict()
                    if ax_unit is not None:
                        dd[ax_name]['unit'] = ax_unit
                else:
                    if 'unit' in dd[ax_name] and ax_unit is not None and dd[ax_name]['unit'] != ax_unit:
                        raise ValueError(f'conflicting units for {ax_name}')

                if 'axes' not in dd[name]:
                    dd[name]['axes'] = []
                dd[name]['axes'].append(ax_name)

    return DataDict(**dd)

#: shortcut to :func:`.datastructure_from_string`.
str2dd = datastructure_from_string


def datasets_are_equal(a: DataDictBase, b: DataDictBase,
                       ignore_meta: bool = False) -> bool:
    """Check whether two datasets are equal.

    Compares type, structure, and content of all fields.

    :param a: First dataset.
    :param b: Second dataset.
    :param ignore_meta: If ``True``, do not verify if metadata matches.
    :returns: ``True`` or ``False``.
    """

    if not type(a) == type(b):
        return False

    if not a.same_structure(a, b):
        return False

    if not ignore_meta:
        # are all meta data of a also in b, and are they the same value?
        for k, v in a.meta_items():
            if k not in [kk for kk, vv in b.meta_items()]:
                return False
            elif b.meta_val(k) != v:
                return False

        # are all meta data of b also in a?
        for k, v in b.meta_items():
            if k not in [kk for kk, vv in a.meta_items()]:
                return False

    # check all data fields in a
    for dn, dv in a.data_items():

        # are all fields also present in b?
        if dn not in [dnn for dnn, dvv in b.data_items()]:
            return False

        # check if data is equal
        if not num.arrays_equal(
                np.array(a.data_vals(dn)),
                np.array(b.data_vals(dn)),
        ):
            return False

        if not ignore_meta:
            # check meta data
            for k, v in a.meta_items(dn):
                if k not in [kk for kk, vv in b.meta_items(dn)]:
                    return False
                elif v != b.meta_val(k, dn):
                    return False

    # only thing left to check is whether there are items in b but not a
    for dn, dv in b.data_items():
        if dn not in [dnn for dnn, dvv in a.data_items()]:
            return False

        if not ignore_meta:
            for k, v in b.meta_items(dn):
                if k not in [kk for kk, vv in a.meta_items(dn)]:
                    return False

    return True


def datadict_to_dataframe(data: DataDict) -> pd.DataFrame:
    """
    datadict_to_dataframe use data stored in DataDict return a copy in form pandas.DataFrame
    column labels are the names of variables
    row labels are the index of values in list
    ex.       x     y      z
          0   x1    y1     z1
          1   x2    y2     z2
          2   x3    y3     z3

    :param data: source data stored in Datadict form
    :return: copy of data stored in DataFrame form
    """
    # initialize parameter
    data_set = {}
    axe_ls = data.axes()
    dimension_check = True
    max_ele = 0

    # check for the dimension of Data
    for key, value in data.data_items():
        if np.shape(data.data_vals(key)) != np.shape(data.data_vals(axe_ls[0])):
            dimension_check = False

        if np.size(data.data_vals(key)) > max_ele:
            max_ele = np.size(data.data_vals(key))

    # if the dimension of all variables are the same, directly flat the array
    if dimension_check:
        for key, value in data.data_items():
            data_set[key] = (data.data_vals(key)).flatten()

    # if the dimension is different between variables, match their dimension to the highest one
    else:
        for key, value in data.data_items():
            repeated_time = int(max_ele/np.size(data.data_vals(key)))
            value_array = np.repeat(data.data_vals(key), repeated_time)
            data_set[key] = value_array.flatten('F')

    # convert organized data to DataFrame and return it
    return pd.DataFrame(data=data_set)

