from plottr.data.datadict import DataDict, DataDictBase

#TODO: full description of tests.

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
    assert dd.axes('c') == ['a', 'b']
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


def test_validation():
    """Test if validation is working."""


def test_sanitizing():
    """Test cleaning up of datasets."""


def test_reorder():
    """Test reordering and transposing axes."""


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

    # TODO: nested dims.


def test_expansion():
    """Test correct expansion of data."""
