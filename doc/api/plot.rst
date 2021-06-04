Plotting elements
#################

.. _Base plot API:

Base plotting elements
^^^^^^^^^^^^^^^^^^^^^^

Overview
========

Classes for plotting functionality
----------------------------------

* :class:`.PlotNode` : The base class for a `.Node` with the purpose of receiving data for visualization.
* :class:`.PlotWidgetContainer` : A class that contains a `PlotWidget` (and can change it during runtime)
* :class:`.PlotWidget` : An abstract widget that can be inherited to implement actual plotting.
* :class:`.AutoFigureMaker` : A convenience class for semi-automatic generation of figures.
  The purpose is to keep actual plotting code out of the plot widget. This is not mandatory, just convenient.

Data structures
---------------

* :class:`.PlotDataType` : Enum with types of data that can be plotted.
* :class:`.ComplexRepresentation`: Enum with ways to represent complex-valued data.


Additional tools
----------------

* :func:`.makeFlowchartWithPlot` : convenience function for creating a flowchart that leads to a plot node.
* :func:`.determinePlotDataType` : try to infer which type of plot data is in a data set.

Object Documentation
====================

.. automodule:: plottr.plot.base
    :members:

.. _MPL plot API:

Matplotlib plotting tools
^^^^^^^^^^^^^^^^^^^^^^^^^

Overview
========

.. automodule:: plottr.plot.mpl
    :members:

Object Documentation
====================

General Widgets
---------------
.. automodule:: plottr.plot.mpl.widgets
    :members:

General plotting tools
----------------------
.. automodule:: plottr.plot.mpl.plotting
    :members:

Autoplot
--------
.. automodule:: plottr.plot.mpl.autoplot
    :members:
