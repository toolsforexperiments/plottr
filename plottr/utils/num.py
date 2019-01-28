"""num.py

Tools for numerical operations.
"""
from typing import Sequence, Tuple, Union, List
import numpy as np

INTTYPES = [int, np.int, np.int16, np.int32, np.int64]
FLOATTYPES = [float, np.float, np.float16, np.float32, np.float64,
              complex, np.complex, np.complex64, np.complex128]
NUMTYPES = INTTYPES + FLOATTYPES


def largest_numtype(arr: np.ndarray) -> Union[None, type]:
    """
    Get the largest numerical type present in an array.
    :param arr: input array
    :return: type if possible. None if no numeric data in array.
    """
    types = {type(a) for a in np.array(arr).flatten()}
    curidx = -1
    for t in types:
        if t in NUMTYPES:
            idx = NUMTYPES.index(t)
            if idx > curidx:
                curidx = idx
    if curidx > -1:
        return NUMTYPES[curidx]
    else:
        return None


def _are_close(a, b, rtol=1e-8):
    return np.isclose(a, b, rtol=rtol)


def _are_equal(a, b):
    return a == b


def _is_invalid(a):
    isnone = a == None
    if a.dtype in FLOATTYPES:
        isnan = np.isnan(a)
    else:
        isnan = np.zeros(a.shape, dtype=bool)
    return isnone | isnan


def _are_invalid(a, b):
    return _is_invalid(a) & _is_invalid(b)


def arrays_equal(a: np.ndarray, b: np.ndarray,
                 rtol=1e-8) -> bool:
    """Check if two numpy arrays are equal, content-wise.

    Perform the following checks:
    * actual equality of elements
    * approximate equality to a certain degree of relative accuracy (for floats)
    * invalid entries (capturing both ``None`` and ``np.nan``; all treated as
      equally invalid).

    Element-wise comparison is ``True`` if any of the conditions are ``True``.

    :param a: 1st numpy array
    :param b: 2nd numpy array
    :return: ``True``, if all element-wise checks are ``True``. ``False``
             otherwise.
    :raises: ``ValueError`` if shapes of ``a`` and ``b`` don't match.
    """
    if a.shape != b.shape:
        raise ValueError('Shapes are not equal.')

    close = np.zeros(a.shape, dtype=bool)
    if a.dtype in FLOATTYPES and b.dtype in FLOATTYPES:
        close = _are_close(a, b, rtol=rtol)

    equal = _are_equal(a, b)
    invalid = _are_invalid(a, b)

    return np.all(equal | close | invalid)


def array1d_to_meshgrid(arr: Sequence, target_shape: Tuple[int],
                        copy: bool = True) -> np.ndarray:
    """
    reshape an array to a target shape.

    If target shape is larger than the array, fill with invalids
    (``nan`` for float and complex dtypes, ``None`` otherwise).
    If target shape is smaller than the array, cut off the end.

    :param arr: input array
    :param target_shape: desired output shape
    :param copy: whether to make a copy before the operation.
    :return: re-shaped array.
    """
    if not isinstance(arr, np.ndarray):
        arr = np.array(arr)
    if copy:
        arr = arr.copy()
    arr = arr.reshape(-1)

    newsize = np.prod(target_shape)
    if newsize < arr.size:
        arr = arr[:newsize]
    elif newsize > arr.size:
        if arr.dtype in FLOATTYPES:
            fill = np.zeros(newsize - arr.size) * np.nan
        else:
            fill = np.array((newsize - arr.size) * [None])
        arr = np.append(arr, fill)

    return arr.reshape(target_shape)


def find_direction_period(vals: np.ndarray, ignore_last: bool = False) \
        -> Union[None, int]:
    """
    Find the period with which the values in an array change direction.

    :param vals: the axes values (1d array)
    :param ignore_last: if True, we'll ignore the last value when determining
                        if the period is unique (useful for incomplete data),
    :return: None if we could not determine a unique period.
             The period, i.e., the number of elements after which
             the more common direction is changed.
    """
    direction = np.sign(vals[1:] - vals[:-1])
    ups = np.where(direction == 1)[0]
    downs = np.where(direction == -1)[0]

    if len(ups) > len(downs):
        switches = downs
    else:
        switches = ups

    if len(switches) == 0:
        return vals.size
    elif len(switches) == 1:
        if switches[0] >= (vals.size / 2.) - 1:
            return switches[0] + 1
        else:
            return None

    if switches[-1] < vals.size - 1:
        switches = np.append(switches, vals.size-1)
    periods = (switches[1:] - switches[:-1])

    if ignore_last and periods[-1] < periods[0]:
        periods = periods[:-1]

    if len(set(periods)) > 1:
        return None
    elif len(periods) == 0:
        return vals.size
    else:
        return int(periods[0])


def guess_grid_from_sweep_direction(**axes: np.ndarray) \
        -> Union[None, Tuple[List[str], Tuple[int]]]:
    """
    Try to determine order and shape of a set of axes data
    (such as flattened meshgrid data).

    Analyzes the periodicity (in sweep direction) of the given set of axes
    values, and use that information to infer the shape of the dataset,
    and the order of the axes, given from slowest to fastest.

    :param axes: all axes values as keyword args, given as 1d numpy arrays.
    :return: None, if we cannot infer a shape that makes sense.
             Sorted list of axes names, and shape tuple for the dataset.
    :raises: `ValueError` for incorrect input
    """
    periods = []
    names = []
    size = None

    if len(axes) < 1:
        raise ValueError("Empty input.")

    for name, vals in axes.items():
        if len(np.array(vals).shape) > 1:
            raise ValueError(
                f"Expect 1-dimensional axis data, not {np.array(vals).shape}")
        if size is None:
            size = np.array(vals).size
        else:
            if size != np.array(vals).size:
                raise ValueError("Non-matching array sizes.")

        period = find_direction_period(vals, ignore_last=True)
        if period is not None:
            periods.append(period)
            names.append(name)
        else:
            return None

    order = np.argsort(periods)
    periods = np.array(periods)[order]
    names = np.array(names)[order]

    divisor = 1
    for i, p in enumerate(periods.copy()):

        # need to make sure that incomplete grids work.
        # for incomplete grids, the period of the outermost (here: last) axis
        # is by definition not yet complete --> compensate for that.
        if i + 1 == periods.size and periods[i] % divisor > 0:
            periods[i] = periods[i] // divisor + 1
        else:
            periods[i] //= divisor
        divisor *= int(periods[i])

    # incomplete grids can lack at most <slowest period - 1> elements.
    if (divisor < size) or (divisor > (size + divisor//periods[-1] - 1)):
        return None

    # in returning, we go back to standard order, i.e., slow->fast.
    return names[::-1].tolist(), tuple(periods[::-1])
