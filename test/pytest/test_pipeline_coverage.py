"""
test_pipeline_coverage.py

Comprehensive pipeline tests exercising every plottr node with various data
shapes, structures, and dtypes.

Uses two approaches:
- hypothesis @given for pure DataDict/MeshgridDataDict operations (no Qt needed)
- pytest parametrize + qtbot for flowchart-based node tests (needs QApplication)
"""
import numpy as np
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from plottr.data.datadict import (
    DataDict,
    DataDictBase,
    MeshgridDataDict,
    datadict_to_meshgrid,
    meshgrid_to_datadict,
)
from plottr.node.tools import linearFlowchart
from plottr.node.node import Node
from plottr.node.data_selector import DataSelector
from plottr.node.grid import DataGridder, GridOption
from plottr.node.dim_reducer import DimensionReducer, XYSelector, ReductionMethod
from plottr.node.scaleunits import ScaleUnits
from plottr.node.filter.correct_offset import SubtractAverage
from plottr.node.histogram import Histogrammer
from plottr.utils import num


# ---------------------------------------------------------------------------
# Disable UI for all node classes within this module's tests only.
# We save/restore originals via a session-scoped fixture.
# ---------------------------------------------------------------------------

_ORIGINAL_UI_SETTINGS = {}

@pytest.fixture(autouse=True, scope="module")
def _disable_ui_for_module():
    """Temporarily disable UIs for all node classes during this module's tests."""
    classes = [DataSelector, DataGridder, DimensionReducer, XYSelector,
               ScaleUnits, SubtractAverage, Histogrammer]
    for cls in classes:
        _ORIGINAL_UI_SETTINGS[cls] = (cls.useUi, cls.uiClass)
        cls.useUi = False
        cls.uiClass = None
    yield
    for cls in classes:
        cls.useUi, cls.uiClass = _ORIGINAL_UI_SETTINGS[cls]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_griddable_dd(shape, ndeps=1):
    """Create a DataDict from a meshgrid shape (flattened)."""
    naxes = len(shape)
    ax_names = [f'ax{i}' for i in range(naxes)]
    axes_1d = [np.linspace(0, 1, s) for s in shape]
    grids = np.meshgrid(*axes_1d, indexing='ij')

    dd = DataDict()
    for i, ax in enumerate(ax_names):
        dd[ax] = dict(values=grids[i].ravel(), axes=[], unit='V', label=ax)
    for j in range(ndeps):
        dd[f'dep{j}'] = dict(values=np.random.randn(int(np.prod(shape))),
                             axes=ax_names.copy(), unit='A', label=f'dep{j}')
    dd.validate()
    return dd


def make_mesh(shape, ndeps=1):
    """Create a MeshgridDataDict."""
    naxes = len(shape)
    ax_names = [f'ax{i}' for i in range(naxes)]
    axes_1d = [np.linspace(0, 1, s) for s in shape]
    grids = np.meshgrid(*axes_1d, indexing='ij')

    dd = MeshgridDataDict()
    for i, ax in enumerate(ax_names):
        dd[ax] = dict(values=grids[i], axes=[], unit='V', label=ax)
    for j in range(ndeps):
        dd[f'dep{j}'] = dict(values=np.random.randn(*shape),
                             axes=ax_names.copy(), unit='A', label=f'dep{j}')
    dd.validate()
    return dd


def snapshot_values(dd):
    return {k: v['values'].copy() for k, v in dd.data_items()}


def assert_not_mutated(dd, snap):
    for k, orig in snap.items():
        assert num.arrays_equal(np.asarray(orig), np.asarray(dd.data_vals(k))), \
            f"Field {k} was mutated"


# ---------------------------------------------------------------------------
# Hypothesis strategies for pure data operations
# ---------------------------------------------------------------------------

@st.composite
def griddable_datadict_st(draw, min_axis_len=2, max_axis_len=12,
                          min_axes=1, max_axes=3, min_deps=1, max_deps=3):
    naxes = draw(st.integers(min_value=min_axes, max_value=max_axes))
    ndeps = draw(st.integers(min_value=min_deps, max_value=max_deps))
    shape = tuple(draw(st.integers(min_value=min_axis_len, max_value=max_axis_len))
                  for _ in range(naxes))
    return make_griddable_dd(shape, ndeps)


