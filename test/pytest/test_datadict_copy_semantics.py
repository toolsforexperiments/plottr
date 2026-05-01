"""
test_datadict_copy_semantics.py

Comprehensive tests for DataDict copy semantics, data integrity through pipeline
operations, and edge cases. These tests serve as a safety net before making
performance optimizations to the DataDict implementation.
"""
import copy as cp

import numpy as np
import pytest

from plottr.data.datadict import (
    DataDict,
    DataDictBase,
    MeshgridDataDict,
    datadict_to_meshgrid,
    meshgrid_to_datadict,
    datasets_are_equal,
)
from plottr.utils import num


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_datadict(npts: int = 100) -> DataDict:
    """Simple 1D DataDict: x -> y, z."""
    return DataDict(
        x=dict(values=np.arange(npts, dtype=float), unit='V', label='x'),
        y=dict(values=np.random.randn(npts), axes=['x'], unit='A', label='y'),
        z=dict(values=np.random.randn(npts), axes=['x'], unit='A', label='z'),
    )


def make_meshgrid(shape: tuple = (10, 8), ndeps: int = 2) -> MeshgridDataDict:
    """Gridded data with given shape."""
    naxes = len(shape)
    dd = MeshgridDataDict()
    ax_names = [f'ax{i}' for i in range(naxes)]
    grids = np.meshgrid(*[np.linspace(0, 1, s) for s in shape], indexing='ij')
    for i, ax in enumerate(ax_names):
        dd[ax] = dict(values=grids[i], axes=[], unit='V', label=ax)
    for i in range(ndeps):
        dd[f'dep{i}'] = dict(
            values=np.random.randn(*shape),
            axes=ax_names.copy(),
            unit='A',
            label=f'dep{i}',
        )
    dd.validate()
    return dd


# ===========================================================================
# 1. COPY ISOLATION TESTS
# ===========================================================================

class TestCopyIsolation:
    """Verify that copy() produces fully independent data."""

    def test_copy_values_independent(self):
        """Modifying copied values must not affect the original."""
        dd = make_datadict()
        dd2 = dd.copy()
        dd2['y']['values'][0] = 999.0
        assert dd['y']['values'][0] != 999.0

    def test_copy_axes_independent(self):
        """Modifying copied axes list must not affect the original."""
        dd = make_datadict()
        dd2 = dd.copy()
        dd2['y']['axes'].append('extra')
        assert 'extra' not in dd['y']['axes']

    def test_copy_unit_independent(self):
        """Changing unit on copy must not affect original."""
        dd = make_datadict()
        dd2 = dd.copy()
        dd2['y']['unit'] = 'mA'
        assert dd['y']['unit'] == 'A'

    def test_copy_meta_independent(self):
        """Modifying mutable metadata on copy must not affect original.

        This was previously broken (copy() via structure() did not deepcopy
        global mutable metadata). Fixed by the Phase 1a copy() rewrite.
        """
        dd = make_datadict()
        dd.add_meta('info', {'key': 'value'})
        dd2 = dd.copy()
        dd2.meta_val('info')['key'] = 'changed'
        assert dd.meta_val('info')['key'] == 'value'

    def test_copy_field_meta_independent(self):
        """Per-field mutable metadata should be independent after copy.

        Note: this works because structure() calls cp.deepcopy on each field dict,
        which catches per-field meta. However, global meta is NOT deepcopied
        (see test_copy_meta_independent above).
        """
        dd = make_datadict()
        dd.add_meta('cal', [1, 2, 3], data='y')
        dd2 = dd.copy()
        dd2.meta_val('cal', 'y').append(4)
        assert dd.meta_val('cal', 'y') == [1, 2, 3]

    def test_copy_preserves_type_datadict(self):
        dd = make_datadict()
        dd2 = dd.copy()
        assert type(dd2) is DataDict

    def test_copy_preserves_type_meshgrid(self):
        dd = make_meshgrid()
        dd2 = dd.copy()
        assert type(dd2) is MeshgridDataDict

    def test_copy_preserves_equality(self):
        dd = make_datadict()
        dd.add_meta('info', 'test')
        dd2 = dd.copy()
        assert dd == dd2

    def test_meshgrid_copy_values_independent(self):
        dd = make_meshgrid((10, 8))
        dd2 = dd.copy()
        dd2['dep0']['values'][0, 0] = 999.0
        assert dd['dep0']['values'][0, 0] != 999.0

    def test_meshgrid_copy_axes_independent(self):
        dd = make_meshgrid((10, 8))
        dd2 = dd.copy()
        original_axes = dd['dep0']['axes'].copy()
        dd2['dep0']['axes'].pop()
        assert dd['dep0']['axes'] == original_axes


