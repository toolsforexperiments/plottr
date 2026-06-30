"""
test_gridder_comprehensive.py

Comprehensive tests for the DataGridder node and underlying gridding functions.
Covers all GridOption paths, various data shapes, edge cases, and input types.
"""
import numpy as np
import pytest

from plottr.data.datadict import (
    DataDict, MeshgridDataDict, DataDictBase,
    datadict_to_meshgrid, meshgrid_to_datadict,
    guess_shape_from_datadict, GriddingError,
)
from plottr.node.tools import linearFlowchart
from plottr.node.grid import DataGridder, GridOption
from plottr.utils.num import (
    guess_grid_from_sweep_direction, find_direction_period,
    _find_switches, array1d_to_meshgrid,
)

DataGridder.useUi = False
DataGridder.uiClass = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_griddable(shape, ndeps=1, noise=0.0):
    """Create a griddable DataDict from a meshgrid shape."""
    naxes = len(shape)
    ax_names = [f'ax{i}' for i in range(naxes)]
    axes_1d = [np.linspace(0, 1, s) for s in shape]
    grids = np.meshgrid(*axes_1d, indexing='ij')
    dd = DataDict()
    for i, ax in enumerate(ax_names):
        vals = grids[i].ravel()
        if noise > 0:
            vals = vals + np.random.randn(vals.size) * noise
        dd[ax] = dict(values=vals, axes=[], unit='V', label=ax)
    for j in range(ndeps):
        dd[f'dep{j}'] = dict(values=np.random.randn(int(np.prod(shape))),
                             axes=ax_names[:], unit='A', label=f'dep{j}')
    dd.validate()
    return dd


def make_mesh(shape, ndeps=1):
    naxes = len(shape)
    ax_names = [f'ax{i}' for i in range(naxes)]
    axes_1d = [np.linspace(0, 1, s) for s in shape]
    grids = np.meshgrid(*axes_1d, indexing='ij')
    dd = MeshgridDataDict()
    for i, ax in enumerate(ax_names):
        dd[ax] = dict(values=grids[i], axes=[], unit='V', label=ax)
    for j in range(ndeps):
        dd[f'dep{j}'] = dict(values=np.random.randn(*shape),
                             axes=ax_names[:], unit='A', label=f'dep{j}')
    dd.validate()
    return dd


# ===========================================================================
# _find_switches
# ===========================================================================

class TestFindSwitches:
    def test_monotonic_no_switches(self):
        arr = np.linspace(0, 10, 100)
        assert len(_find_switches(arr)) == 0

    def test_single_sawtooth(self):
        arr = np.concatenate([np.arange(10), np.arange(10)])
        switches = _find_switches(arr)
        assert len(switches) >= 1

    def test_flat_array(self):
        arr = np.ones(50)
        assert len(_find_switches(arr)) == 0

    def test_with_nan(self):
        arr = np.linspace(0, 10, 100)
        arr[50] = np.nan
        switches = _find_switches(arr)
        assert isinstance(switches, np.ndarray)

    def test_short_array(self):
        arr = np.array([1.0, 2.0])
        switches = _find_switches(arr)
        assert isinstance(switches, np.ndarray)

    def test_single_element(self):
        arr = np.array([1.0])
        switches = _find_switches(arr)
        assert len(switches) == 0


# ===========================================================================
# find_direction_period
# ===========================================================================

class TestFindDirectionPeriod:
    def test_repeating_pattern(self):
        # 0,1,2,3,4, 0,1,2,3,4, 0,1,2,3,4
        arr = np.tile(np.arange(5, dtype=float), 3)
        period = find_direction_period(arr)
        assert period == 5

    def test_no_repetition(self):
        arr = np.linspace(0, 10, 100)
        period = find_direction_period(arr)
        assert period == np.inf

    def test_incomplete_last_period(self):
        arr = np.concatenate([np.tile(np.arange(5, dtype=float), 3),
                              np.arange(3, dtype=float)])
        period = find_direction_period(arr, ignore_last=True)
        assert period == 5

    def test_single_value(self):
        arr = np.array([1.0])
        period = find_direction_period(arr)
        assert period is not None  # should handle gracefully


# ===========================================================================
# guess_grid_from_sweep_direction
# ===========================================================================

class TestGuessGrid:
    @pytest.mark.parametrize("shape", [
        (10,), (5, 4), (3, 4, 2), (10, 10), (20, 15),
    ])
    def test_correct_shape_guessed(self, shape):
        naxes = len(shape)
        ax_names = [f'ax{i}' for i in range(naxes)]
        axes_1d = [np.linspace(0, 1, s) for s in shape]
        grids = np.meshgrid(*axes_1d, indexing='ij')
        kwargs = {ax_names[i]: grids[i].ravel() for i in range(naxes)}
        result = guess_grid_from_sweep_direction(**kwargs)
        assert result is not None
        _, guessed_shape = result
        assert guessed_shape == shape

    def test_noisy_axes(self):
        shape = (10, 8)
        grids = np.meshgrid(np.linspace(0, 1, 10), np.linspace(0, 1, 8), indexing='ij')
        x = grids[0].ravel() + np.random.randn(80) * 1e-6
        y = grids[1].ravel()
        result = guess_grid_from_sweep_direction(x=x, y=y)
        assert result is not None
        _, guessed = result
        assert guessed == shape

    def test_single_axis(self):
        x = np.linspace(0, 1, 50)
        result = guess_grid_from_sweep_direction(x=x)
        assert result is not None
        _, shape = result
        assert shape == (50,)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            guess_grid_from_sweep_direction()

    def test_mismatched_sizes_raises(self):
        with pytest.raises(ValueError):
            guess_grid_from_sweep_direction(x=np.arange(10, dtype=float),
                                            y=np.arange(5, dtype=float))


# ===========================================================================
# array1d_to_meshgrid
# ===========================================================================

class TestArray1dToMeshgrid:
    def test_exact_reshape(self):
        arr = np.arange(12, dtype=float)
        result = array1d_to_meshgrid(arr, (3, 4))
        assert result.shape == (3, 4)

    def test_padding_with_nan(self):
        arr = np.arange(10, dtype=float)
        result = array1d_to_meshgrid(arr, (4, 4))  # needs 16, has 10
        assert result.shape == (4, 4)
        assert np.isnan(result.ravel()[-1])

    def test_truncation(self):
        arr = np.arange(20, dtype=float)
        result = array1d_to_meshgrid(arr, (3, 4))  # needs 12, has 20
        assert result.shape == (3, 4)

    def test_copy_true_independent(self):
        arr = np.arange(12, dtype=float)
        result = array1d_to_meshgrid(arr, (3, 4), copy=True)
        result[0, 0] = 999
        assert arr[0] != 999

    def test_copy_false_may_share(self):
        arr = np.arange(12, dtype=float)
        result = array1d_to_meshgrid(arr, (3, 4), copy=False)
        assert result.shape == (3, 4)

    def test_object_array_padding(self):
        arr = np.array([1, 2, 3], dtype=object)
        result = array1d_to_meshgrid(arr, (2, 3))  # needs 6, has 3
        assert result.shape == (2, 3)


# ===========================================================================
# guess_shape_from_datadict
# ===========================================================================

class TestGuessShapeFromDatadict:
    @pytest.mark.parametrize("shape", [
        (10, 5), (3, 4, 2), (20, 15),
    ])
    def test_guesses_correct_shape(self, shape):
        dd = make_griddable(shape)
        shapes = guess_shape_from_datadict(dd)
        for dep in dd.dependents():
            assert shapes[dep] is not None
            _, guessed = shapes[dep]
            assert guessed == shape

    def test_with_multiple_deps(self):
        dd = make_griddable((10, 8), ndeps=3)
        shapes = guess_shape_from_datadict(dd)
        assert len(shapes) == 3
        for dep in dd.dependents():
            assert shapes[dep] is not None


# ===========================================================================
# datadict_to_meshgrid
# ===========================================================================

class TestDatadictToMeshgrid:
    @pytest.mark.parametrize("shape", [
        (5,), (5, 4), (10, 10), (3, 4, 2),
    ])
    def test_produces_correct_shape(self, shape):
        dd = make_griddable(shape)
        mesh = datadict_to_meshgrid(dd)
        assert isinstance(mesh, MeshgridDataDict)
        assert mesh.shape() == shape

    def test_with_target_shape(self):
        dd = make_griddable((5, 4))
        mesh = datadict_to_meshgrid(dd, target_shape=(5, 4))
        assert mesh.shape() == (5, 4)

    def test_with_inner_axis_order(self):
        # Create data where inner order doesn't match axes order
        x = np.arange(5, dtype=float)
        y = np.linspace(0, 1, 4)
        xx, yy = np.meshgrid(x, y, indexing='xy')  # xy order
        dd = DataDict(
            x=dict(values=xx.ravel()), y=dict(values=yy.ravel()),
            z=dict(values=(xx * yy).ravel(), axes=['x', 'y']),
        )
        dd.validate()
        mesh = datadict_to_meshgrid(dd, target_shape=(4, 5),
                                     inner_axis_order=['y', 'x'])
        assert isinstance(mesh, MeshgridDataDict)

    def test_use_existing_shape(self):
        """use_existing_shape works when data already has the right shape."""
        # Need data with nested array shapes matching target
        x = np.arange(5, dtype=float)
        y = np.linspace(0, 1, 4)
        xx, yy = np.meshgrid(x, y, indexing='ij')
        dd = DataDict(
            x=dict(values=xx),  # already (5,4) shaped
            y=dict(values=yy),
            z=dict(values=xx * yy, axes=['x', 'y']),
        )
        dd.validate()
        mesh = datadict_to_meshgrid(dd, use_existing_shape=True)
        assert isinstance(mesh, MeshgridDataDict)
        assert mesh.shape() == (5, 4)

    def test_copy_false(self):
        dd = make_griddable((5, 4))
        mesh = datadict_to_meshgrid(dd, copy=False)
        assert isinstance(mesh, MeshgridDataDict)

    def test_preserves_meta(self):
        dd = make_griddable((5, 4))
        dd.add_meta('info', 'test')
        mesh = datadict_to_meshgrid(dd)
        assert mesh.meta_val('info') == 'test'

    def test_incompatible_axes_raises(self):
        dd = DataDict(
            x=dict(values=np.arange(10, dtype=float)),
            y=dict(values=np.arange(10, dtype=float), axes=['x']),
            z=dict(values=np.arange(10, dtype=float)),
            w=dict(values=np.arange(10, dtype=float), axes=['z']),
        )
        dd.validate()
        with pytest.raises(GriddingError):
            datadict_to_meshgrid(dd)

    def test_empty_datadict(self):
        dd = DataDict()
        dd.validate()
        mesh = datadict_to_meshgrid(dd)
        assert isinstance(mesh, MeshgridDataDict)

    def test_incomplete_data_pads_with_nan(self):
        # 5x4 grid but only 18 of 20 points
        shape = (5, 4)
        grids = np.meshgrid(np.linspace(0, 1, 5), np.linspace(0, 1, 4), indexing='ij')
        dd = DataDict(
            x=dict(values=grids[0].ravel()[:18]),
            y=dict(values=grids[1].ravel()[:18]),
            z=dict(values=np.random.randn(18), axes=['x', 'y']),
        )
        dd.validate()
        mesh = datadict_to_meshgrid(dd, target_shape=shape)
        assert mesh.shape() == shape
        # Last 2 values should be NaN
        assert np.isnan(mesh.data_vals('z').ravel()[-1])


# ===========================================================================
# meshgrid_to_datadict
# ===========================================================================

class TestMeshgridToDatadict:
    @pytest.mark.parametrize("shape", [
        (5, 4), (10, 10), (3, 4, 2),
    ])
    def test_produces_flat(self, shape):
        mesh = make_mesh(shape)
        dd = meshgrid_to_datadict(mesh)
        assert isinstance(dd, DataDict)
        assert dd.nrecords() == int(np.prod(shape))


# ===========================================================================
# DataGridder node — all GridOption paths
# ===========================================================================

