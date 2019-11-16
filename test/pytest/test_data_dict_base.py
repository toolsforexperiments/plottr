import pytest
import numpy as np
from plottr.utils.num import arrays_equal
from plottr.data.datadict import DataDict, DataDictBase
from plottr.data.datadict import combine_datadicts


# TODO: full description of tests.

def test_get_data():
    """Test basic accessing of data."""

    dd = DataDictBase(
        x=dict(values=[1, 2, 3]),
        y=dict(values=[1, 2, 3], axes=['x']),
        a=dict(values=[4, 5, 6], axes=[]),
        b=dict(values=[5, 6, 7], axes=[]),
        c=dict(values=[6, 7, 8], axes=['b', 'a']),
    )

    assert set(dd.dependents()) == {'y', 'c'}
    assert set(dd.axes()) == {'a', 'b', 'x'}
    assert dd.axes('c') == ['b', 'a']
    assert dd.data_vals('c') == [6, 7, 8]


def test_meta():
    """Test accessing meta information."""

    dd = DataDict(
        x=dict(
            values=[1, 2, 3],
            __meta1__='abc',
            __meta2__='def',
        ),
        y=dict(
            values=[1, 2, 3],
            axes=['x'],
            __meta3__='123',
            __meta4__=None,
        ),
        __info__=lambda x: 0,
        __more_info__=object,
    )
    dd['__1234!__'] = '```'
    dd.add_meta('###', 3e-12)
    dd.add_meta('@^&', 0, data='x')

    assert dd.validate()

    global_meta = {k: v for k, v in dd.meta_items()}
    for k in ['info', 'more_info', '1234!', '###']:
        assert f'__{k}__' in dd
        assert k in global_meta

    assert dd.meta_val('more_info') == object
    assert dd.meta_val('info')(1) == 0
    assert dd.meta_val('@^&', 'x') == 0

    for k in ['meta1', 'meta2', '@^&']:
        assert dd.meta_val(k, data='x') == dd['x'][f'__{k}__']
        assert f'__{k}__' in dd['x']
        assert k in [n for n, _ in dd.meta_items('x')]

    # test stripping of meta information
    dd.clear_meta()
    assert dd.validate()

    nmeta = 0
    for k, _ in dd.items():
        if k[:2] == '__' and k[-2:] == '__':
            nmeta += 1
    assert nmeta == 0

    for d, v in dd.data_items():
        for k, _ in dd[d].items():
            if k[:2] == '__' and k[-2:] == '__':
                nmeta += 1
        assert nmeta == 0


def test_extract():
    """Test extraction of data fields."""


def test_structure():
    """Test if structure is reported correctly."""

    dd = DataDictBase(
        x=dict(values=[1, 2, 3, 1]),
        y=dict(values=[1, 2, 3, 1]),
        z=dict(values=[0, 0, 0, 0], axes=['x', 'y']),
        __info__='some info',
    )

    dd2 = DataDictBase(
        x=dict(values=[2, 3, 4]),
        y=dict(values=[10, 20, 30]),
        z=dict(values=[-1, -3, -5], axes=['x', 'y']),
        __otherinfo__=0,
    )

    assert dd.structure().dependents() == ['z']
    assert dd.structure().axes('z') == ['x', 'y']

    assert dd.structure(include_meta=False) == \
           dd2.structure(include_meta=False)

    assert dd.structure(include_meta=True) != \
           dd2.structure(include_meta=True)

    assert DataDictBase.same_structure(dd, dd2)


def test_validation():
    """Test if validation is working."""

    with pytest.raises(ValueError):
        dd = DataDict(
            y=dict(values=[0], axes=['x'])
        )
        dd.validate()

    dd = DataDict(
        x=dict(values=[0]),
        y=dict(values=[0], axes=['x']),
    )
    assert dd.validate()


def test_sanitizing():
    """Test cleaning up of datasets."""
    dd = DataDictBase(
        x=dict(values=[0]),
        y=dict(values=[0]),
        z=dict(values=[0], axes=['y']),
    )

    dd = dd.sanitize()
    assert dd.axes() == ['y']
    assert dd.dependents() == ['z']
    assert dd.validate()


