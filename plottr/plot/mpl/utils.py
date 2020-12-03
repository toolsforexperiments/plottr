from typing import Optional

import numpy as np
from matplotlib import pyplot as plt, colors
from matplotlib.axes import Axes
from mpl_toolkits.axes_grid1 import make_axes_locatable


class SymmetricNorm(colors.Normalize):
    """Color norm that's symmetric and linear around a center value."""
    def __init__(self, vmin: Optional[float] = None,
                 vmax: Optional[float] = None,
                 vcenter: float = 0,
                 clip: bool = False):
        super().__init__(vmin, vmax, clip)
        self.vcenter = vcenter

    def __call__(self, value: float, clip: Optional[bool] = None) -> np.ma.core.MaskedArray:
        vlim = max(abs(self.vmin-self.vcenter), abs(self.vmax-self.vcenter))
        self.vmax: float = vlim+self.vcenter
        self.vmin: float = -vlim+self.vcenter
        return super().__call__(value, clip)


def attachColorAx(ax: Axes) -> Axes:
    """Attach a colorbar to the `AxesImage` `im` that was plotted
    into `Axes` `ax`.

    :returns: the newly generated color bar subPlots.
    """
    div = make_axes_locatable(ax)
    cax = div.append_axes("right", size="5%", pad=0.05)
    return cax

