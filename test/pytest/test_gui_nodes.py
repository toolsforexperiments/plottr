"""GUI smoke tests for plottr node widgets and plot windows.

These tests verify that node UIs build inside a flowchart, accept data through
the flowchart, and that the plot windows can be constructed and fed data under
the active Qt binding (PySide6 by default).

They are the pytest-qt successors of the old interactive scripts that used to
live under ``test/gui`` (``data_selector.py``, ``ddh5_loader.py``,
``dimension_assignment.py``, ``grid_options.py``, ``correct_offset.py`` and
``simple_2d_plot.py``).
"""

import numpy as np
import pytest

from plottr.data import datadict_storage as dds
from plottr.data.datadict_storage import DDH5LoaderWidget
from plottr.data.datadict import MeshgridDataDict, datadict_to_meshgrid
from plottr.gui import PlotWindow
from plottr.gui.widgets import makeFlowchartWithPlotWindow
from plottr.node.data_selector import DataSelector, DataDisplayWidget
from plottr.node.dim_reducer import (
    DimensionReducer,
    DimensionReducerNodeWidget,
    XYSelector,
    XYSelectorNodeWidget,
)
from plottr.node.filter.correct_offset import SubtractAverage, SubtractAverageWidget
from plottr.node.grid import DataGridder, DataGridderNodeWidget, GridOption
from plottr.node.tools import linearFlowchart
from plottr.plot.mpl import AutoPlot
from plottr.utils import testdata


# Several other test modules set ``<NodeClass>.useUi = False`` and even
# ``<NodeClass>.uiClass = None`` (class attributes) and don't restore them,
# which would suppress UI creation here depending on test order. The widget
# classes themselves are unaffected by that pollution, so we reference them
# directly; the fixture below forces UI creation for the node classes exercised
# in this file and restores the previous values afterwards.
_NODE_UI_CLASSES = {
    DataSelector: DataDisplayWidget,
    dds.DDH5Loader: DDH5LoaderWidget,
    DimensionReducer: DimensionReducerNodeWidget,
    XYSelector: XYSelectorNodeWidget,
    DataGridder: DataGridderNodeWidget,
    SubtractAverage: SubtractAverageWidget,
}


@pytest.fixture
def node_ui_enabled():
    saved = {cls: (cls.useUi, cls.uiClass) for cls in _NODE_UI_CLASSES}
    for cls, ui_class in _NODE_UI_CLASSES.items():
        cls.useUi = True
        cls.uiClass = ui_class
    yield
    for cls, (use_ui, ui_class) in saved.items():
        cls.useUi = use_ui
        cls.uiClass = ui_class


# -- node UIs in a flowchart ---------------------------------------------------

def test_data_selector_node_ui(qtbot, node_ui_enabled):
    """The DataSelector node builds its UI and accepts data."""
    fc = linearFlowchart(('selector', DataSelector))
    node = fc.nodes()['selector']
    assert node.ui is not None
    qtbot.addWidget(node.ui)

    data = testdata.three_incompatible_3d_sets(2, 2, 2)
    fc.setInput(dataIn=data)
    node.selectedData = ['data']
    assert fc.outputValues()['dataOut'] is not None


def test_ddh5_loader_node_ui(qtbot, node_ui_enabled):
    """The DDH5Loader node builds its UI."""
    fc = linearFlowchart(('loader', dds.DDH5Loader))
    node = fc.nodes()['loader']
    assert node.ui is not None
    qtbot.addWidget(node.ui)


def test_dimension_reducer_node_ui(qtbot, node_ui_enabled):
    """The DimensionReducer node builds its UI and passes meshgrid data through."""
    fc = linearFlowchart(('reducer', DimensionReducer))
    node = fc.nodes()['reducer']
    assert node.ui is not None
    qtbot.addWidget(node.ui)

    data = datadict_to_meshgrid(testdata.three_compatible_3d_sets(5, 5, 5))
    fc.setInput(dataIn=data)
    out = fc.outputValues()['dataOut']
    assert isinstance(out, MeshgridDataDict)
    # the embedded selection widget gets one row per axis.
    assert node.ui.widget.topLevelItemCount() == len(data.axes())


def test_xy_selector_node_ui(qtbot, node_ui_enabled):
    """The XYSelector node builds its UI and is populated from meshgrid data.

    Without explicit x/y role assignment the node output is ``None`` (it cannot
    determine the plot axes yet); we therefore assert on the populated UI.
    """
    fc = linearFlowchart(('xysel', XYSelector))
    node = fc.nodes()['xysel']
    assert node.ui is not None
    qtbot.addWidget(node.ui)

    data = datadict_to_meshgrid(testdata.three_compatible_3d_sets(5, 5, 5))
    fc.setInput(dataIn=data)
    assert node.ui.widget.topLevelItemCount() == len(data.axes())
    assert 'dataOut' in fc.outputValues()


def test_data_gridder_node_ui(qtbot, node_ui_enabled):
    """The DataGridder node builds its UI and grids non-grid data on request."""
    fc = linearFlowchart(('grid', DataGridder))
    node = fc.nodes()['grid']
    assert node.ui is not None
    qtbot.addWidget(node.ui)

    data = testdata.three_compatible_3d_sets(5, 5, 5)
    fc.setInput(dataIn=data)

    node.grid = GridOption.guessShape, {}

    out = fc.outputValues()['dataOut']
    assert isinstance(out, MeshgridDataDict)


# -- plot windows --------------------------------------------------------------

def test_subtract_average_with_plot_window(qtbot, node_ui_enabled):
    """A flowchart with a plot window accepts (and re-accepts) meshgrid data."""
    win, fc = makeFlowchartWithPlotWindow([('sub', SubtractAverage)])
    qtbot.addWidget(win)

    x = np.arange(11) - 5.
    y = np.linspace(0, 10, 51)
    xx, yy = np.meshgrid(x, y, indexing='ij')
    zz = np.sin(yy) + xx
    data = MeshgridDataDict(
        x=dict(values=xx),
        y=dict(values=yy),
        z=dict(values=zz, axes=['x', 'y']),
    )
    data.validate()
    fc.setInput(dataIn=data)

    data2 = MeshgridDataDict(
        reps=dict(values=xx),
        y=dict(values=yy),
        z=dict(values=zz, axes=['reps', 'y']),
    )
    data2.validate()
    fc.setInput(dataIn=data2)

    assert fc.outputValues()['dataOut'] is not None


def test_plot_window_with_mpl_autoplot(qtbot):
    """A PlotWindow with an MPL AutoPlot accepts 1d and 2d data."""
    win = PlotWindow()
    qtbot.addWidget(win)
    plot = AutoPlot(parent=win)
    win.plot.setPlotWidget(plot)

    data_1d = datadict_to_meshgrid(testdata.get_1d_scalar_cos_data(21, 1))
    win.plot.setData(data_1d)

    data_2d = datadict_to_meshgrid(testdata.get_2d_scalar_cos_data(21, 11, 1))
    win.plot.setData(data_2d)
