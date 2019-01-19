"""num.py

Tools for numerical operations.
"""
from typing import Sequence, Tuple
import numpy as np


FLOATTYPES = [float, np.float, np.float16, np.float32, np.float64,
              complex, np.complex, np.complex64, np.complex128]


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
