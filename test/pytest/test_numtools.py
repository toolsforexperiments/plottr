import numpy as np

from plottr.utils import num


def test_array_equality():
    """Test if two arrays are correctly identified as having equal content"""

    a = np.arange(2 * 4).astype(object).reshape(4, 2)
    a[2, 0] = None
    b = np.arange(2 * 4).astype(np.complex128).reshape(4, 2)
    b[2, 0] = np.nan
    assert num.arrays_equal(a, b)

    a = np.arange(2 * 4).astype(object).reshape(4, 2)
    a[2, 0] = 0
    b = np.arange(2 * 4).astype(np.complex128).reshape(4, 2)
    b[2, 0] = np.nan
    assert not num.arrays_equal(a, b)
