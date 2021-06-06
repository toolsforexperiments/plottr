"""
``plottr.plot.mpl.plotting`` -- Plotting tools (mostly used in Autoplot)
"""

from enum import Enum, auto, unique
from typing import Any, Optional, Tuple, Union

import numpy as np
from matplotlib import colors, rcParams
from matplotlib.axes import Axes
from matplotlib.image import AxesImage

from plottr.utils import num
from plottr.utils.num import centers2edges_2d, interp_meshgrid_2d

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


@unique
class PlotType(Enum):
    """Plot types currently supported in Autoplot."""

    #: no plot defined
    empty = auto()

    #: a single 1D line/scatter plot per panel
    singletraces = auto()

    #: multiple 1D lines/scatter plots per panel
    multitraces = auto()

    #: image plot of 2D data
    image = auto()

    #: colormesh plot of 2D data
    colormesh = auto()

    #: 2D scatter plot
    scatter2d = auto()


class SymmetricNorm(colors.Normalize):
    """Color norm that's symmetric and linear around a center value."""

    def __init__(self, vmin: Optional[float] = None,
                 vmax: Optional[float] = None,
                 vcenter: float = 0,
                 clip: bool = False):
        super().__init__(vmin, vmax, clip)
        self.vcenter = vcenter

    def __call__(self, value: float, clip: Optional[bool] = None) -> np.ma.core.MaskedArray:
        vlim = max(abs(self.vmin - self.vcenter), abs(self.vmax - self.vcenter))
        self.vmax: float = vlim + self.vcenter
        self.vmin: float = -vlim + self.vcenter
        return super().__call__(value, clip)


# 2D plots
def colorplot2d(ax: Axes,
                x: Union[np.ndarray, np.ma.MaskedArray],
                y: Union[np.ndarray, np.ma.MaskedArray],
                z: Union[np.ndarray, np.ma.MaskedArray],
                plotType: PlotType = PlotType.image,
                axLabels: Tuple[Optional[str], Optional[str], Optional[str]] = ('', '', ''),
                **kw: Any) -> Optional[AxesImage]:
    """make a 2d colorplot. what plot is made, depends on `plotType`.
    Any of the 2d plot types in :class:`PlotType` works.

    :param ax: matplotlib subPlots to plot in
    :param x: x coordinates (meshgrid)
    :param y: y coordinates (meshgrid)
    :param z: z data
    :param plotType: the plot type
    :param axLabels: labels for the x, y subPlots, and the colorbar.

    all keywords are passed to the actual plotting functions, depending on the ``plotType``:

    - :attr:`PlotType.image` --
        :func:`plotImage`
    - :attr:`PlotType.colormesh` --
        :func:`ppcolormesh_from_meshgrid`
    - :attr:`PlotType.scatter2d` --
        matplotlib's `scatter`
    """
    cmap = kw.pop('cmap', rcParams['image.cmap'])

    # first we need to check if our grid can be plotted nicely.
    if plotType in [PlotType.image, PlotType.colormesh]:
        x = x.astype(float)
        y = y.astype(float)
        z = z.astype(float)

        # first check if we need to fill some masked values in
        if isinstance(x, np.ma.MaskedArray) and np.ma.is_masked(x):
            x = x.filled(np.nan)
        if isinstance(y, np.ma.MaskedArray) and np.ma.is_masked(y):
            y = y.filled(np.nan)
        if isinstance(z, np.ma.MaskedArray) and np.ma.is_masked(z):
            z = z.filled(np.nan)

        # next: try some surgery, if possible
        if np.all(num.is_invalid(x)) or np.all(num.is_invalid(y)):
            return None
        if np.any(np.isnan(x)) or np.any(np.isnan(y)):
            x, y = interp_meshgrid_2d(x, y)
        if np.any(num.is_invalid(x)) or np.any(num.is_invalid(y)):
            x, y, z = num.crop2d(x, y, z)

        # next, check if the resulting grids are even still plottable
        for g in x, y, z:
            if g.size == 0:
                return None
            elif len(g.shape) < 2:
                return None

            # special case: if we have a single line, a pcolor-type plot won't work.
            elif min(g.shape) < 2:
                plotType = PlotType.scatter2d

    if plotType is PlotType.image:
        im = plotImage(ax, x, y, z, cmap=cmap, **kw)
    elif plotType is PlotType.colormesh:
        im = ppcolormesh_from_meshgrid(ax, x, y, z, cmap=cmap, **kw)
    elif plotType is PlotType.scatter2d:
        im = ax.scatter(x.ravel(), y.ravel(), c=z.ravel(), cmap=cmap, **kw)
    else:
        im = None

    if im is None:
        return None

    ax.set_xlabel(axLabels[0])
    ax.set_ylabel(axLabels[1])
    return im


def ppcolormesh_from_meshgrid(ax: Axes, x: np.ndarray, y: np.ndarray,
                              z: np.ndarray, **kw: Any) -> Union[AxesImage, None]:
    r"""Plot a pcolormesh with some reasonable defaults.
    Input are the corresponding arrays from a 2D ``MeshgridDataDict``.

    Will attempt to fix missing points in the coordinates.

    :param ax: subPlots to plot the colormesh into.
    :param x: x component of the meshgrid coordinates
    :param y: y component of the meshgrid coordinates
    :param z: data values
    :returns: the image returned by `pcolormesh`.

    Keywords are passed on to `pcolormesh`.
    """
    # the meshgrid we have describes coordinates, but for plotting
    # with pcolormesh we need vertices.
    try:
        x = centers2edges_2d(x)
        y = centers2edges_2d(y)
    except:
        return None

    im = ax.pcolormesh(x, y, z, **kw)
    ax.set_xlim(x.min(), x.max())
    ax.set_ylim(y.min(), y.max())
    return im


def plotImage(ax: Axes, x: np.ndarray, y: np.ndarray,
              z: np.ndarray, **kw: Any) -> AxesImage:
    """Plot 2d meshgrid data as image.

    :param ax: matplotlib subPlots to plot the image in.
    :param x: x coordinates (as meshgrid)
    :param y: y coordinates
    :param z: z values
    :returns: the image object returned by `imshow`

    All keywords are passed to `imshow`.
    """
    ax.grid(False)
    x0, x1 = x.min(), x.max()
    y0, y1 = y.min(), y.max()

    extentx = [x0, x1]
    if x0 > x1:
        extentx = extentx[::-1]
    if x0 == x1:
        extentx = [x0, x0 + 1]
    extenty = [y0, y1]
    if y0 > y1:
        extenty = extenty[::-1]
    if y0 == y1:
        extenty = [y0, y0 + 1]
    extent = tuple(extentx + extenty)

    if x.shape[0] > 1:
        # in image mode we have to be a little careful:
        # if the x/y subPlots are specified with decreasing values we need to
        # flip the image. otherwise we'll end up with an axis that has the
        # opposite ordering from the data.
        z = z if x[0, 0] < x[1, 0] else z[::-1, :]

    if y.shape[1] > 1:
        z = z if y[0, 0] < y[0, 1] else z[:, ::-1]

    im = ax.imshow(z.T, aspect='auto', origin='lower',
                   extent=extent, **kw)
    return im
