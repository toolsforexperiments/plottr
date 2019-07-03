import numpy as np
import pytest

from plottr.data.datadict import (
    DataDict, DataDictBase,
    guess_shape_from_datadict, datadict_to_meshgrid
)
from plottr.utils import num


def test_append():
    """Testing appending datadicts to each other."""
    dd1 = DataDict(
        x=dict(values=[1, 2, 3]),
        y=dict(values=np.arange(6).reshape(3, 2), axes=['x']),
    )

    dd2 = DataDict(
        x=dict(values=[4, 5, 6]),
        y=dict(values=np.arange(6, 12).reshape(3, 2), axes=['x']),
    )

    dd3 = dd1 + dd2
    assert np.all(
        np.isclose(
            dd3.data_vals('y'),
            np.arange(12).reshape(6, 2)
        )
    )
    assert np.all(
        np.isclose(
            dd3.data_vals('x'),
            np.arange(1, 7)
        )
    )

    dd1.append(dd2)
    assert np.all(
        np.isclose(
            dd1.data_vals('y'),
            np.arange(12).reshape(6, 2)
        )
    )
    assert np.all(
        np.isclose(
            dd1.data_vals('x'),
            np.arange(1, 7)
        )
    )


def test_add_data():
    """Testing simple adding of data"""

    # make base data
    dd = DataDict(
        x=dict(values=[1, 2, 3]),
        y=dict(values=np.arange(6).reshape(3, 2), axes=['x']),
    )
    assert dd.validate()

    # test bad data insertion
    with pytest.raises(ValueError):
        dd.add_data(x=[4, ])
    assert num.arrays_equal(
        dd.data_vals('x'),
        np.array([1, 2, 3]),
    )

    # this should work!
    dd.add_data(x=[4, ], y=[[6, 7], ])
    assert num.arrays_equal(
        dd.data_vals('x'),
        np.array([1, 2, 3, 4])
    )
    assert num.arrays_equal(
        dd.data_vals('y'),
        np.arange(8).reshape(4, 2)
    )


def test_expansion_simple():
    """Test whether simple expansion of nested parameters works."""

    a = np.arange(3)
    x = np.arange(3)
    y = np.arange(7, 10)

    aaa, xxx, yyy = np.meshgrid(a, x, y, indexing='ij')
    zzz = aaa + xxx * yyy

    dd = DataDict(
        a=dict(values=a),
        x=dict(values=xxx),
        y=dict(values=yyy),
        z=dict(values=zzz),
    )

    assert dd.validate()
    assert dd.nrecords() == 3
    assert dd._inner_shapes() == dict(a=tuple(), x=(3, 3), y=(3, 3), z=(3, 3))
    assert dd.is_expandable()
    assert not dd.is_expanded()

    dd2 = dd.expand()
    assert dd2.is_expanded()
    assert dd2.nrecords() == aaa.size
    assert np.all(np.isclose(
        dd2.data_vals('a'), aaa.reshape(-1)))
    assert np.all(np.isclose(
        dd2.data_vals('x'), xxx.reshape(-1)))
    assert np.all(np.isclose(
        dd2.data_vals('z'), zzz.reshape(-1)))
    assert set(dd2.shapes().values()) == {(aaa.size,)}


def test_expansion_fail():
    """Test whether expansion fails correctly"""

    dd = DataDict(
        a=dict(values=np.arange(4).reshape(2, 2)),
        b=dict(values=np.arange(4).reshape(2, 2), axes=['a']),
        x=dict(values=np.arange(6).reshape(2, 3), ),
        y=dict(values=np.arange(6).reshape(2, 3), axes=['x'])
    )

    assert dd.validate()
    assert not dd.is_expandable()
    with pytest.raises(ValueError):
        dd.expand()


def test_nontrivial_expansion():
    """test expansion when different dependents require different
    expansion of an axis."""

    a = np.arange(4)
    b = np.arange(4 * 2).reshape(4, 2)
    x = np.arange(4)
    y = np.arange(4 * 2).reshape(4, 2)

    dd = DataDict(
        a=dict(values=a),
        b=dict(values=b),
        x=dict(values=x, axes=['a']),
        y=dict(values=y, axes=['a', 'b'])
    )

    assert dd.validate()
    assert dd.is_expandable()

    dd_x = dd.extract('x').expand()
    assert num.arrays_equal(a, dd_x.data_vals('a'))

    dd_y = dd.extract('y').expand()
    assert num.arrays_equal(a.repeat(2), dd_y.data_vals('a'))


def test_validation_fail():
    """Test if invalid data fails the validation,"""

    dd = DataDict(
        x=dict(values=[1, 2]),
        y=dict(values=[1, 2], axes=['x']),
    )
    assert dd.validate()

    dd = DataDict(
        x=dict(values=[1, 2, 3]),
        y=dict(values=[1, 2], axes=['x']),
    )
    with pytest.raises(ValueError):
        dd.validate()


