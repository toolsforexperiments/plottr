import pytest
import numpy as np
from plottr.data.datadict import DataDict


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
        a = dict(values=np.arange(4).reshape(2,2)),
        b = dict(values=np.arange(4).reshape(2,2), axes=['a']),
        x = dict(values=np.arange(6).reshape(2,3),),
        y = dict(values=np.arange(6).reshape(2,3), axes=['x'])
    )

    assert dd.validate()
    assert not dd.is_expandable()
    with pytest.raises(ValueError):
        dd.expand()
