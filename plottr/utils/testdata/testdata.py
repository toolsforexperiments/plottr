"""
Generation of useful test data.

Convention:
functions with name `generate_[...]` return generators that can be
used to produce data line by line.
functions with name `get_[...]` return valid DataDict objects.
"""
from typing import Iterable, Dict
import numpy as np

from plottr.data.datadict import DataDict


def generate_2d_scalar_simple(nx: int, ny: int, ndeps: int = 1) -> Iterable[Dict[str, int]]:
    """
    Generate 2d example data, with axes x, y.

    Axes:
    x = np.arange(0, nx)
    y = np.arange(0, ny)

    Dependents:
    z_<idx> = x * y * <idx>

    :param nx: number of points on the x-axes.
    :param ny: number of points on the y-axis.
    :param ndeps: number of columns
    :param noise: how much noise to add to data
    """

    x = np.arange(nx, dtype=float)
    y = np.arange(ny, dtype=float)
    xx, yy = np.meshgrid(x, y, indexing='ij')

    for x, y in zip(xx.reshape(-1), yy.reshape(-1)):
        ret = dict(x=x, y=y)
        for n in range(ndeps):
            ret[f'z_{n}'] = x * y * n
        yield ret


def get_1d_scalar_cos_data(nx: int = 10, ndata: int = 1) -> DataDict:
    """
    return a datadict with `ndata` dependents.
    All have a cos-dependence on x (with increasing frequency).
    Also noise is added on top.
    """
    x = np.linspace(0, 10, nx)
    d = DataDict(
        x=dict(values=x, unit='A')
    )
    for n in range(ndata):
        dd = np.cos((n+1)*x) + (-0.1 + 0.2 * np.random.rand(x.size))
        d[f"data_{n+1}"] = dict(values=dd, axes=['x',], unit='a.u.')

    d.validate()
    return d


def get_2d_scalar_cos_data(nx: int = 10, ny: int = 10, ndata: int = 1) -> DataDict:
    """
    return a datadict with `ndata` dependents.
    All have a cos-dependence on x (with increasing frequency),
    and repetitions along y.
    Also noise is added on top.
    """
    x = np.linspace(0, 10, nx)
    y = np.arange(ny)
    xx, yy = np.meshgrid(x, y, indexing='ij')

    d = DataDict(
        x=dict(values=xx.reshape(-1), unit='A'),
        y=dict(values=yy.reshape(-1), unit='B'),
    )
    for n in range(ndata):
        dd = np.cos((n+1)*xx) + (-0.1 + 0.2 * np.random.rand(*yy.shape))
        d[f"data_{n+1}"] = dict(values=dd.reshape(-1), axes=['x', 'y'])

    d.validate()
    return d


# DEPRECATED BUT STILL IN USE
def two_1d_traces(nvals: int = 11) -> DataDict:
    x = np.linspace(0, 10, nvals)
    y = np.cos(x)
    z = np.cos(x) ** 2
    d = DataDict(
        x={'values': x},
        y={'values': y, 'axes': ['x']},
        z={'values': z, 'axes': ['x']},
    )
    d.validate()
    return d


def one_2d_set(nx: int = 10, ny: int = 10) -> DataDict:
    x = np.linspace(0, 10, nx)
    y = np.arange(ny)

    xx, yy = np.meshgrid(x, y, indexing='ij')
    dd = np.cos(xx) + (-0.05 + 0.1 * np.random.rand(*yy.shape))

    d = DataDict(
        x=dict(values=xx.reshape(-1)),
        y=dict(values=yy.reshape(-1)),
        cos_data=dict(values=dd.reshape(-1), axes=['x', 'y']),
    )
    d.validate()
    return d


def two_compatible_noisy_2d_sets(nx: int =10, ny: int = 10) -> DataDict:
    x = np.linspace(0, 10, nx)
    y = np.arange(ny)

    xx, yy = np.meshgrid(x, y, indexing='ij')
    dd = np.cos(xx) + (-0.05 + 0.1 * np.random.rand(*yy.shape))
    dd2 = np.sin(xx) + (-0.5 + 1 * np.random.rand(*yy.shape))

    d = DataDict(
        x=dict(values=xx.reshape(-1)),
        y=dict(values=yy.reshape(-1)),
        cos_data=dict(values=dd.reshape(-1), axes=['x', 'y']),
        sin_data=dict(values=dd2.reshape(-1), axes=['x', 'y']),
    )
    d.validate()
    return d


def three_compatible_3d_sets(nx: int = 3, ny: int = 3,
                             nz: int = 3, rand_factor: int = 1) -> DataDict:
    x = np.linspace(0, 10, nx)
    y = np.linspace(-5, 5, ny)
    z = np.arange(nz)
    xx, yy, zz = np.meshgrid(x, y, z, indexing='ij')
    dd = np.cos(xx) * np.sin(yy) + rand_factor * np.random.rand(*zz.shape)
    dd2 = np.sin(xx) * np.cos(yy) + rand_factor * np.random.rand(*zz.shape)
    dd3 = np.cos(xx) ** 2 * np.cos(yy) ** 2 + rand_factor * np.random.rand(
        *zz.shape)

    d = DataDict(
        x=dict(values=xx.reshape(-1), unit='mA'),
        y=dict(values=yy.reshape(-1), unit='uC'),
        z=dict(values=zz.reshape(-1), unit='nF'),
        data=dict(values=dd.reshape(-1), axes=['x', 'y', 'z'], unit='kW'),
        more_data=dict(values=dd2.reshape(-1), axes=['x', 'y', 'z'], unit='MV'),
        different_data=dict(values=dd3.reshape(-1), axes=['x', 'y', 'z'],
                            unit='TS')
    )
    d.validate()
    return d


def three_incompatible_3d_sets(nx: int = 3, ny: int = 3,
                               nz: int = 3, rand_factor: int = 1) -> DataDict:
    x = np.linspace(0, 10, nx)
    y = np.linspace(-5, 5, ny)
    z = np.arange(nz)
    xx, yy, zz = np.meshgrid(x, y, z, indexing='ij')
    dd = np.cos(xx) * np.sin(yy) + rand_factor * np.random.rand(*zz.shape)
    dd2 = np.sin(xx) * np.cos(yy) + rand_factor * np.random.rand(*zz.shape)
    dd3 = np.cos(xx) ** 2 * np.exp(-yy**2 * 0.2) + rand_factor * np.random.rand(
        *zz.shape)

    d = DataDict(
        x=dict(values=xx.reshape(-1), unit='mA'),
        y=dict(values=yy.reshape(-1), unit='uC'),
        z=dict(values=zz.reshape(-1), unit='nF'),
        data=dict(values=dd.reshape(-1),
                  axes=['x', 'y', 'z'], unit='kW'),
        more_data=dict(values=dd2.reshape(-1),
                       axes=['y', 'x', 'z'], unit='MV'),
        different_data=dict(values=dd3.reshape(-1),
                            axes=['z', 'y', 'x'], unit='TS'),
    )
    d.validate()
    return d
