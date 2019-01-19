import numpy as np
import pytest

from plottr.data.datadict import DataDict
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
    b = np.arange(4*2).reshape(4,2)
    x = np.arange(4)
    y = np.arange(4*2).reshape(4,2)

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
