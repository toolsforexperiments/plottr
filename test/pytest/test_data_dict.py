import numpy as np

from plottr.data.datadict import DataDict


def test_append():
    """Testing appending datadicts to each other."""
    dd1 = DataDict(
        x=dict(values=[1, 2, 3]),
        y=dict(values=np.arange(6).reshape(3,2), axes=['x']),
    )

    dd2 = DataDict(
        x=dict(values=[4, 5, 6]),
        y=dict(values=np.arange(6,12).reshape(3,2), axes=['x']),
    )

    dd3 = dd1 + dd2
    assert np.all(
        np.isclose(
            dd3.data_vals('y'),
            np.arange(12).reshape(6,2)
        )
    )
    assert np.all(
        np.isclose(
            dd3.data_vals('x'),
            np.arange(1,7)
        )
    )

    dd1.append(dd2)
    assert np.all(
        np.isclose(
            dd1.data_vals('y'),
            np.arange(12).reshape(6,2)
        )
    )
    assert np.all(
        np.isclose(
            dd1.data_vals('x'),
            np.arange(1,7)
        )
    )
