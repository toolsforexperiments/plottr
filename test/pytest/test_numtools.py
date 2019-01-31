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


def test_find_direction_period():
    """Test period finding in the direction"""

    arr = np.concatenate((np.arange(5), np.arange(5))).astype(float)
    assert num.find_direction_period(arr) == 5

    arr[1] = np.nan
    arr[6] = None
    assert num.find_direction_period(arr) == 5

    arr = np.array([1, 2, 3, 1, 2, 1, 2, 3])
    assert num.find_direction_period(arr) is None


def test_find_grid_from_directions():
    """Test finding the shape of a dataset by analyzing axes values"""

    x = np.arange(5)
    y = np.arange(7, 3, -1)
    xx, yy = np.meshgrid(x, y, indexing='ij')

    ret = num.guess_grid_from_sweep_direction(
        x=xx.reshape(-1), y=yy.reshape(-1)
    )
    assert ret[0] == ['x', 'y']
    assert ret[1] == xx.shape

    # also test incomplete grids
    ret = num.guess_grid_from_sweep_direction(
        x=xx.reshape(-1)[:-3], y=yy.reshape(-1)[:-3]
    )
    assert ret[0] == ['x', 'y']
    assert ret[1] == xx.shape


def test_cropping2d():
    """Test basic data cropping of 2d grids"""
    arr = np.arange(16.).reshape(4, 4)
    arr[2:] = np.nan
    data = np.random.rand(4, 4)

    x, y, z = num.crop2d(arr, arr.T, data)
    assert num.arrays_equal(x, arr[:2, :2])
    assert num.arrays_equal(y, arr.T[:2, :2])
    assert num.arrays_equal(z, data[:2, :2])
