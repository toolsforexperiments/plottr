import numpy as np
import pytest

from plottr.data.datadict import MeshgridDataDict
from plottr.utils import num


def test_basics():
    """Creation and validation of the meshgrid data dict."""
    x = np.arange(3)
    y = np.arange(1, 4)
    xx, yy = np.meshgrid(x, y, indexing='ij')
    zz = xx * yy

    dd = MeshgridDataDict(
        x=dict(values=xx),
        y=dict(values=yy),
        z=dict(values=zz, axes=['x', 'y'])
    )

    assert dd.validate()
    assert dd.shape() == xx.shape

    dd = MeshgridDataDict(
        x=dict(values=x),
        y=dict(values=y),
        z=dict(values=zz, axes=['x', 'y'])
    )

    with pytest.raises(ValueError):
        dd.validate()


def test_reorder():
    """Test reordering of axes."""

    a = np.arange(3)
    b = np.arange(5, 10)
    c = np.linspace(0, 1, 3)
    aa, bb, cc = np.meshgrid(a, b, c, indexing='ij')
    zz = aa + bb + cc

    dd = MeshgridDataDict(
        a=dict(values=aa),
        b=dict(values=bb),
        c=dict(values=cc),
        z=dict(values=zz, axes=['a', 'b', 'c'])
    )

    assert dd.validate()
    dd = dd.reorder_axes(c=0)
    assert dd.axes('z') == ['c', 'a', 'b']
    assert num.arrays_equal(dd.data_vals('a'), aa.transpose([2, 0, 1]))
    assert num.arrays_equal(dd.data_vals('b'), bb.transpose([2, 0, 1]))
    assert num.arrays_equal(dd.data_vals('c'), cc.transpose([2, 0, 1]))
    assert num.arrays_equal(dd.data_vals('z'), zz.transpose([2, 0, 1]))