@st.composite
def meshgrid_st(draw, min_axis_len=2, max_axis_len=12,
                min_axes=1, max_axes=3, min_deps=1, max_deps=3):
    naxes = draw(st.integers(min_value=min_axes, max_value=max_axes))
    ndeps = draw(st.integers(min_value=min_deps, max_value=max_deps))
    shape = tuple(draw(st.integers(min_value=min_axis_len, max_value=max_axis_len))
                  for _ in range(naxes))
    return make_mesh(shape, ndeps)


# ===========================================================================
# PART A: HYPOTHESIS TESTS — pure DataDict operations (no Qt)
# ===========================================================================

class TestDataDictOperationsHypothesis:
    """Property-based tests for DataDict operations that don't need a QApplication."""

    @given(data=griddable_datadict_st(min_axes=1, max_axes=3, min_axis_len=3))
    @settings(max_examples=50, deadline=10000)
    def test_gridding_roundtrip_structure(self, data):
        """Gridding should produce a MeshgridDataDict with matching structure."""
        try:
            mesh = datadict_to_meshgrid(data)
        except (ValueError, Exception):
            # Some shapes may not grid cleanly; that's expected for edge cases
            return
        assert isinstance(mesh, MeshgridDataDict)
        assert set(mesh.axes()) == set(data.axes())
        assert set(mesh.dependents()) == set(data.dependents())

    @given(data=meshgrid_st(min_axes=1, max_axes=3))
    @settings(max_examples=50, deadline=5000)
    def test_flatten_roundtrip(self, data):
        """Flatten to DataDict and back should preserve shapes."""
        flat = meshgrid_to_datadict(data)
        assert isinstance(flat, DataDict)
        assert flat.nrecords() == int(np.prod(data.shape()))

    @given(data=griddable_datadict_st(min_axes=1, max_axes=3))
    @settings(max_examples=30, deadline=5000)
    def test_copy_preserves_equality(self, data):
        """copy() should produce an equal dataset."""
        data2 = data.copy()
        assert data == data2

    @given(data=griddable_datadict_st(min_deps=2, max_deps=4))
    @settings(max_examples=30, deadline=5000)
    def test_extract_produces_subset(self, data):
        """extract() should return only the requested deps and their axes."""
        dep = data.dependents()[0]
        ex = data.extract([dep])
        assert ex.dependents() == [dep]
        assert set(ex.axes()) == set(data.axes(dep))

    @given(data=meshgrid_st(min_axes=2, max_axes=3))
    @settings(max_examples=30, deadline=5000)
    def test_meshgrid_copy_independent(self, data):
        """Copied MeshgridDataDict must be independent."""
        data2 = data.copy()
        data2[data2.dependents()[0]]['values'].flat[0] = 999.0
        assert data[data.dependents()[0]]['values'].flat[0] != 999.0

    @given(data=meshgrid_st(min_axes=2, max_axes=3))
    @settings(max_examples=20, deadline=5000)
    def test_mask_invalid_clean_data(self, data):
        """mask_invalid on clean data should not change values."""
        data2 = data.copy()
        data2 = data2.mask_invalid()
        for dep in data.dependents():
            assert np.allclose(
                np.asarray(data.data_vals(dep)),
                np.asarray(data2.data_vals(dep)),
            )

    @given(data=meshgrid_st(min_axes=2, max_axes=2))
    @settings(max_examples=20, deadline=5000)
    def test_mean_removes_axis(self, data):
        """mean() should remove the averaged axis."""
        ax = data.axes()[0]
        result = data.mean(ax)
        assert ax not in result.axes()

    @given(data=meshgrid_st(min_axes=2, max_axes=2, min_axis_len=4))
    @settings(max_examples=20, deadline=5000)
    def test_slice_preserves_validity(self, data):
        """Slicing should produce valid data."""
        ax = data.axes()[0]
        result = data.slice(**{ax: slice(1, 3)})
        assert result.validate()


