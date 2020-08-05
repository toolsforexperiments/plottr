import os
from plottr import QtGui, QtCore, plottrPath

gfxPath = os.path.join(plottrPath, 'resource', 'gfx')

# Template
# Icon = QtGui.QIcon(
#     os.path.join(gfxPath, ".svg")
# )

# Plot types
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

dataColumnsIcon = QtGui.QIcon(
    os.path.join(gfxPath, "data_columns.svg")
)

axesAssignIcon = QtGui.QIcon(
    os.path.join(gfxPath, "axes_assign.svg")
)

gridIcon = QtGui.QIcon(
    os.path.join(gfxPath, "grid.svg")
)

xySelectIcon = QtGui.QIcon(
    os.path.join(gfxPath, "xy_select.svg")
)