def test_sanitizing_1d():
    """Test if dataset cleanup gives expected results."""
    a = np.arange(10).astype(object)
    a[4:6] = None
    b = np.arange(10).astype(complex)
    b[4] = np.nan

    a_clean = np.hstack((a[:4], a[5:]))
    b_clean = np.hstack((b[:4], b[5:]))

    dd = DataDict(
        a=dict(values=a),
        b=dict(values=b, axes=['a']),
    )

    assert dd.validate()
    dd2 = dd.remove_invalid_entries()
    assert dd2.validate()
    assert num.arrays_equal(dd2.data_vals('a'), a_clean)
    assert num.arrays_equal(dd2.data_vals('b'), b_clean)


def test_sanitizing_2d():
    """Test if dataset cleanup gives expected results."""

    a = np.arange(2 * 4).astype(object).reshape(4, 2)
    a[1, :] = None
    a[3, :] = None
    a[2, -1] = None

    b = np.arange(2 * 4).astype(float).reshape(4, 2)
    b[1, :] = np.nan
    b[0, 0] = np.nan
    b[3, 0] = np.nan

    a_clean = np.vstack((a[0:1, :], a[2:, :]))
    b_clean = np.vstack((b[0:1, :], b[2:, :]))

    dd = DataDict(
        a=dict(values=a),
        b=dict(values=b, axes=['a']),
    )

    assert dd.validate()
    dd2 = dd.remove_invalid_entries()
    assert dd2.validate()
    assert dd2.shapes() == {'a': (3, 2), 'b': (3, 2)}
    assert num.arrays_equal(dd2.data_vals('a'), a_clean)
    assert num.arrays_equal(dd2.data_vals('b'), b_clean)


def test_shape_guessing_simple():
    """test whether we can infer shapes correctly"""

    a = np.linspace(0, 1, 11)
    b = np.arange(5)
    aa, bb = np.meshgrid(a, b, indexing='ij')
    zz = aa * bb

    dd = DataDict(
        a=dict(values=aa.reshape(-1)),
        b=dict(values=bb.reshape(-1)),
        z=dict(values=zz.reshape(-1), axes=['a', 'b'])
    )

    assert guess_shape_from_datadict(dd) == dict(z=(['a', 'b'], (11, 5)))

    dd['a']['values'][5] = None
    dd['a']['values'][10] = np.nan
    assert guess_shape_from_datadict(dd) == dict(z=(['a', 'b'], (11, 5)))

    # non-uniform
    # noise on the coordinates should not result in failing as long as it
    # keeps monotonicity in the sweep axes
    dd['a']['values'] = (aa + np.random.rand(a.size).reshape(a.size, 1)
                         * 1e-3).reshape(-1)
    assert guess_shape_from_datadict(dd) == dict(z=(['a', 'b'], (11, 5)))

    dd['b']['values'] = bb.reshape(-1) + np.random.rand(bb.size) * 1e-3
    assert guess_shape_from_datadict(dd) == dict(z=(['a', 'b'], (11, 5)))


def test_meshgrid_conversion():
    """Test making a meshgrid from a dataset"""

    a = np.linspace(0, 1, 11)
    b = np.arange(5)
    aa, bb = np.meshgrid(a, b, indexing='ij')
    zz = aa * bb

    dd = DataDict(
        a=dict(values=aa.reshape(-1)),
        b=dict(values=bb.reshape(-1)),
        z=dict(values=zz.reshape(-1), axes=['a', 'b']),
        __info__='some info',
    )

    dd2 = datadict_to_meshgrid(dd, target_shape=(11, 5))
    assert DataDictBase.same_structure(dd, dd2)
    assert num.arrays_equal(dd2.data_vals('a'), aa)
    assert num.arrays_equal(dd2.data_vals('z'), zz)

    dd2 = datadict_to_meshgrid(dd, target_shape=None)
    assert DataDictBase.same_structure(dd, dd2)
    assert num.arrays_equal(dd2.data_vals('a'), aa)
    assert num.arrays_equal(dd2.data_vals('z'), zz)

    # test the case where inner/outer
    aa, bb = np.meshgrid(a, b, indexing='xy')
    zz = aa * bb

    dd = DataDict(
        a=dict(values=aa.reshape(-1)),
        b=dict(values=bb.reshape(-1)),
        z=dict(values=zz.reshape(-1), axes=['a', 'b']),
        __info__='some info',
    )

    dd2 = datadict_to_meshgrid(dd, target_shape=(5, 11),
                               inner_axis_order=['b', 'a'])
    assert DataDictBase.same_structure(dd, dd2)
    assert num.arrays_equal(dd2.data_vals('a'), np.transpose(aa, (1, 0)))
    assert num.arrays_equal(dd2.data_vals('z'), np.transpose(zz, (1, 0)))

    dd2 = datadict_to_meshgrid(dd, target_shape=None)
    assert DataDictBase.same_structure(dd, dd2)
    assert num.arrays_equal(dd2.data_vals('a'), np.transpose(aa, (1, 0)))
    assert num.arrays_equal(dd2.data_vals('z'), np.transpose(zz, (1, 0)))
