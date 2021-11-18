from collections import OrderedDict

import numpy as np
from numpy.testing import assert_array_equal

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
    arr[7] = None
    assert num.find_direction_period(arr) == 5

    arr = np.array([1, 2, 3, 1, 2, 1, 2, 3])
    assert num.find_direction_period(arr) is None

    arr = np.ones(10)
    assert num.find_direction_period(arr) is np.inf


def test_find_grid_from_directions_2d():
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


def test_find_grid_from_directions_multid():
    """Test grid finding on N-d data, incl dimensions that don't change and
    some missing data."""

    arrs = dict(
        v = np.logspace(-5, 3, 9),
        w = np.linspace(-100, -90, 17),
        x = np.arange(5),
        y = np.arange(10, 0, -1),
        z0 = None,
        z1 = None,
        z2 = None,
    )

    for m in np.linspace(0, 7645, 31):
        nmissing = int(m)

        # construct expected outcome
        names_unordered = ['w', 'v', 'x', 'y']
        fullsize = np.prod([arrs[a].size for a in names_unordered])

        # compute the shape by simply iterating
        target_order = names_unordered.copy()
        target_shape = [1 for a in names_unordered]
        cur_dim = -1
        while np.prod(target_shape) < (fullsize-nmissing):
            if target_shape[cur_dim] < arrs[names_unordered[cur_dim]].size:
                target_shape[cur_dim] += 1
            else:
                cur_dim -= 1

        # add non-sweep dims
        for n, v in arrs.items():
            if n[0] == 'z':
                target_shape.insert(0, 1)
                target_order.insert(0, n)
        target_shape = tuple(target_shape)

        # construct input data
        arrs_unordered = [arrs[k] for k in names_unordered]
        grid = np.meshgrid(*arrs_unordered, indexing='ij')

        # format input data such that we can feed it into the function
        grid_flat = [a.flatten() for a in grid]
        if nmissing > 0:
            grid_flat = [a[:-nmissing] for a in grid_flat]
        grid_flat_dict = {k: v for k, v in zip(names_unordered, grid_flat)}
        for n, v in arrs.items():
            if n[0] == 'z':
                grid_flat_dict[n] = np.ones(grid_flat[0].size)

        # analyze flattened data arrays
        names_out, shapes_out = num.guess_grid_from_sweep_direction(**grid_flat_dict)

        # test shape
        assert shapes_out == target_shape

        for i, n in enumerate(names_out):
            if shapes_out[i] > 1:
                assert n == target_order[i]


def test_cropping2d():
    """Test basic data cropping of 2d grids"""
    arr = np.arange(16.).reshape(4, 4)
    arr[2:] = np.nan
    data = np.random.rand(4, 4)

    x, y, z = num.crop2d(arr, arr.T, data)
    assert num.arrays_equal(x, arr[:2, :2])
    assert num.arrays_equal(y, arr.T[:2, :2])
    assert num.arrays_equal(z, data[:2, :2])


def test_crop2d_noop():
    x = np.arange(1, 10)
    y = np.arange(20, 26)

    xx, yy = np.meshgrid(x, y)

    zz = np.random.rand(*xx.shape)

    xxx, yyy, zzz = num.crop2d(xx, yy, zz)

    assert_array_equal(xx, xxx)
    assert_array_equal(yy, yyy)
    assert_array_equal(zz, zzz)


def test_crop_all_nan():
    x = np.arange(1., 10.)
    y = np.arange(20., 26.)

    xx, yy = np.meshgrid(x, y)

    xx[:] = np.nan
    yy[:] = np.nan

    zz = np.random.rand(*xx.shape)

    xxx, yyy, zzz = num.crop2d(xx, yy, zz)

    assert xxx.shape == (0, 0)
    assert yyy.shape == (0, 0)
    assert zzz.shape == (0, 0)


def test_crop_less_than_one_row():
    x = np.arange(1., 10.)
    y = np.arange(20., 26.)

    xx, yy = np.meshgrid(x, y)

    xx[1:, :] = np.nan
    xx[0, 5:] = np.nan
    yy[1:, :] = np.nan
    yy[0:, 5:] = np.nan

    zz = np.random.rand(*xx.shape)

    xxx, yyy, zzz = num.crop2d(xx, yy, zz)

    assert xxx.shape == (1, 5)
    assert_array_equal(xxx, xx[0:1, 0:5])

    assert zzz.shape == (1, 5)
    assert_array_equal(yyy, yy[0:1, 0:5])

    assert zzz.shape == (1, 5)
    assert_array_equal(zzz, zz[0:1, 0:5])