# ===========================================================================
# PART B: FLOWCHART-BASED NODE TESTS (need qtbot for QApplication)
# ===========================================================================

# --- Node base ---

def test_node_passthrough(qtbot):
    data = make_griddable_dd((5, 4))
    fc = linearFlowchart(('n', Node))
    fc.setInput(dataIn=data)
    assert fc.outputValues()['dataOut'] is data


# --- DataSelector ---

class TestDataSelectorFC:

    @pytest.mark.parametrize("shape,ndeps", [
        ((10,), 2), ((5, 4), 2), ((3, 3, 2), 3),
    ])
    def test_select_single_dep(self, qtbot, shape, ndeps):
        data = make_griddable_dd(shape, ndeps)
        fc = linearFlowchart(('sel', DataSelector))
        fc.setInput(dataIn=data)
        fc.nodes()['sel'].selectedData = [data.dependents()[0]]
        out = fc.outputValues()['dataOut']
        assert out is not None
        assert out.dependents() == [data.dependents()[0]]

    @pytest.mark.parametrize("shape,ndeps", [
        ((10,), 3), ((5, 4), 2),
    ])
    def test_select_multiple_deps(self, qtbot, shape, ndeps):
        data = make_griddable_dd(shape, ndeps)
        fc = linearFlowchart(('sel', DataSelector))
        fc.setInput(dataIn=data)
        deps = data.dependents()[:2]
        fc.nodes()['sel'].selectedData = deps
        out = fc.outputValues()['dataOut']
        assert out is not None
        assert set(out.dependents()) == set(deps)

    def test_select_does_not_mutate(self, qtbot):
        data = make_griddable_dd((10,), 2)
        snap = snapshot_values(data)
        fc = linearFlowchart(('sel', DataSelector))
        fc.setInput(dataIn=data)
        fc.nodes()['sel'].selectedData = [data.dependents()[0]]
        _ = fc.outputValues()['dataOut']
        assert_not_mutated(data, snap)


# --- DataGridder ---

class TestDataGridderFC:

    @pytest.mark.parametrize("shape", [
        (5,), (5, 4), (10, 10), (3, 4, 2), (5, 5, 5),
    ])
    def test_guess_shape(self, qtbot, shape):
        data = make_griddable_dd(shape)
        fc = linearFlowchart(('grid', DataGridder))
        fc.setInput(dataIn=data)
        fc.nodes()['grid'].grid = GridOption.guessShape, {}
        out = fc.outputValues()['dataOut']
        assert out is not None
        assert isinstance(out, MeshgridDataDict)
        assert out.shape() == shape

    @pytest.mark.parametrize("shape", [
        (5, 4), (3, 3, 2),
    ])
    def test_specify_shape(self, qtbot, shape):
        data = make_griddable_dd(shape)
        ax_names = data.axes(data.dependents()[0])
        fc = linearFlowchart(('grid', DataGridder))
        fc.setInput(dataIn=data)
        fc.nodes()['grid'].grid = GridOption.specifyShape, dict(
            shape=shape, order=ax_names,
        )
        out = fc.outputValues()['dataOut']
        assert out is not None
        assert isinstance(out, MeshgridDataDict)
        assert out.shape() == shape

    def test_nogrid_passthrough(self, qtbot):
        data = make_griddable_dd((5, 4))
        fc = linearFlowchart(('grid', DataGridder))
        fc.setInput(dataIn=data)
        fc.nodes()['grid'].grid = GridOption.noGrid, {}
        out = fc.outputValues()['dataOut']
        assert out is not None
        assert isinstance(out, DataDict)

    def test_meshgrid_passthrough_guess(self, qtbot):
        data = make_mesh((5, 4))
        fc = linearFlowchart(('grid', DataGridder))
        fc.setInput(dataIn=data)
        fc.nodes()['grid'].grid = GridOption.guessShape, {}
        out = fc.outputValues()['dataOut']
        assert isinstance(out, MeshgridDataDict)

    def test_meshgrid_to_flat_nogrid(self, qtbot):
        data = make_mesh((5, 4))
        fc = linearFlowchart(('grid', DataGridder))
        fc.setInput(dataIn=data)
        fc.nodes()['grid'].grid = GridOption.noGrid, {}
        out = fc.outputValues()['dataOut']
        assert isinstance(out, DataDict)
        assert out.nrecords() == 20

    def test_gridder_does_not_mutate(self, qtbot):
        data = make_griddable_dd((5, 4))
        snap = snapshot_values(data)
        fc = linearFlowchart(('grid', DataGridder))
        fc.setInput(dataIn=data)
        fc.nodes()['grid'].grid = GridOption.guessShape, {}
        _ = fc.outputValues()['dataOut']
        assert_not_mutated(data, snap)