class TestDataGridderNode:

    # --- DataDict input ---

    @pytest.mark.parametrize("shape", [
        (10,), (5, 4), (3, 4, 2),
    ])
    def test_noGrid_tabular_passthrough(self, qtbot, shape):
        dd = make_griddable(shape)
        fc = linearFlowchart(('g', DataGridder))
        fc.setInput(dataIn=dd)
        fc.nodes()['g'].grid = GridOption.noGrid, {}
        out = fc.outputValues()['dataOut']
        assert isinstance(out, DataDict)

    @pytest.mark.parametrize("shape", [
        (10,), (5, 4), (10, 10), (50, 3), (3, 4, 2),
    ])
    def test_guessShape_tabular(self, qtbot, shape):
        dd = make_griddable(shape)
        fc = linearFlowchart(('g', DataGridder))
        fc.setInput(dataIn=dd)
        fc.nodes()['g'].grid = GridOption.guessShape, {}
        out = fc.outputValues()['dataOut']
        assert isinstance(out, MeshgridDataDict)
        assert out.shape() == shape

    def test_specifyShape_tabular(self, qtbot):
        dd = make_griddable((5, 4))
        fc = linearFlowchart(('g', DataGridder))
        fc.setInput(dataIn=dd)
        fc.nodes()['g'].grid = GridOption.specifyShape, dict(
            shape=(5, 4), order=['ax0', 'ax1'])
        out = fc.outputValues()['dataOut']
        assert isinstance(out, MeshgridDataDict)
        assert out.shape() == (5, 4)

    def test_metadataShape_tabular(self, qtbot):
        dd = make_griddable((5, 4))
        fc = linearFlowchart(('g', DataGridder))
        fc.setInput(dataIn=dd)
        fc.nodes()['g'].grid = GridOption.metadataShape, {}
        out = fc.outputValues()['dataOut']
        # metadataShape uses existing shape from data arrays
        assert out is not None

    # --- MeshgridDataDict input ---

    def test_noGrid_meshgrid_flattens(self, qtbot):
        mesh = make_mesh((5, 4))
        fc = linearFlowchart(('g', DataGridder))
        fc.setInput(dataIn=mesh)
        fc.nodes()['g'].grid = GridOption.noGrid, {}
        out = fc.outputValues()['dataOut']
        assert isinstance(out, DataDict)
        assert out.nrecords() == 20

    def test_guessShape_meshgrid_passthrough(self, qtbot):
        mesh = make_mesh((5, 4))
        fc = linearFlowchart(('g', DataGridder))
        fc.setInput(dataIn=mesh)
        fc.nodes()['g'].grid = GridOption.guessShape, {}
        out = fc.outputValues()['dataOut']
        assert isinstance(out, MeshgridDataDict)

    def test_specifyShape_meshgrid_warns(self, qtbot):
        mesh = make_mesh((5, 4))
        fc = linearFlowchart(('g', DataGridder))
        fc.setInput(dataIn=mesh)
        fc.nodes()['g'].grid = GridOption.specifyShape, dict(shape=(5, 4))
        out = fc.outputValues()['dataOut']
        # Should pass through with warning
        assert isinstance(out, MeshgridDataDict)

    def test_metadataShape_meshgrid_passthrough(self, qtbot):
        mesh = make_mesh((5, 4))
        fc = linearFlowchart(('g', DataGridder))
        fc.setInput(dataIn=mesh)
        fc.nodes()['g'].grid = GridOption.metadataShape, {}
        out = fc.outputValues()['dataOut']
        assert isinstance(out, MeshgridDataDict)

    # --- Edge cases ---

    def test_gridding_error_falls_back(self, qtbot):
        """Data that can't be gridded should fall back to noGrid."""
        dd = DataDict(
            x=dict(values=np.array([1.0, 1.0, 2.0, 2.0, 3.0])),
            y=dict(values=np.array([1.0, 2.0, 1.0, 2.0, 1.0])),
            z=dict(values=np.random.randn(5), axes=['x', 'y']),
        )
        dd.validate()
        fc = linearFlowchart(('g', DataGridder))
        fc.setInput(dataIn=dd)
        fc.nodes()['g'].grid = GridOption.guessShape, {}
        out = fc.outputValues()['dataOut']
        # Should not crash; may fall back to expanded DataDict
        assert out is not None

    def test_does_not_mutate_input(self, qtbot):
        dd = make_griddable((10, 8))
        ref_vals = {k: v['values'].copy() for k, v in dd.data_items()}
        fc = linearFlowchart(('g', DataGridder))
        fc.setInput(dataIn=dd)
        fc.nodes()['g'].grid = GridOption.guessShape, {}
        _ = fc.outputValues()['dataOut']
        for k, orig in ref_vals.items():
            assert np.array_equal(dd.data_vals(k), orig), f"{k} was mutated"

    def test_multiple_deps(self, qtbot):
        dd = make_griddable((5, 4), ndeps=3)
        fc = linearFlowchart(('g', DataGridder))
        fc.setInput(dataIn=dd)
        fc.nodes()['g'].grid = GridOption.guessShape, {}
        out = fc.outputValues()['dataOut']
        assert len(out.dependents()) == 3

    def test_with_noisy_axes(self, qtbot):
        dd = make_griddable((10, 8), noise=1e-6)
        fc = linearFlowchart(('g', DataGridder))
        fc.setInput(dataIn=dd)
        fc.nodes()['g'].grid = GridOption.guessShape, {}
        out = fc.outputValues()['dataOut']
        assert out is not None
        assert isinstance(out, MeshgridDataDict)