# ===========================================================================
# 2. EXTRACT ISOLATION TESTS
# ===========================================================================

class TestExtractIsolation:
    """Verify that extract() produces independent data when copy=True."""

    def test_extract_copy_true_values_independent(self):
        dd = make_datadict()
        ex = dd.extract(['y'], copy=True)
        ex['y']['values'][0] = 999.0
        assert dd['y']['values'][0] != 999.0

    def test_extract_copy_true_axes_independent(self):
        dd = make_datadict()
        ex = dd.extract(['y'], copy=True)
        ex['y']['axes'].append('extra')
        assert 'extra' not in dd['y']['axes']

    def test_extract_copy_false_shares_values(self):
        dd = make_datadict()
        ex = dd.extract(['y'], copy=False)
        # With copy=False, arrays are shared
        assert np.shares_memory(ex['y']['values'], dd['y']['values'])

    def test_extract_includes_axes_fields(self):
        dd = make_datadict()
        ex = dd.extract(['y'])
        assert 'x' in ex
        assert 'y' in ex
        assert 'z' not in ex

    def test_extract_includes_meta(self):
        dd = make_datadict()
        dd.add_meta('info', 'hello')
        ex = dd.extract(['y'])
        assert ex.has_meta('info')

    def test_extract_preserves_field_meta(self):
        dd = make_datadict()
        dd.add_meta('cal', 42, data='y')
        ex = dd.extract(['y'])
        assert ex.meta_val('cal', 'y') == 42


# ===========================================================================
# 3. STRUCTURE TESTS
# ===========================================================================

class TestStructure:
    """Verify structure() correctness and independence."""

    def test_structure_has_empty_values(self):
        dd = make_datadict()
        s = dd.structure()
        for _, v in s.data_items():
            assert len(v['values']) == 0

    def test_structure_preserves_axes(self):
        dd = make_datadict()
        s = dd.structure()
        assert s['y']['axes'] == ['x']

    def test_structure_preserves_units(self):
        dd = make_datadict()
        s = dd.structure()
        assert s['y']['unit'] == 'A'

    def test_structure_preserves_meta(self):
        dd = make_datadict()
        dd.add_meta('info', 'test')
        s = dd.structure()
        assert s.meta_val('info') == 'test'

    def test_structure_axes_independent(self):
        """Mutating axes in structure must not affect original."""
        dd = make_datadict()
        s = dd.structure()
        s['y']['axes'].append('extra')
        assert 'extra' not in dd['y']['axes']

    def test_structure_preserves_custom_field_keys(self):
        """Custom keys in field dicts must be preserved."""
        dd = make_datadict()
        dd['y']['__shape__'] = (100,)
        dd['y']['__custom_meta__'] = 'hello'
        s = dd.structure()
        assert '__shape__' in s['y']
        assert '__custom_meta__' in s['y']

    def test_structure_with_remove_data(self):
        dd = make_meshgrid((5, 4))
        s = dd.structure(remove_data=['ax0'])
        assert 'ax0' not in s
        for dep in s.dependents():
            assert 'ax0' not in s[dep]['axes']


# ===========================================================================
# 4. EDGE CASES: DATA TYPES
# ===========================================================================

