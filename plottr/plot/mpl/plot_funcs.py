"""
plottr/plot/mpl.py : Tools for plotting with matplotlib.


"""

import logging
import io
from enum import Enum, unique, auto
from typing import Dict, List, Tuple, Union, cast, Type, Optional, Any
from collections import OrderedDict

# standard scientific computing imports
import numpy as np
from matplotlib.image import AxesImage
from matplotlib import rcParams, cm, colors, pyplot as plt
from matplotlib.axes import Axes
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FCanvas,
    NavigationToolbar2QT as NavBar,
)
from matplotlib.figure import Figure
from mpl_toolkits.axes_grid1 import make_axes_locatable

from plottr import QtGui, QtCore, Signal, Slot, QtWidgets, configFiles
from plottr.utils import num
from plottr.utils.num import interp_meshgrid_2d, centers2edges_2d
from plottr.data.datadict import DataDictBase, DataDict, MeshgridDataDict
from plottr.icons import (get_singleTracePlotIcon, get_multiTracePlotIcon, get_imagePlotIcon,
                          get_colormeshPlotIcon, get_scatterPlot2dIcon)

from ..base import PlotWidget

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


# TODO: might be handy to develop some form of figure manager class,
#   into which we can dump various types of data, and that figures
#   out the general layout/labeling, etc.
#   could be a context manager, where during the enter we just accumulate infos,
#   and do the plotting only at the end.

# def setMplDefaults() -> None:
#     """Set some reasonable matplotlib defaults for appearance."""
#
#     rcParams['figure.dpi'] = 300
#     rcParams['figure.figsize'] = (4.5, 3)
#     rcParams['savefig.dpi'] = 300
#     rcParams['subPlots.grid'] = True
#     rcParams['grid.linewidth'] = 0.5
#     rcParams['grid.linestyle'] = ':'
#     rcParams['font.family'] = 'Arial', 'Helvetica', 'DejaVu Sans'
#     rcParams['font.size'] = 6
#     rcParams['lines.markersize'] = 3
#     rcParams['lines.linestyle'] = '-'
#     rcParams['savefig.transparent'] = False
#     rcParams['figure.subplot.bottom'] = 0.15
#     rcParams['figure.subplot.top'] = 0.85
#     rcParams['figure.subplot.left'] = 0.15
#     rcParams['figure.subplot.right'] = 0.9


# 2D plots
def colorplot2d(ax: Axes, x: np.ndarray, y: np.ndarray, z: np.ndarray,
                style: PlotType = PlotType.image,
                axLabels: Tuple[Optional[str], Optional[str], Optional[str]] = ('', '', ''),
                **kw: Any) -> None:
    """make a 2d colorplot. what plot is made, depends on `style`.
    Any of the 2d plot types in :class:`PlotType` works.

    :param ax: matplotlib subPlots to plot in
    :param x: x coordinates (meshgrid)
    :param y: y coordinates (meshgrid)
    :param z: z data
    :param style: the plot type
    :param axLabels: labels for the x, y subPlots, and the colorbar.

    all keywords are passed to the actual plotting functions:
    
    - :attr:`PlotType.image` --
        :func:`plotImage`
    - :attr:`PlotType.colormesh` --
        :func:`ppcolormesh_from_meshgrid`
    - :attr:`PlotType.scatter2d` --
        matplotlib's `scatter`
    """
    cmap = kw.pop('cmap', default_cmap)

    # first we need to check if our grid can be plotted nicely.
    if style in [PlotType.image, PlotType.colormesh]:
        x = x.astype(float)
        y = y.astype(float)
        z = z.astype(float)

        # first check if we need to fill some masked values in
        if np.ma.is_masked(x):
            x = x.filled(np.nan)
        if np.ma.is_masked(y):
            y = y.filled(np.nan)
        if np.ma.is_masked(z):
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
                style = PlotType.scatter2d

    if style is PlotType.image:
        im = plotImage(ax, x, y, z, cmap=cmap, **kw)
    elif style is PlotType.colormesh:
        im = ppcolormesh_from_meshgrid(ax, x, y, z, cmap=cmap, **kw)
    elif style is PlotType.scatter2d:
        im = ax.scatter(x, y, c=z, cmap=cmap, **kw)

    if im is None:
        return

    cax = attachColorBar(ax, im)
    ax.set_xlabel(axLabels[0])
    ax.set_ylabel(axLabels[1])
    cax.set_ylabel(axLabels[2])


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
        extentx = [x0, x0+1]
    extenty = [y0, y1]
    if y0 > y1:
        extenty = extenty[::-1]
    if y0 == y1:
        extenty = [y0, y0+1]
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