def test_reorder():
    """Test reordering and transposing axes."""
    dd = DataDictBase(
        a=dict(values=[4, 5, 6], axes=[]),
        b=dict(values=[5, 6, 7], axes=[]),
        c=dict(values=[6, 7, 8], axes=[]),
        d=dict(values=[0, 0, 0], axes=['a', 'b', 'c'])
    )

    assert dd.axes('d') == ['a', 'b', 'c']

    dd = dd.reorder_axes('d', b=0, a=1, c=2)
    assert dd.axes('d') == ['b', 'a', 'c']

    dd = dd.reorder_axes(c=0)
    assert dd.axes('d') == ['c', 'b', 'a']


def test_shapes():
    """Test correct retrieval of shapes, incl nested shapes."""

    dd = DataDict(
        x=dict(
            values=[1, 2, 3],
        ),
        y=dict(
            values=[1, 2, 3],
            axes=['x'],
        ),
        z=dict(
            values=[[0, 0], [1, 1], [2, 2]],
            axes=['x'],
        ),
    )

    assert dd.validate()

    shapes = dd.shapes()
    assert shapes['x'] == (3,)
    assert shapes['y'] == (3,)
    assert shapes['z'] == (3, 2)


def test_combine_ddicts():
    """test the datadict combination function"""

    # first case: two ddicts with different independents and shared axes.
    # should work. probably the most common use case.
    dd1 = DataDict(
        x=dict(
            values=np.array([1, 2, 3]),
        ),
        y=dict(
            values=np.array([1, 2, 3]),
        ),
        z1=dict(
            values=np.array([1, 2, 3]),
            axes=['x', 'y'],
        )
    )
    dd1.validate()

    dd2 = DataDict(
        x=dict(
            values=np.array([1, 2, 3]),
        ),
        y=dict(
            values=np.array([1, 2, 3]),
        ),
        z2=dict(
            values=np.array([3, 2, 1]),
            axes=['x', 'y'],
        )
    )
    dd2.validate()

    combined_dd = combine_datadicts(dd1, dd2)
    expected_dd = DataDict(
        x=dict(
            values=np.array([1, 2, 3]),
        ),
        y=dict(
            values=np.array([1, 2, 3]),
        ),
        z1=dict(
            values=np.array([1, 2, 3]),
            axes=['x', 'y'],
        ),
        z2=dict(
            values=np.array([3, 2, 1]),
            axes=['x', 'y'],
        ),
    )
    expected_dd.validate()
    assert combined_dd == expected_dd

    # second case: two ddicts with a conflict in an axis
    dd1 = DataDict(
        x=dict(
            values=np.array([1, 2, 3]),
        ),
        y=dict(
            values=np.array([1, 2, 3]),
        ),
        z1=dict(
            values=np.array([1, 2, 3]),
            axes=['x', 'y'],
        )
    )
    dd1.validate()

    dd2 = DataDict(
        x=dict(
            values=np.array([1, 2, 4]),
        ),
        y=dict(
            values=np.array([1, 2, 3]),
        ),
        z2=dict(
            values=np.array([3, 2, 1]),
            axes=['x', 'y'],
        )
    )
    dd2.validate()

    combined_dd = combine_datadicts(dd1, dd2)
    expected_dd = DataDict(
        x=dict(
            values=np.array([1, 2, 3]),
        ),
        y=dict(
            values=np.array([1, 2, 3]),
        ),
        z1=dict(
            values=np.array([1, 2, 3]),
            axes=['x', 'y'],
        ),
        x_0=dict(
            values=np.array([1, 2, 4]),
        ),
        z2=dict(
            values=np.array([3, 2, 1]),
            axes=['x_0', 'y'],
        )
    )
    expected_dd.validate()
    assert combined_dd == expected_dd

    # third case: rename a dependent only
    x = np.array([1, 2, 3])
    y = np.array([1, 2, 3])
    z = np.arange(3)
    dd1 = DataDict(x=dict(values=x),
                   y=dict(values=y),
                   z=dict(values=z, axes=['x', 'y']))
    dd1.validate()
    dd2 = dd1.copy()
    dd2['z']['values'] = z[::-1]
    dd2.validate()

    combined_dd = combine_datadicts(dd1, dd2)
    expected_dd = DataDict(x=dict(values=x),
                           y=dict(values=y),
                           z=dict(values=z, axes=['x', 'y']),
                           z_0=dict(values=z[::-1], axes=['x', 'y']))
    assert combined_dd == expected_dd