class TestEdgeCaseDataTypes:
    """Tests with unusual data types."""

    def test_object_array_with_none(self):
        """DataDict with object arrays containing None values."""
        dd = DataDict(
            x=dict(values=np.array([1, 2, 3, 4, 5], dtype=object)),
            y=dict(values=np.array([1.0, None, 3.0, None, 5.0], dtype=object),
                   axes=['x']),
        )
        assert dd.validate()
        dd2 = dd.copy()
        assert dd == dd2

    def test_complex_array(self):
        """DataDict with complex-valued data."""
        dd = DataDict(
            x=dict(values=np.arange(10, dtype=float)),
            y=dict(values=np.random.randn(10) + 1j * np.random.randn(10),
                   axes=['x']),
        )
        assert dd.validate()
        dd2 = dd.copy()
        assert dd == dd2
        dd2['y']['values'][0] = 999 + 0j
        assert dd['y']['values'][0] != 999 + 0j

    def test_integer_array(self):
        """DataDict with integer data (no NaN possible)."""
        dd = DataDict(
            x=dict(values=np.arange(10)),
            y=dict(values=np.arange(10, 20), axes=['x']),
        )
        assert dd.validate()
        dd2 = dd.copy()
        assert dd == dd2

    def test_masked_array_values(self):
        """DataDict where values are already MaskedArrays."""
        vals = np.ma.MaskedArray([1.0, 2.0, 3.0], mask=[False, True, False])
        dd = DataDict(
            x=dict(values=np.arange(3, dtype=float)),
            y=dict(values=vals, axes=['x']),
        )
        assert dd.validate()
        dd2 = dd.copy()
        assert np.ma.is_masked(dd2['y']['values'])

    def test_empty_datadict(self):
        """Empty DataDict operations."""
        dd = DataDict()
        s = dd.structure()
        assert s is not None
        dd2 = dd.copy()
        assert dd == dd2

    def test_single_point(self):
        """DataDict with a single data point."""
        dd = DataDict(
            x=dict(values=np.array([1.0])),
            y=dict(values=np.array([2.0]), axes=['x']),
        )
        assert dd.validate()
        dd2 = dd.copy()
        assert dd == dd2


# ===========================================================================
# 5. MASK_INVALID TESTS
# ===========================================================================

class TestMaskInvalid:
    """Tests for mask_invalid() behavior with different data."""

    def test_mask_invalid_clean_float_data(self):
        """Clean float data — all values valid."""
        dd = make_datadict()
        dd2 = dd.copy()
        dd2 = dd2.mask_invalid()
        # Values should be unchanged (though possibly wrapped in MaskedArray)
        for name, _ in dd2.data_items():
            assert np.allclose(
                np.asarray(dd.data_vals(name)),
                np.asarray(dd2.data_vals(name)),
            )

    def test_mask_invalid_with_nan(self):
        """Float data with NaN values should be masked."""
        dd = DataDict(
            x=dict(values=np.array([1.0, 2.0, 3.0])),
            y=dict(values=np.array([1.0, np.nan, 3.0]), axes=['x']),
        )
        dd = dd.mask_invalid()
        y_vals = dd.data_vals('y')
        assert isinstance(y_vals, np.ma.MaskedArray)
        assert y_vals.mask[1] == True

    def test_mask_invalid_with_none_objects(self):
        """Object array with None values should be masked."""
        dd = DataDict(
            x=dict(values=np.array([1, 2, 3], dtype=object)),
            y=dict(values=np.array([1.0, None, 3.0], dtype=object), axes=['x']),
        )
        dd = dd.mask_invalid()
        y_vals = dd.data_vals('y')
        assert isinstance(y_vals, np.ma.MaskedArray)

    def test_mask_invalid_preserves_structure(self):
        """Structure should be unchanged after masking."""
        dd = make_meshgrid()
        s_before = dd.structure()
        dd = dd.mask_invalid()
        s_after = dd.structure()
        assert DataDictBase.same_structure(
            s_before, s_after
        )


# ===========================================================================
# 6. MESHGRID CONVERSION TESTS
# ===========================================================================