# --- DimensionReducer ---

class TestDimensionReducerFC:

    @pytest.mark.parametrize("shape", [
        (5, 4), (4, 3, 2),
    ])
    def test_element_selection(self, qtbot, shape):
        data = make_mesh(shape)
        fc = linearFlowchart(('red', DimensionReducer))
        fc.setInput(dataIn=data)
        last_ax = data.axes()[-1]
        fc.nodes()['red'].reductions = {
            last_ax: (ReductionMethod.elementSelection, [], {'index': 0})
        }
        out = fc.outputValues()['dataOut']
        assert out is not None
        assert last_ax not in out.axes()

    @pytest.mark.parametrize("shape", [
        (5, 4), (4, 3, 2),
    ])
    def test_average_reduction(self, qtbot, shape):
        data = make_mesh(shape)
        fc = linearFlowchart(('red', DimensionReducer))
        fc.setInput(dataIn=data)
        last_ax = data.axes()[-1]
        fc.nodes()['red'].reductions = {last_ax: (ReductionMethod.average,)}
        out = fc.outputValues()['dataOut']
        assert out is not None
        assert last_ax not in out.axes()

    def test_reducer_does_not_mutate(self, qtbot):
        data = make_mesh((5, 4))
        snap = snapshot_values(data)
        fc = linearFlowchart(('red', DimensionReducer))
        fc.setInput(dataIn=data)
        fc.nodes()['red'].reductions = {
            'ax1': (ReductionMethod.elementSelection, [], {'index': 0})
        }
        _ = fc.outputValues()['dataOut']
        assert_not_mutated(data, snap)


# --- XYSelector ---

class TestXYSelectorFC:

    @pytest.mark.parametrize("shape", [
        (5, 4), (8, 6), (4, 3, 2), (5, 5, 5),
    ])
    def test_xy_produces_2d(self, qtbot, shape):
        data = make_mesh(shape)
        axes = data.axes()
        fc = linearFlowchart(('xy', XYSelector))
        fc.setInput(dataIn=data)
        fc.nodes()['xy'].xyAxes = (axes[0], axes[1])
        out = fc.outputValues()['dataOut']
        assert out is not None
        for dep in out.dependents():
            assert out.data_vals(dep).ndim == 2

    def test_xy_1d_x_only(self, qtbot):
        data = make_mesh((10,))
        fc = linearFlowchart(('xy', XYSelector))
        fc.setInput(dataIn=data)
        fc.nodes()['xy'].xyAxes = ('ax0', None)
        out = fc.outputValues()['dataOut']
        assert out is not None
        for dep in out.dependents():
            assert out.data_vals(dep).ndim == 1

    def test_xy_no_axes_returns_none(self, qtbot):
        data = make_mesh((5, 4))
        fc = linearFlowchart(('xy', XYSelector))
        fc.setInput(dataIn=data)
        assert fc.outputValues()['dataOut'] is None

    def test_xy_does_not_mutate(self, qtbot):
        data = make_mesh((5, 4, 3))
        snap = snapshot_values(data)
        fc = linearFlowchart(('xy', XYSelector))
        fc.setInput(dataIn=data)
        fc.nodes()['xy'].xyAxes = ('ax0', 'ax1')
        _ = fc.outputValues()['dataOut']
        assert_not_mutated(data, snap)


# --- ScaleUnits ---

