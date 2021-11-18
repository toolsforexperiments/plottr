"""num.py

Tools for numerical operations.
"""
from typing import List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

from ..utils.misc import unwrap_optional

INTTYPES = [int, np.int16, np.int32, np.int64]
FLOATTYPES = [float, np.float16, np.float32, np.float64,
              complex, np.complex64, np.complex128]
NUMTYPES = INTTYPES + FLOATTYPES


def largest_numtype(arr: np.ndarray, include_integers: bool = True) \
        -> Union[None, type]:
    """
    Get the largest numerical type present in an array.
    :param arr: input array
    :param include_integers: whether to include int as possible return.
                             if ``False``, return will be float, if there's
                             only integers in the the data.
    :return: type if possible. None if no numeric data in array.
    """
    types = {type(a) for a in np.array(arr).flatten()}
    curidx = -1
    if include_integers:
        ok_types = NUMTYPES
    else:
        ok_types = FLOATTYPES

    for t in types:
        if t in ok_types:
            idx = ok_types.index(t)
            if idx > curidx:
                curidx = idx

    if curidx > -1:
        return ok_types[curidx]
    elif not include_integers and len(set(types).intersection(INTTYPES)) > 0:
        return float
    else:
        return None


def _are_close(a: np.ndarray, b: np.ndarray, rtol: float = 1e-8) -> Union[np.ndarray, np.bool_]:
    return np.isclose(a, b, rtol=rtol)


