"""GUI smoke tests for standalone plottr widgets.

These tests verify that the data-display, dimension-selection and gridding
widgets can be constructed, populated with data, and emit their selection
signals without raising under the active Qt binding (PySide6 by default).

They are the pytest-qt successors of the old interactive scripts that used to
live under ``test/gui`` (``data_display_widgets.py``,
``dimension_selection_widgets.py`` and ``grid_options.py``).
"""

import numpy as np

from plottr.data.datadict import str2dd, datadict_to_meshgrid
from plottr.gui.data_display import DataSelectionWidget
from plottr.gui.widgets import (
    AxisSelector,
    DependentSelector,
    DimensionSelector,
    MultiDimensionSelector,
)
from plottr.node.grid import GridOption, GridOptionWidget, ShapeSpecificationWidget
from plottr.node.dim_reducer import XYSelectionWidget
from plottr.utils import testdata


# -- data display --------------------------------------------------------------

def test_data_selection_widget_set_and_clear(qtbot):
    """The selection widget accepts data, can be cleared, and re-populated."""
    widget = DataSelectionWidget()
    qtbot.addWidget(widget)

    data = testdata.three_incompatible_3d_sets(5, 5, 5)
    widget.setData(data.structure(), data.shapes())
    assert set(widget.dataItems.keys()) == set(data.dependents())

    widget.clear()
    assert widget.dataItems == {}

    widget.setData(data.structure(), data.shapes())
    assert set(widget.dataItems.keys()) == set(data.dependents())


def test_data_selection_widget_readonly(qtbot):
    """A read-only selection widget still displays the data fields."""
    widget = DataSelectionWidget(readonly=True)
    qtbot.addWidget(widget)

    data = testdata.three_incompatible_3d_sets(2, 2, 2)
    widget.setData(data.structure(), data.shapes())
    assert len(widget.dataItems) == len(data.dependents())


# -- dimension selection -------------------------------------------------------

def test_dimension_selector_emits(qtbot):
    """Selecting a dimension in the combo emits ``dimensionSelected``."""
    data = str2dd("data1(x,y,z); data2(x,z);")
    widget = DimensionSelector()
    qtbot.addWidget(widget)

    dims = data.axes() + data.dependents()
    widget.combo.setDimensions(dims)
    # every available dimension is offered in the combo (plus the 'None' entry).
    combo_entries = [widget.combo.itemText(i) for i in range(widget.combo.count())]
    for d in dims:
        assert d in combo_entries

    with qtbot.waitSignal(widget.combo.dimensionSelected, timeout=1000):
        widget.combo.setCurrentText(dims[0])


def test_axis_and_dependent_selectors(qtbot):
    """Axis/dependent selectors populate their combo from the given dimensions."""
    data = str2dd("data1(x,y,z); data2(x,z);")

    axis_sel = AxisSelector()
    qtbot.addWidget(axis_sel)
    axis_sel.combo.setDimensions(data.axes())
    axis_entries = [axis_sel.combo.itemText(i)
                    for i in range(axis_sel.combo.count())]
    for ax in data.axes():
        assert ax in axis_entries

    dep_sel = DependentSelector()
    qtbot.addWidget(dep_sel)
    dep_sel.combo.setDimensions(data.dependents())
    dep_entries = [dep_sel.combo.itemText(i)
                   for i in range(dep_sel.combo.count())]
    for dep in data.dependents():
        assert dep in dep_entries


def test_multi_dimension_selector(qtbot):
    """The multi-selector lists all dimensions and emits on selection."""
    data = str2dd("data1(x,y,z); data2(x,z);")
    dims = data.axes() + data.dependents()

    widget = MultiDimensionSelector()
    qtbot.addWidget(widget)
    widget.setDimensions(dims)
    assert widget.count() == len(dims)

    with qtbot.waitSignal(widget.dimensionSelectionMade, timeout=1000):
        widget.setSelected([dims[0]])
    assert widget.getSelected() == [dims[0]]


# -- gridding ------------------------------------------------------------------

def test_shape_specification_widget(qtbot):
    """ShapeSpecificationWidget takes axes and a shape and reports it back."""
    widget = ShapeSpecificationWidget()
    qtbot.addWidget(widget)

    axes = ['x', 'y', 'aVeryVeryVeryVeryLongAxisName']
    widget.setAxes(axes)
    widget.setShape({'order': axes, 'shape': (5, 5, 5)})

    shape = widget.getShape()
    assert list(shape['order']) == axes
    assert tuple(shape['shape']) == (5, 5, 5)


def test_grid_option_widget_emits(qtbot):
    """Selecting a grid option via its radio button emits ``optionSelected``."""
    data = datadict_to_meshgrid(testdata.three_compatible_3d_sets(5, 5, 5))
    widget = GridOptionWidget()
    qtbot.addWidget(widget)
    widget.setAxes(data.axes())

    with qtbot.waitSignal(widget.optionSelected, timeout=1000):
        widget.buttons[GridOption.guessShape].setChecked(True)


# -- xy selection (standalone widget) ------------------------------------------

def test_xy_selection_widget(qtbot):
    """XYSelectionWidget populates one row per axis of meshgrid data."""
    data = datadict_to_meshgrid(testdata.three_compatible_3d_sets(4, 4, 4))
    widget = XYSelectionWidget()
    qtbot.addWidget(widget)

    widget.setData(data.structure(), data.shapes(), type(data))
    assert widget.topLevelItemCount() == len(data.axes())

    # clearing and re-setting data should be idempotent in row count.
    widget.clear()
    widget.setData(data.structure(), data.shapes(), type(data))
    assert widget.topLevelItemCount() == len(data.axes())