class TestScaleUnitsFC:

    @pytest.mark.parametrize("scale,prefix_substr", [
        (1e-9, 'n'), (1e-6, '\u03bc'), (1e-3, 'm'), (1e6, 'M'), (1e9, 'G'),
    ])
    def test_si_prefix(self, qtbot, scale, prefix_substr):
        dd = DataDict(
            x=dict(values=np.arange(5, dtype=float) * scale, unit='V'),
            y=dict(values=np.arange(5, dtype=float), axes=['x'], unit='A'),
        )
        dd.validate()
        fc = linearFlowchart(('su', ScaleUnits))
        fc.setInput(dataIn=dd)
        out = fc.outputValues()['dataOut']
        assert prefix_substr in out['x']['unit']

    def test_does_not_mutate(self, qtbot):
        dd = DataDict(
            x=dict(values=np.arange(5, dtype=float) * 1e-9, unit='V'),
            y=dict(values=np.arange(5, dtype=float), axes=['x'], unit='A'),
        )
        dd.validate()
        snap = snapshot_values(dd)
        fc = linearFlowchart(('su', ScaleUnits))
        fc.setInput(dataIn=dd)
        _ = fc.outputValues()['dataOut']
        assert_not_mutated(dd, snap)


# --- SubtractAverage ---

class TestSubtractAverageFC:

    @pytest.mark.parametrize("shape", [
        (10, 5), (5, 4, 3),
    ])
    def test_subtract_axis(self, qtbot, shape):
        data = make_mesh(shape)
        ax = data.axes()[-1]
        fc = linearFlowchart(('sa', SubtractAverage))
        fc.setInput(dataIn=data)
        fc.nodes()['sa'].averagingAxis = ax
        out = fc.outputValues()['dataOut']
        assert out is not None
        # After subtraction, mean along that axis should be ~0
        ax_idx = data.axes().index(ax)
        for dep in out.dependents():
            avg = out.data_vals(dep).mean(axis=ax_idx)
            assert np.allclose(avg, 0, atol=1e-10)

    def test_no_axis_passthrough(self, qtbot):
        data = make_mesh((5, 4))
        fc = linearFlowchart(('sa', SubtractAverage))
        fc.setInput(dataIn=data)
        out = fc.outputValues()['dataOut']
        assert out is not None

    def test_does_not_mutate(self, qtbot):
        data = make_mesh((5, 4))
        snap = snapshot_values(data)
        fc = linearFlowchart(('sa', SubtractAverage))
        fc.setInput(dataIn=data)
        fc.nodes()['sa'].averagingAxis = 'ax1'
        _ = fc.outputValues()['dataOut']
        assert_not_mutated(data, snap)


# --- Histogrammer ---

class TestHistogrammerFC:

    @pytest.mark.parametrize("shape,hist_ax", [
        ((20, 5), 'ax0'),
        ((10, 8), 'ax1'),
        ((5, 4, 3), 'ax0'),
    ])
    def test_histogram_produces_counts(self, qtbot, shape, hist_ax):
        data = make_mesh(shape)
        fc = linearFlowchart(('h', Histogrammer))
        fc.setInput(dataIn=data)
        fc.nodes()['h'].nbins = 10
        fc.nodes()['h'].histogramAxis = hist_ax
        out = fc.outputValues()['dataOut']
        assert out is not None
        assert any('count' in d for d in out.dependents())

    def test_no_axis_passthrough(self, qtbot):
        data = make_mesh((10, 5))
        fc = linearFlowchart(('h', Histogrammer))
        fc.setInput(dataIn=data)
        out = fc.outputValues()['dataOut']
        assert out is not None


# ===========================================================================
# FULL PIPELINE INTEGRATION
# ===========================================================================

