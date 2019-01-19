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


def test_array_reshape():
    """Test array reshaping with size adaption."""

    a = np.arange(10)
    out = num.array1d_to_meshgrid(a, (4, 4))
    assert out.shape == (4, 4)
    assert num.arrays_equal(out, np.append(a, 6 * [None]).reshape(4, 4))

    a = np.arange(10).astype(complex)
    out = num.array1d_to_meshgrid(a, (4, 4))
    assert out.shape == (4, 4)
    assert num.arrays_equal(out, np.append(a, 6 * [np.nan]).reshape(4, 4))

    a = np.arange(10).astype(float)
    out = num.array1d_to_meshgrid(a, (3, 3))
    assert out.shape == (3, 3)
    assert num.arrays_equal(out, a[:9].reshape(3, 3))
