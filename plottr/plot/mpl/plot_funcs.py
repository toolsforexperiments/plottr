import numpy as np
from matplotlib import pyplot as plt
from matplotlib.axes import Axes


def plot_line(ax: Axes, x: np.ndarray, y: np.ndarray, **kw) -> None:
    """Plot 1D data.

    :param ax: Axes to plot into
    :param x: x values
    :param y: y values

    All keywords are passed to matplotlib's `plot` function.
    """

    if isinstance(x, np.ma.MaskedArray):
        x = x.filled(np.nan)
    if isinstance(y, np.ma.MaskedArray):
        y = y.filled(np.nan)

    # if we're plotting real and imaginary parts, modify the label
    lbl = None
    lbl_imag = None
    if np.issubsctype(y, np.complexfloating):
        if curveLabel is None:
            lbl = 'Re'
            lbl_imag = 'Im'
        else:
            lbl = f"Re({curveLabel})"
            lbl_imag = f"Im({curveLabel})"
    if lbl is None:
        lbl = curveLabel

    line, = ax.plot(x, y.real, fmt, label=lbl, **plot_kw)
    if np.issubsctype(y, np.complexfloating):
        plot_kw['dashes'] = [2, 2]
        plot_kw['color'] = line.get_color()
        fmt = 's' + fmt[1:]
        ax.plot(x, y.imag, fmt, label=lbl_imag, **plot_kw)