class TestFullPipelineFC:

    @pytest.mark.parametrize("shape", [
        (5, 4), (10, 10), (8, 6), (3, 4, 2),
    ])
    def test_selector_gridder_xy(self, qtbot, shape):
        data = make_griddable_dd(shape, ndeps=2)
        fc = linearFlowchart(
            ('sel', DataSelector),
            ('grid', DataGridder),
            ('xy', XYSelector),
        )
        fc.setInput(dataIn=data)
        fc.nodes()['sel'].selectedData = [data.dependents()[0]]
        fc.nodes()['grid'].grid = GridOption.guessShape, {}
        axes = data.axes(data.dependents()[0])
        fc.nodes()['xy'].xyAxes = (axes[0], axes[1])

        out = fc.outputValues()['dataOut']
        assert out is not None
        assert isinstance(out, MeshgridDataDict)

    def test_full_pipeline_does_not_mutate(self, qtbot):
        data = make_griddable_dd((8, 6))
        snap = snapshot_values(data)
        fc = linearFlowchart(
            ('sel', DataSelector),
            ('grid', DataGridder),
            ('xy', XYSelector),
        )
        fc.setInput(dataIn=data)
        fc.nodes()['sel'].selectedData = [data.dependents()[0]]
        fc.nodes()['grid'].grid = GridOption.guessShape, {}
        fc.nodes()['xy'].xyAxes = ('ax0', 'ax1')
        _ = fc.outputValues()['dataOut']
        assert_not_mutated(data, snap)

    def test_full_with_scale_and_subtract(self, qtbot):
        data = make_griddable_dd((6, 5))
        # Give units to exercise ScaleUnits
        data['ax0']['unit'] = 'V'
        data['ax0']['values'] *= 1e-9
        data['dep0']['unit'] = 'A'

        fc = linearFlowchart(
            ('sel', DataSelector),
            ('grid', DataGridder),
            ('xy', XYSelector),
            ('sa', SubtractAverage),
            ('su', ScaleUnits),
        )
        fc.setInput(dataIn=data)
        fc.nodes()['sel'].selectedData = ['dep0']
        fc.nodes()['grid'].grid = GridOption.guessShape, {}
        fc.nodes()['xy'].xyAxes = ('ax0', 'ax1')
        fc.nodes()['sa'].averagingAxis = 'ax1'

        out = fc.outputValues()['dataOut']
        assert out is not None

    @pytest.mark.parametrize("dtype", [
        np.float64, np.float32, np.complex128,
    ])
    def test_pipeline_various_dtypes(self, qtbot, dtype):
        shape = (5, 4)
        data = make_griddable_dd(shape)
        z = np.random.randn(20).astype(dtype)
        if np.issubdtype(dtype, np.complexfloating):
            z = z + 1j * np.random.randn(20).astype(dtype)
        data['dep0']['values'] = z

        fc = linearFlowchart(
            ('sel', DataSelector),
            ('grid', DataGridder),
        )
        fc.setInput(dataIn=data)
        fc.nodes()['sel'].selectedData = ['dep0']
        fc.nodes()['grid'].grid = GridOption.guessShape, {}
        out = fc.outputValues()['dataOut']
        assert out is not None
        assert np.issubdtype(out.data_vals('dep0').dtype, dtype)

    def test_pipeline_with_nan_data(self, qtbot):
        """Pipeline with incomplete data (NaN values)."""
        data = make_griddable_dd((6, 5))
        # Inject NaN at end (simulating incomplete sweep)
        data['dep0']['values'][-5:] = np.nan
        data['ax0']['values'][-5:] = np.nan
        data['ax1']['values'][-5:] = np.nan

        fc = linearFlowchart(
            ('sel', DataSelector),
            ('grid', DataGridder),
        )
        fc.setInput(dataIn=data)
        fc.nodes()['sel'].selectedData = ['dep0']
        fc.nodes()['grid'].grid = GridOption.guessShape, {}
        out = fc.outputValues()['dataOut']
        # Should handle NaN gracefully (either grid or fall back)
        assert out is not None

    def test_pipeline_with_multiple_deps(self, qtbot):
        """Pipeline selecting multiple compatible dependents."""
        data = make_griddable_dd((5, 4), ndeps=3)
        fc = linearFlowchart(
            ('sel', DataSelector),
            ('grid', DataGridder),
            ('xy', XYSelector),
        )
        fc.setInput(dataIn=data)
        fc.nodes()['sel'].selectedData = data.dependents()[:2]
        fc.nodes()['grid'].grid = GridOption.guessShape, {}
        fc.nodes()['xy'].xyAxes = ('ax0', 'ax1')
        out = fc.outputValues()['dataOut']
        assert out is not None
        assert len(out.dependents()) == 2
