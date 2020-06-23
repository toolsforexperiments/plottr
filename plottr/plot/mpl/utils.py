from matplotlib import pyplot as plt
from matplotlib.axes import Axes
from mpl_toolkits.axes_grid1 import make_axes_locatable

def attach_color_ax(ax: Axes) -> Axes:
    """Attach a colorbar to the `AxesImage` `im` that was plotted
    into `Axes` `ax`.

    :returns: the newly generated color bar axes.
    """
    div = make_axes_locatable(ax)
    cax = div.append_axes("right", size="5%", pad=0.05)
    return cax