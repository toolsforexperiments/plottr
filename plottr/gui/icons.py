import os
from .. import QtGui, QtCore, plottrPath

gfxPath = os.path.join(plottrPath, 'gui', 'gfx')

singleTracePlotIcon = QtGui.QIcon(
    os.path.join(gfxPath, "single_trace_plot.svg")
)

multiTracePlotIcon = QtGui.QIcon(
    os.path.join(gfxPath, "multi_trace_plot.svg")
)

imagePlotIcon = QtGui.QIcon(
    os.path.join(gfxPath, "image_plot.svg")
)

colormeshPlotIcon = QtGui.QIcon(
    os.path.join(gfxPath, "colormesh_plot.svg")
)

scatterPlot2dIcon = QtGui.QIcon(
    os.path.join(gfxPath, "2dscatter_plot.svg")
)