"""
plottr.plot.mpl.autoplot -- tools for automatically generating plots from
input data.
"""


from typing import Dict, List, Tuple, Union
from collections import OrderedDict

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.axes import Axes
from matplotlib.image import AxesImage

from . import PlotDataType, ComplexRepresentation
from .utils import attach_color_ax


def _generate_auto_dict_key(d: Dict):
    guess = 0
    while guess in d.keys():
        guess += 1
    return guess


class FigureMakerBase(object):
    """Automatic creation of figures based on input data.

    FigureMakerBase is a context manager. The user should eventually only need to
    add data and specify what kind of data it is. FigureMakerBase will then generate
    plots from that.

    In the simplest form, usage looks something like this::

        >>> with FigureMakerBase() as fm:
        >>>     fm.add_plot(plot_func, xvals, yvals)
        >>>     [...]

    See :method:`add_plot` for details on how to specify data and how to plot it.

    This base class still requires specifying a plot function when adding data.
    This is mainly to create a uniform blueprint on how to implement data adding
    and plotting.
    Inheriting classes have more specific methods for adding data, which automatically
    use predefined plot functions.
    """

    # TODO: implement feature for always plotting certain traces with other
    #   other ones ('children'). This is mainly used for models/fits.
    #   needs a system to copy certain style aspects from the parents.
    # TODO: similar, but with siblings (imagine Re/Im parts)
    # TODO: need a system for styling based on a name filter
    # TODO: need a system for styling with style sets
    # TODO: support for error bars
    # TODO: marker filling with a different alpha/tint than the rest of the curve

    default_style = None

    def __init__(self):

        self.axes = OrderedDict()
        self.plot_items = OrderedDict()
        self.images = OrderedDict()
        self.layout = 'grid-square'
        self.figsize = 'auto'
        self.fig = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._make_axes()
        for axname in self.axes.keys():
            self._plot_axes(axname)

        self.fig.tight_layout()

    # private methods
    def _make_axes(self):
        nax = len(self.axes)
        if self.layout == 'grid-square':
            nrows = int(nax ** .5 + .5)
            ncols = np.ceil(nax / nrows)
        else:
            raise ValueError('only grid-square layout supported.')

        if self.figsize == 'auto':
            size = ncols * 3 + 1, nrows * 2 + 1
        else:
            size = self.figsize

        if self.default_style is not None:
            plt.style.use(self.default_style)

        self.fig = plt.figure(figsize=size)
        for i, ax_name in zip(range(1, nax + 1), self.axes.keys()):
            self.axes[ax_name]['axes'] = self.fig.add_subplot(nrows, ncols, i)

    def _plot_axes(self, axname):
        plot_names = self._find_ax_plots(axname)

        xlbls = {}
        ylbls = {}
        clbls = {}
        for n in plot_names:
            dlbls = self.plot_items[n]['dim_labels']
            if dlbls is not None:
                if len(dlbls) >= 1 and dlbls[0] is not None:
                    xlbls[n] = dlbls[0]
                if len(dlbls) >= 2 and dlbls[1] is not None:
                    ylbls[n] = dlbls[1]
                if len(dlbls) >= 3 and dlbls[2] is not None:
                    clbls[n] = dlbls[2]

        xlabel = ''
        ylabel = ''
        clabel = ''

        if len(set(xlbls.values())) == 1:
            xlabel = list(xlbls.values())[0]
        if len(set(ylbls.values())) == 1:
            ylabel = list(ylbls.values())[0]
        if len(set(clbls.values())) == 1:
            clabel = list(clbls.values())[0]

        has_legend = False
        for n in plot_names:
            label = self.plot_items[n]['plot_kwargs'].pop('label', None)
            if len(set(xlbls.values())) > 1 and n in xlbls:
                if label is None:
                    label = f"vs. {xlbls[n]}"
                else:
                    label = f"vs. {xlbls[n]}: {label}"

            if len(set(ylbls.values())) > 1 and n in ylbls:
                if label is None:
                    label = f"{ylbls[n]}"
                else:
                    if len(label) > 3 and label[:3] == 'vs.':
                        label = f"{ylbls[n]} {label}"
                    else:
                        label = f"{ylbls[n]}: {label}"

            if label is not None:
                has_legend = True
            self._plot(n, label=label)

        ax = self.axes[axname]['axes']
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if has_legend:
            ax.legend(loc=1)

        if self.axes[axname]['cax'] is not None:
            self.axes[axname]['cax'].set_ylabel(clabel)

    def _find_ax_plots(self, axname: str) -> List[str]:
        plotnames = []
        for tn, to in self.plot_items.items():
            if to['ax'] == axname:
                plotnames.append(tn)
        return plotnames

    def _plot(self, name, **plot_kwargs):
        item = self.plot_items[name]
        pf = item['plot_func']
        data = list(item['data'])
        ax = self.axes[item['ax']]

        # if we have z-values, then that means we need to have a color axes
        axlst = [ax['axes']]
        if len(data) > 2 and ax['cax'] is None:
            ax['cax'] = attach_color_ax(ax['axes'])

        # assemble the call to the plot function
        args = axlst + data
        opts = item['plot_kwargs'].copy()
        opts.update(plot_kwargs)

        ret = self.plot_items[name]['artist'] = pf(*args, **opts)
        if len(data) > 2 and isinstance(ret, AxesImage):
            if 'colorbar' not in self.plot_items[name]:
                cb = self.plot_items[name]['colorbar'] = \
                    self.fig.colorbar(ret, cax=ax['cax'])

    # public methods
    def add_plot(self, plot_func, *data, ax=None, name=None, join=None,
                 dim_labels=None, **plot_kwargs) -> str:

        if name is None:
            name = _generate_auto_dict_key(self.plot_items)

        if ax is None and join is None:
            ax = self.add_axes()
        elif join is not None:
            ax = self.plot_items[join]['ax']
        elif ax == 'prev':
            ax = next(reversed(self.axes))

        self.plot_items[name] = dict(
            ax=ax,
            plot_func=plot_func,
            data=data,
            dim_labels=dim_labels,
            plot_kwargs=plot_kwargs,
        )

        return name

    def add_axes(self, name=None) -> str:
        if name is None:
            name = _generate_auto_dict_key(self.axes)

        self.axes[name] = dict(
            axes=None,
            cax=None,
        )

        return name


