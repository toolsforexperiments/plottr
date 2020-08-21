import os
from plottr import QtGui, QtCore, plottrPath

gfxPath = os.path.join(plottrPath, 'resource', 'gfx')

# The pyqt versions shipped by anaconda (both main channel and conda forge)
# are not able to render svg icons if the QIcon is created before the
# main qapp is up and running. To work around this we wrapp all of them
# in a function that returns the instance rather than creating them up
# front.


def get_singleTracePlotIcon() -> QtGui.QIcon:
    # Plot types
    singleTracePlotIcon = QtGui.QIcon(
        os.path.join(gfxPath, "single_trace_plot.svg")
    )
    return singleTracePlotIcon


def get_multiTracePlotIcon() -> QtGui.QIcon:
    # Plot types
    multiTracePlotIcon = QtGui.QIcon(
        os.path.join(gfxPath, "multi_trace_plot.svg")
    )
    return multiTracePlotIcon


def get_imagePlotIcon() -> QtGui.QIcon:
    imagePlotIcon = QtGui.QIcon(
        os.path.join(gfxPath, "image_plot.svg")
    )
    return imagePlotIcon


def get_colormeshPlotIcon() -> QtGui.QIcon:
    colormeshPlotIcon = QtGui.QIcon(
        os.path.join(gfxPath, "colormesh_plot.svg")
    )
    return colormeshPlotIcon


def get_scatterPlot2dIcon() -> QtGui.QIcon:
    scatterPlot2dIcon = QtGui.QIcon(
        os.path.join(gfxPath, "2dscatter_plot.svg")
    )
    return scatterPlot2dIcon


def get_dataColumnsIcon() -> QtGui.QIcon:
    dataColumnsIcon = QtGui.QIcon(
        os.path.join(gfxPath, "data_columns.svg")
    )
    return dataColumnsIcon

def get_axesAssignIcon() -> QtGui.QIcon:
    axesAssignIcon = QtGui.QIcon(
        os.path.join(gfxPath, "axes_assign.svg")
    )
    return axesAssignIcon


def get_gridIcon() -> QtGui.QIcon:
    gridIcon = QtGui.QIcon(
        os.path.join(gfxPath, "grid.svg")
    )
    return gridIcon


def get_xySelectIcon() -> QtGui.QIcon:
    xySelectIcon = QtGui.QIcon(
        os.path.join(gfxPath, "xy_select.svg")
    )
    return xySelectIcon