class TestMeshgridConversions:
    """Test conversions between DataDict and MeshgridDataDict."""

    def test_roundtrip_datadict_meshgrid_datadict(self):
        """Tabular → grid → tabular should preserve data."""
        x = np.linspace(0, 1, 10)
        y = np.arange(5, dtype=float)
        xx, yy = np.meshgrid(x, y, indexing='ij')
        zz = xx * yy

        dd = DataDict(
            x=dict(values=xx.ravel()),
            y=dict(values=yy.ravel()),
            z=dict(values=zz.ravel(), axes=['x', 'y']),
        )
        mesh = datadict_to_meshgrid(dd)
        assert isinstance(mesh, MeshgridDataDict)
        assert mesh.shape() == (10, 5)

        dd2 = meshgrid_to_datadict(mesh)
        assert isinstance(dd2, DataDict)
        assert dd2.nrecords() == 50

    def test_datadict_to_meshgrid_copy_true(self):
        """copy=True should produce independent arrays."""
        x = np.arange(6, dtype=float)
        y = np.tile(np.arange(3, dtype=float), 2)
        dd = DataDict(
            x=dict(values=x),
            y=dict(values=y),
            z=dict(values=np.arange(6, dtype=float), axes=['x', 'y']),
        )
        mesh = datadict_to_meshgrid(dd, target_shape=(2, 3), copy=True)
        mesh['z']['values'][0, 0] = 999.0
        assert dd['z']['values'][0] != 999.0

    def test_datadict_to_meshgrid_preserves_meta(self):
        """Conversion should preserve global metadata."""
        x = np.arange(6, dtype=float)
        y = np.tile(np.arange(3, dtype=float), 2)
        dd = DataDict(
            x=dict(values=x),
            y=dict(values=y),
            z=dict(values=np.arange(6, dtype=float), axes=['x', 'y']),
            __info__='test_meta',
        )
        mesh = datadict_to_meshgrid(dd, target_shape=(2, 3))
        assert mesh.meta_val('info') == 'test_meta'

    def test_meshgrid_to_datadict_independent(self):
        """meshgrid_to_datadict should not share arrays with original."""
        mesh = make_meshgrid((5, 4))
        dd = meshgrid_to_datadict(mesh)
        dd['dep0']['values'][0] = 999.0
        assert mesh['dep0']['values'].ravel()[0] != 999.0


# ===========================================================================
# 7. MESHGRID VALIDATION TESTS
# ===========================================================================

class TestMeshgridValidation:
    """Test MeshgridDataDict validation, especially monotonicity checks."""

    def test_valid_monotonic_increasing(self):
        dd = make_meshgrid((5, 4))
        assert dd.validate()

    def test_valid_monotonic_decreasing(self):
        """Axes that decrease monotonically are valid."""
        dd = MeshgridDataDict()
        x = np.linspace(1, 0, 5)  # decreasing
        y = np.linspace(0, 1, 4)
        xx, yy = np.meshgrid(x, y, indexing='ij')
        dd['x'] = dict(values=xx, axes=[], unit='V', label='x')
        dd['y'] = dict(values=yy, axes=[], unit='V', label='y')
        dd['z'] = dict(values=xx + yy, axes=['x', 'y'], unit='A', label='z')
        assert dd.validate()

    def test_invalid_non_monotonic(self):
        """Axis that goes up then down should fail."""
        dd = MeshgridDataDict()
        x_vals = np.array([0, 1, 2, 1, 0], dtype=float)
        y_vals = np.arange(3, dtype=float)
        xx, yy = np.meshgrid(x_vals, y_vals, indexing='ij')
        dd['x'] = dict(values=xx, axes=[], unit='V', label='x')
        dd['y'] = dict(values=yy, axes=[], unit='V', label='y')
        dd['z'] = dict(values=np.random.randn(5, 3), axes=['x', 'y'],
                       unit='A', label='z')
        with pytest.raises(ValueError, match="not monotonous"):
            dd.validate()

    def test_invalid_flat_axis(self):
        """Axis with no variation should fail."""
        dd = MeshgridDataDict()
        x = np.array([1.0, 1.0, 1.0])
        y = np.arange(4, dtype=float)
        xx, yy = np.meshgrid(x, y, indexing='ij')
        dd['x'] = dict(values=xx, axes=[], unit='V', label='x')
        dd['y'] = dict(values=yy, axes=[], unit='V', label='y')
        dd['z'] = dict(values=np.random.randn(3, 4), axes=['x', 'y'],
                       unit='A', label='z')
        with pytest.raises(ValueError, match="no variation"):
            dd.validate()

    def test_valid_with_nan_in_axis(self):
        """Axis with NaN values (incomplete data) should still validate
        if the non-NaN values are monotonic."""
        dd = make_meshgrid((5, 4))
        dd['ax0']['values'][3, :] = np.nan
        dd['ax0']['values'][4, :] = np.nan
        # Should not raise — NaN steps are ignored
        assert dd.validate()

    def test_valid_3d_meshgrid(self):
        """3D meshgrid should validate correctly."""
        dd = make_meshgrid((5, 4, 3))
        assert dd.validate()

    def test_shape_mismatch_fails(self):
        """Different shapes across fields should fail."""
        dd = MeshgridDataDict()
        dd['x'] = dict(values=np.arange(10, dtype=float).reshape(2, 5),
                       axes=[])
        dd['z'] = dict(values=np.arange(12, dtype=float).reshape(3, 4),
                       axes=['x'])
        with pytest.raises(ValueError):
            dd.validate()