class FigureMaker(FigureMakerBase):
    """A context manager for (somewhat-)automatic plotting of data.

    The idea is that the user only needs to describe the type of data that's
    added to the Figure Maker.
    The appropriate plotting method is inferred, but the user can still customize
    when needed.

    Basic usage principle::

        >>> with FigureMaker() as fm:
        >>>     fm.add_*(*data, **opts)
        >>>     [...]

    Here, `add_*` is a place holder for several ways to add different kinds of
    data.

    At the moment there are the following methods to add plot data:

    - :meth:`add_line` --
      add a 1d trace of data, x and y values. Will result in a line plot.
      If complex data is given in y, :attr:`complex_representation` governs how the
      data is plotted.
    """

    def __init__(self):
        super().__init__()

        #: how to represent complex data.
        self.complex_representation = ComplexRepresentation.realAndImag

    def add_line(self, x, y, **kwarg):
        if isinstance(x, np.ma.MaskedArray):
            x = x.filled(np.nan)
        if isinstance(y, np.ma.MaskedArray):
            y = y.filled(np.nan)

        if np.issubsctype(y, np.complexfloating):

            if self.complex_representation is ComplexRepresentation.realAndImag:

                label = kwarg.pop('label', None)
                if label is None:
                    re_label = 'Real'
                    im_label = 'Imag'
                else:
                    re_label = label + ' (Real)'
                    im_label = label + ' (Imag)'

                kwarg['label'] = re_label
                re = self.add_plot(lambda ax, *arg, **kw: ax.plot(*arg, **kw),
                                   x, y.real, **kwarg)
                kw_im = kwarg.copy()
                kw_im['join'] = re
                kw_im['label'] = im_label
                im = self.add_plot(lambda ax, *arg, **kw: ax.plot(*arg, **kw),
                                   x, y.imag, **kw_im)
                return re

            elif self.complex_representation is ComplexRepresentation.magAndPhase:

                label = kwarg.pop('label', None)
                if label is None:
                    mag_label = 'Mag'
                    phase_label = 'Phase'
                else:
                    mag_label = label + ' (Mag)'
                    phase_label = label + ' (Phase)'

                kw_mag = kwarg.copy()
                kw_mag['label'] = mag_label
                mag = self.add_plot(lambda ax, *arg, **kw: ax.plot(*arg, **kw),
                                    x, np.abs(y), **kw_mag)

                kw_phase = kwarg.copy()
                kw_phase['label'] = phase_label
                join = kwarg.pop('join', None)
                if join is not None:
                    kw_phase['join'] = self.plot_items[join].get('phase_plot', None)
                phase = self.add_plot(lambda ax, *arg, **kw: ax.plot(*arg, **kw),
                                      x, np.angle(y), **kw_phase)
                self.plot_items[mag]['phase_plot'] = phase

                if join is not None and 'phase_plot' not in self.plot_items[join]:
                    self.plot_items[join]['phase_plot'] = phase

                return mag

            elif self.complex_representation is ComplexRepresentation.real:

                return self.add_plot(lambda ax, *arg, **kw: ax.plot(*arg, **kw),
                                     x, y.real, **kwarg)

        else:
            return self.add_plot(lambda ax, *arg, **kw: ax.plot(*arg, **kw),
                                 x, y, **kwarg)
