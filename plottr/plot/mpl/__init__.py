"""
``plottr.plot.mpl`` -- matplotlib plotting system for plottr.
Contains the following main objects:

Base UI elements
----------------

* :class:`.widgets.MPLPlot` (``matplotlib.backends.backend_qt5agg.FigureCanvasQTAgg``) --
  Figure and Canvas widget.
  The most elementary Qt widget that contains the the matplotlib figure instance.

* :class:`.widgets.MPLPlotWidget` (:class:`plottr.plot.base.PlotWidget`) --
  A widget that contains the figure/canvas

General plotting functionality
------------------------------

* :class:`.plotting.PlotType` --
  Enum for currently implemented plot types in automatic plotting.

Automatic plotting
------------------

* :class:`.autoplot.AutoPlot` (:class:`.mpl.widgets.PlotWidget`) --
  PlotWidget that allows user selection of plot types and plots using
  :class:`.autoplot.FigureMaker`.

* :class:`.autoplot.FigureMaker` (:class:`.base.AutoFigureMaker`) --
  Matplotlib implementation of the figure manager.

Utilities
---------
* :func:`.widgets.figureDialog` --
  make a dialog window containing a plot widget.

Configuration
-------------
This module looks for a file `plottr_default.mplstyle` in the plottr config
directories and applies it to matplotlib plots using `pyplot.style.use`.

"""
import logging

from matplotlib import rcParams, cm, pyplot as plt

from plottr import configFiles
from .autoplot import AutoPlot, FigureMaker
from .widgets import MPLPlot, MPLPlotWidget


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# matplotlib tools and settings
symmetric_cmap = cm.get_cmap('bwr')