# ===========================================================================
# 8. SHAPES() EDGE CASES
# ===========================================================================

class TestShapes:
    """Test shapes() with various input states."""

    def test_shapes_after_validation(self):
        dd = make_datadict(50)
        dd.validate()
        shapes = dd.shapes()
        assert shapes['x'] == (50,)
        assert shapes['y'] == (50,)

    def test_shapes_with_list_values(self):
        """shapes() should work even before validation when values are lists."""
        dd = DataDictBase(
            x=dict(values=[1, 2, 3]),
            y=dict(values=[4, 5, 6], axes=['x']),
        )
        # Should not crash, even without validate()
        shapes = dd.shapes()
        assert shapes['x'] == (3,)

    def test_shapes_meshgrid(self):
        dd = make_meshgrid((10, 8))
        shapes = dd.shapes()
        for name in dd.dependents() + dd.axes():
            assert shapes[name] == (10, 8)


# ===========================================================================
# 9. PIPELINE DATA INTEGRITY TESTS
# ===========================================================================

class TestPipelineIntegrity:
    """Simulate pipeline operations and verify input is not mutated."""

    def _simulate_data_selector(self, data: DataDictBase) -> DataDictBase:
        """Simulate DataSelector.process() — extract a subset."""
        selected = data.extract(data.dependents()[:1])
        if isinstance(selected, DataDictBase):
            selected = DataDict(**selected)
            selected.validate()
        return selected

    def _simulate_gridder(self, data: DataDict) -> MeshgridDataDict:
        """Simulate DataGridder.process() — copy + grid."""
        data_copy = data.copy()
        return datadict_to_meshgrid(data_copy)

    def _simulate_dim_reducer(self, data: MeshgridDataDict) -> MeshgridDataDict:
        """Simulate DimensionReducer.process() — copy + mask."""
        data_copy = data.copy()
        return data_copy.mask_invalid()

    def test_pipeline_does_not_mutate_input(self):
        """Full pipeline must not modify the original input data."""
        # Create griddable data
        x = np.linspace(0, 1, 10)
        y = np.arange(5, dtype=float)
        xx, yy = np.meshgrid(x, y, indexing='ij')

        original = DataDict(
            x=dict(values=xx.ravel()),
            y=dict(values=yy.ravel()),
            z=dict(values=(xx * yy).ravel(), axes=['x', 'y']),
        )
        original.validate()

        # Save a reference-safe copy for comparison (cp.deepcopy fails on
        # DataDict due to _DataAccess inner class, so use the built-in copy)
        reference = original.copy()

        # Run simulated pipeline
        selected = self._simulate_data_selector(original)
        gridded = self._simulate_gridder(selected)
        reduced = self._simulate_dim_reducer(gridded)

        # Verify original is unchanged
        assert datasets_are_equal(original, reference)

    def test_pipeline_output_types(self):
        """Pipeline stages should produce the expected types."""
        x = np.linspace(0, 1, 10)
        y = np.arange(5, dtype=float)
        xx, yy = np.meshgrid(x, y, indexing='ij')

        dd = DataDict(
            x=dict(values=xx.ravel()),
            y=dict(values=yy.ravel()),
            z=dict(values=(xx * yy).ravel(), axes=['x', 'y']),
        )

        selected = self._simulate_data_selector(dd)
        assert isinstance(selected, DataDict)

        gridded = self._simulate_gridder(selected)
        assert isinstance(gridded, MeshgridDataDict)

        reduced = self._simulate_dim_reducer(gridded)
        assert isinstance(reduced, MeshgridDataDict)


