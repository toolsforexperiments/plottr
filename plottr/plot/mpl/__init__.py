"""plottr/plot/mpl/ -- matplotlib plotting system for plottr.

Overview of the main objects
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- :class:`.mpl.base.MPLPlot` --
  Figure and Canvas management. The most elementary Qt widget that contains the
  the matplotlib figure instance.


Configuration
^^^^^^^^^^^^^
This module looks for a file `plottr_default.mplstyle` in the config
directories and applies it to matplotlib plots using `pyplot.style.use`.

"""
import logging

from matplotlib import rcParams, cm, pyplot as plt

from plottr import configFiles
from .autoplot import AutoPlot, FigureMaker
from .widgets import MPLPlot, MPLPlotWidget


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def setStyle() -> None:
    """Set the matplotlib style based on available config files."""
    styleFiles = configFiles('plottr_default.mplstyle')
    if len(styleFiles) > 0:
        plt.style.use(styleFiles[0])
        logger.info(f'Using matplotlib style: {styleFiles[0]}')


setStyle()


# matplotlib tools and settings
default_prop_cycle = rcParams['axes.prop_cycle']
default_cmap = cm.get_cmap('magma')
symmetric_cmap = cm.get_cmap('bwr')