def _are_equal(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return a == b


def is_invalid(a: np.ndarray) -> np.ndarray:
    # really use == None to do an element wise
    # check for None
    isnone = a == None
    if a.dtype in FLOATTYPES:
        isnan = np.isnan(a)
    else:
        isnan = np.zeros(a.shape, dtype=bool)
    return isnone | isnan


def _are_invalid(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return is_invalid(a) & is_invalid(b)


def arrays_equal(a: np.ndarray, b: np.ndarray,
                 rtol: float = 1e-8, raise_shape_mismatch: bool = False) \
        -> bool:
    """Check if two numpy arrays are equal, content-wise.

    Perform the following checks:
    * actual equality of elements
    * approximate equality to a certain degree of relative accuracy (for floats)
    * invalid entries (capturing both ``None`` and ``np.nan``; all treated as
      equally invalid).

    Element-wise comparison is ``True`` if any of the conditions are ``True``.

    :param a: 1st numpy array
    :param b: 2nd numpy array
    :param rtol: relative uncertainty tolerance. see `numpy.isclose`.
    :param raise_shape_mismatch: if True, raise `ValueError` when shapes
                                 are unequal. If `False`, return `False` in that
                                 case.
    :return: `True`, if all element-wise checks are `True`. `False`
             otherwise.
    :raises: `ValueError` if shapes of `a` and `b` don't match
    """
    if a.shape != b.shape:
        if raise_shape_mismatch:
            raise ValueError('Shapes are not equal.')
        else:
            return False

    close: Union[np.ndarray, np.bool_] = np.zeros(a.shape, dtype=bool)
    if a.dtype in FLOATTYPES and b.dtype in FLOATTYPES:
        close = _are_close(a, b, rtol=rtol)

    equal = _are_equal(a, b)
    invalid = _are_invalid(a, b)

    return bool(np.all(equal | close | invalid))


def array1d_to_meshgrid(arr: Union[List, np.ndarray],
                        target_shape: Tuple[int, ...],
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
        localarr = np.array(arr)
    else:
        localarr = arr

    if copy:
        localarr = localarr.copy()
    localarr = localarr.reshape(-1)

    newsize = int(np.prod(target_shape))
    if newsize < localarr.size:
        localarr = localarr[:newsize]
    elif newsize > localarr.size:
        if localarr.dtype in FLOATTYPES:
            fill = np.zeros(newsize - localarr.size) * np.nan
        else:
            fill = np.array((newsize - localarr.size) * [None])
        localarr = np.append(localarr, fill)

    return localarr.reshape(target_shape)


def _find_switches(arr: np.ndarray,
                   rth: float = 25,
                   ztol: float = 1e-15) -> np.ndarray:
    arr_: np.ndarray = np.ma.MaskedArray(arr, is_invalid(arr))
    deltas = arr_[1:] - arr_[:-1]
    hi = np.percentile(arr[~is_invalid(arr)], 100.-rth)
    lo = np.percentile(arr[~is_invalid(arr)], rth)
    diff = np.abs(hi-lo)

    if not diff > ztol:
        return np.array([])

    # first step: suspected switches are where we have 'large' jumps in value.
    switch_candidates = np.where(np.abs(deltas) >= diff)[0]
    switch_candidates = switch_candidates[switch_candidates > 0]
    if not len(switch_candidates) > 0:
        return np.array([])

    # importantly: switches have to opposite to the sweep direction.
    # we check the sweep direction by looking at the values prior to the
    # first suspected switch
    sweep_direction = np.sign(np.mean(deltas[:switch_candidates[0]]))

    # real switches are then those where the delta is opposite to the sweep
    # direction.
    switch_candidate_vals = deltas[switch_candidates]
    switches = [s for (s, v) in zip(switch_candidates, switch_candidate_vals)
                if np.sign(v) == -sweep_direction]

    return np.array(switches)


def find_direction_period(vals: np.ndarray, ignore_last: bool = False) \
        -> Optional[float]:
    """
    Find the period with which the values in an array change direction.

    :param vals: the axes values (1d array)
    :param ignore_last: if True, we'll ignore the last value when determining
                        if the period is unique (useful for incomplete data),
    :return: None if we could not determine a unique period.
             The period, i.e., the number of elements after which
             the more common direction is changed.
    """
    switches = _find_switches(vals)

    # if there's no switch at all, no period is defined.
    if len(switches) == 0:
        return np.inf

    # if there was one switch there is a period only if the switch occurred
    # in the second half of the data
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
        -> Union[None, Tuple[List[str], Tuple[int, ...]]]:
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
    periods_list = []
    sorting: List[float] = []
    names_list = []
    size: Optional[int] = None

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

        # first step: find repeating patterns in the data.
        # record for each dimension in which interval it repeats.
        period = find_direction_period(vals, ignore_last=True)
        if period is not None:
            names_list.append(name)
            periods_list.append(period)

            # some dimensions will likely not have a finite period (because
            # there have been no repetitions (yet).
            # in those cases we try to make a guess as to which dimensions
            # are likely to be the more inner (i.e., faster changing) ones.
            # we do that by looking at how diverse the entries are.
            # more diverse -> more likely to be a fast axis.
            if period != np.inf:
                sorting.append(period)
            else:
                mean = vals.mean()
                std = np.std(vals)
                if std == 0:
                    cost = np.inf
                else:
                    if mean == 0:
                        mean = max(np.abs(vals.max()), np.abs(vals.min()))
                    cost = 1./np.abs(np.std(vals)/mean)
                sorting.append(size + cost)
        else:
            return None

    size = unwrap_optional(size)

    # invert the order. we work from fastest to slowest repetition period.
    order = np.argsort(sorting)
    periods = np.array(periods_list)[order]
    shape = periods.copy()
    names = np.array(names_list)[order]

    divisor = 1
    for i, p in enumerate(periods):

        # we need to treat the non-repeating dimensions correctly.
        # if there's a rest when diving on a dimension that has no defined period,
        # that means we have to add 1 to the period to get its length.
        # (typically it'll go from 0 to 1 then)
        if shape[i] == np.inf:
            if size % divisor > 0:
                shape[i] = int(size // divisor) + 1
            else:
                shape[i] = int(size // divisor)
        else:
            shape[i] //= divisor

        divisor *= int(shape[i])

    shape = shape.astype(int)

    # this is a sanity check.
    # at this point, `divisor` is the size of the full grid.
    # it cannot be smaller than the total size, but can be larger
    # for incomplete grids.
    if (divisor < size):
        return None

    # in returning, we go back to standard order, i.e., slow->fast.
    return names[::-1].tolist(), tuple(shape[::-1])


def crop2d_rows_cols(arr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Get row and col idxs that are completely invalid in a 2d array.

    :param arr: input array
    :return: the x (outer) and y (inner) indices at which the
             data ontains only invalid entries.
    :raises: ``ValueError`` if input is not a 2d ndarray.
    """
    if len(arr.shape) != 2:
        raise ValueError('input is not a 2d array.')

    invalids = is_invalid(arr)
    ys = np.where(np.all(invalids, axis=0))[0]
    xs = np.where(np.all(invalids, axis=1))[0]
    return xs, ys


def joint_crop2d_rows_cols(*arr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Get idxs where full rows/cols are invalid in any of the input arrays.
    Uses ``crop2d_rows_cols`` for each, then joins indices.

    :param arr: input 2d arrays.
    :return: x/y indices with invalid rows/cols.
    """
    xs = []
    ys = []

    for a in arr:
        _x, _y = crop2d_rows_cols(a)
        xs += _x.tolist()
        ys += _y.tolist()

    return (
        np.array(list(set(xs)), dtype=np.int64),
        np.array(list(set(ys)), dtype=np.int64),
    )


def crop2d_from_xy(arr: np.ndarray, xs: np.ndarray,
                   ys: np.ndarray) -> np.ndarray:
    """
    Remove rows/cols from a 2d array.

    :param arr: input array.
    :param xs: list of 1st-dimension indices to remove.
    :param ys: list of 2nd-dimension indices to remove.
    :return: remaining array.
    :raises: ``ValueError`` if input is not a 2d ndarray.
    """
    if len(arr.shape) != 2:
        raise ValueError('input is not a 2d array.')

    a = arr.copy()
    a = np.delete(a, xs, axis=0)
    a = np.delete(a, ys, axis=1)
    return a


def crop2d(x: np.ndarray, y: np.ndarray, *arr: np.ndarray) \
        -> Tuple[np.ndarray, ...]:
    """
    Remove invalid rows and columns from 2d data.

    Determine invalid areas from the x and y coordinates,
    and then crop the invalid rows/columns from all input data.

    :param x: 1st dim coordinates (2d meshgrid-like)
    :param y: 2nd dim coordinates (2d meshgrid-like)
    :param arr: other arrays to crop.
    :return: all arrays (incl. x and y), cropped.
    """
    xs, ys = joint_crop2d_rows_cols(x, y)
    allarrs = [x, y] + [a for a in arr]
    ret = [crop2d_from_xy(a, xs, ys) for a in allarrs]
    return tuple(ret)


def interp_meshgrid_2d(xx: np.ndarray,
                       yy: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Try to find missing vertices in a 2d meshgrid,
    where xx and yy are the x and y coordinates of each point.
    This is just done by simple linear interpolation (using pandas).

    i.e.:
    if xx = [[0, 0], [1, nan]], yy = [[0, 1], [0, nan]]
    this will return [[0, 0], [1, 1]], [[0, 1], [0, 1]].
    """
    xx2 = pd.DataFrame(xx).interpolate(axis=1).values
    yy2 = pd.DataFrame(yy).interpolate(axis=0).values
    return xx2, yy2


def centers2edges_1d(arr: np.ndarray) -> np.ndarray:
    """
    Given an array of center coordinates, return the array of
    bounding vertices for the mesh that is defined by the coordinates.
    This is useful for methods like pcolor(mesh).

    To illustrate: if x are the centers, we return the inferred o's:

      o-x-o-x-o-x-o-x--o--x--o

    They are equidistantly spaced between the centers, such that the centers
    are in the middle between the vertices.
    """
    e = (arr[1:] + arr[:-1]) / 2.
    e = np.concatenate(([arr[0] - (e[0] - arr[0])], e))
    e = np.concatenate((e, [arr[-1] + (arr[-1] - e[-1])]))
    return e


def centers2edges_2d(centers: np.ndarray) -> np.ndarray:
    """
    Given a 2d array of coordinates, return the array of bounding vertices for
    the mesh that is defined by the coordinates.
    This is useful for methods like pcolor(mesh).
    Done by very simple linear interpolation.

    To illustrate: if x are the centers, we return the inferred o's:

    ``
    o   o   o   o
      x---x---x
    o | o | o | o
      x---x---x
    o   o   o   o
    ``
    """
    shp = centers.shape
    edges = np.zeros((shp[0] + 1, shp[1] + 1))

    # the central vertices are easy -- follow just from the means of the
    # neighboring centers
    center = (centers[1:, 1:] + centers[:-1, :-1]
              + centers[:-1, 1:] + centers[1:, :-1]) / 4.
    edges[1:-1, 1:-1] = center

    # for the outer edges we just make the vertices such that the points are
    # pretty much in the center
    # first average over neighbor centers to get the 'vertical' right
    _left = (centers[0, 1:] + centers[0, :-1]) / 2.
    # then extrapolate to the left of the centers
    left = 2 * _left - center[0, :]
    edges[0, 1:-1] = left

    # and same for the other three sides
    _right = (centers[-1, 1:] + centers[-1, :-1]) / 2.
    right = 2 * _right - center[-1, :]
    edges[-1, 1:-1] = right

    _top = (centers[1:, 0] + centers[:-1, 0]) / 2.
    top = 2 * _top - center[:, 0]
    edges[1:-1, 0] = top

    _bottom = (centers[1:, -1] + centers[:-1, -1]) / 2.
    bottom = 2 * _bottom - center[:, -1]
    edges[1:-1, -1] = bottom

    # only thing remaining now is the corners of the grid.
    # this is a bit simplistic, but will be fine for now.
    # (mirror the vertex (1,1) of the diagonal at the outermost center)
    edges[0, 0] = 2 * centers[0, 0] - edges[1, 1]
    edges[0, -1] = 2 * centers[0, -1] - edges[1, -2]
    edges[-1, 0] = 2 * centers[-1, 0] - edges[-2, 1]
    edges[-1, -1] = 2 * centers[-1, -1] - edges[-2, -2]

    return edges