# ===========================================================================
# 10. MESHGRID OPERATIONS: mean, slice
# ===========================================================================

class TestMeshgridOperations:
    """Test mean and slice operations on MeshgridDataDict."""

    def test_mean_reduces_axis(self):
        dd = make_meshgrid((10, 8))
        result = dd.mean('ax0')
        assert result.shape() == (8,)
        assert 'ax0' not in result

    def test_mean_does_not_mutate_original(self):
        dd = make_meshgrid((10, 8))
        original_shape = dd.shape()
        _ = dd.mean('ax0')
        assert dd.shape() == original_shape

    def test_slice_reduces_shape(self):
        dd = make_meshgrid((10, 8))
        result = dd.slice(ax0=slice(2, 5))
        assert result.shape() == (3, 8)

    def test_slice_does_not_mutate_original(self):
        dd = make_meshgrid((10, 8))
        original_shape = dd.shape()
        _ = dd.slice(ax0=slice(2, 5))
        assert dd.shape() == original_shape

    def test_slice_integer_selects_single_element(self):
        """Integer indexing on a meshgrid axis selects a single element,
        but _mesh_slice does NOT remove the axis — it creates a size-1 dim.
        Using a length-1 slice keeps the axis valid."""
        dd = make_meshgrid((10, 8))
        result = dd.slice(ax0=slice(3, 4))
        assert result.shape() == (1, 8)


# ===========================================================================
# 11. CUSTOM FIELD KEY PRESERVATION
# ===========================================================================

class TestCustomFieldKeys:
    """Verify that custom field keys are preserved through operations."""

    def test_copy_preserves_shape_key(self):
        dd = make_meshgrid((5, 4))
        dd['dep0']['__shape__'] = (5, 4)
        dd2 = dd.copy()
        assert dd2['dep0']['__shape__'] == (5, 4)

    def test_copy_preserves_per_field_meta(self):
        dd = make_datadict()
        dd['y']['__calibration__'] = {'gain': 1.5}
        dd2 = dd.copy()
        assert dd2['y']['__calibration__'] == {'gain': 1.5}

    def test_structure_preserves_shape_key(self):
        dd = make_meshgrid((5, 4))
        dd['dep0']['__shape__'] = (5, 4)
        s = dd.structure()
        assert '__shape__' in s['dep0']

    def test_extract_preserves_per_field_meta(self):
        dd = make_datadict()
        dd['y']['__calibration__'] = {'gain': 1.5}
        ex = dd.extract(['y'])
        assert ex['y']['__calibration__'] == {'gain': 1.5}


# ===========================================================================
# 12. DATASETS_ARE_EQUAL TESTS
# ===========================================================================

class TestDatasetsAreEqual:
    """Additional equality checks including edge cases."""

    def test_equal_meshgrids(self):
        dd = make_meshgrid()
        dd2 = dd.copy()
        assert datasets_are_equal(dd, dd2)

    def test_not_equal_different_values(self):
        dd = make_meshgrid()
        dd2 = dd.copy()
        dd2['dep0']['values'][0, 0] += 1.0
        assert not datasets_are_equal(dd, dd2)

    def test_not_equal_different_types(self):
        dd = make_datadict()
        mesh = make_meshgrid()
        assert not datasets_are_equal(dd, mesh)

    def test_not_equal_different_shape(self):
        dd1 = make_meshgrid((5, 4))
        dd2 = make_meshgrid((5, 3))
        assert not datasets_are_equal(dd1, dd2)

    def test_equal_with_meta(self):
        dd = make_datadict()
        dd.add_meta('info', 'value')
        dd2 = dd.copy()
        assert datasets_are_equal(dd, dd2)
        assert datasets_are_equal(dd, dd2, ignore_meta=True)

    def test_not_equal_meta_differs(self):
        dd = make_datadict()
        dd.add_meta('info', 'value')
        dd2 = dd.copy()
        dd2.set_meta('info', 'different')
        assert not datasets_are_equal(dd, dd2)
        assert datasets_are_equal(dd, dd2, ignore_meta=True)
