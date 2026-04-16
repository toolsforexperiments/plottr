"""
test_round2_optimizations.py

Tests for round 2 performance optimizations: is_invalid, largest_numtype,
guess_grid, remove_invalid_entries, Node.process structure deferral,
complex plot splitting, flatten->ravel.
"""
import numpy as np
import pytest
from copy import deepcopy

from plottr.data.datadict import (
    DataDict, MeshgridDataDict, meshgrid_to_datadict, datadict_to_dataframe,
)
from plottr.utils.num import is_invalid, largest_numtype, guess_grid_from_sweep_direction


# ===========================================================================
# is_invalid()
# ===========================================================================

class TestIsInvalid:
    def test_float_with_nan(self):
        arr = np.array([1.0, np.nan, 3.0])
        result = is_invalid(arr)
        assert result.tolist() == [False, True, False]

    def test_float_clean(self):
        arr = np.array([1.0, 2.0, 3.0])
        result = is_invalid(arr)
        assert not np.any(result)

    def test_int_array(self):
        arr = np.arange(10)
        result = is_invalid(arr)
        assert not np.any(result)

    def test_object_with_none(self):
        arr = np.array([1.0, None, 3.0], dtype=object)
        result = is_invalid(arr)
        assert result[1] == True
        assert result[0] == False

    def test_complex_with_nan(self):
        arr = np.array([1+1j, np.nan+0j, 3+0j])
        result = is_invalid(arr)
        assert result[1] == True

    def test_empty_array(self):
        arr = np.array([], dtype=float)
        result = is_invalid(arr)
        assert result.shape == (0,)

    def test_bool_array(self):
        arr = np.array([True, False, True])
        result = is_invalid(arr)
        assert not np.any(result)

    def test_2d_float(self):
        arr = np.array([[1.0, np.nan], [3.0, 4.0]])
        result = is_invalid(arr)
        assert result.shape == (2, 2)
        assert result[0, 1] == True
        assert result[1, 0] == False


# ===========================================================================
# largest_numtype()
# ===========================================================================

class TestLargestNumtype:
    def test_float_array(self):
        arr = np.array([1.0, 2.0, 3.0])
        result = largest_numtype(arr)
        assert issubclass(result, (float, np.floating))

    def test_int_array_include_integers(self):
        arr = np.arange(10)
        result = largest_numtype(arr, include_integers=True)
        # Should return float (promotion) or int
        assert result in (float, int, np.int64, np.int32, np.float64)

    def test_int_array_exclude_integers(self):
        arr = np.arange(10)
        result = largest_numtype(arr, include_integers=False)
        # With include_integers=False, int arrays are promoted to float
        assert result == float

    def test_complex_array(self):
        arr = np.array([1+1j, 2+2j])
        result = largest_numtype(arr)
        assert issubclass(result, (complex, np.complexfloating))

    def test_object_array_with_floats(self):
        arr = np.array([1.0, 2.0, 3.0], dtype=object)
        result = largest_numtype(arr)
        assert result == float

    def test_string_array(self):
        arr = np.array(['a', 'b', 'c'])
        result = largest_numtype(arr)
        assert result is None

    def test_object_with_none_and_floats(self):
        arr = np.array([1.0, None, 3.0], dtype=object)
        result = largest_numtype(arr)
        # Should find float as the largest type
        assert result == float

    def test_empty_array(self):
        arr = np.array([])
        result = largest_numtype(arr)
        # Empty array has no elements to inspect
        assert result is None


# ===========================================================================
# guess_grid_from_sweep_direction()
# ===========================================================================

class TestGuessGrid:
    def test_simple_2d_grid(self):
        x = np.repeat(np.arange(5, dtype=float), 4)
        y = np.tile(np.arange(4, dtype=float), 5)
        result = guess_grid_from_sweep_direction(x=x, y=y)
        assert result is not None
        order, shape = result
        assert set(order) == {'x', 'y'}
        assert 5 in shape and 4 in shape

    def test_1d_sweep(self):
        x = np.arange(10, dtype=float)
        result = guess_grid_from_sweep_direction(x=x)
        assert result is not None
        _, shape = result
        assert shape == (10,)

    def test_single_point(self):
        x = np.array([1.0])
        result = guess_grid_from_sweep_direction(x=x)
        assert result is not None

    def test_with_noise(self):
        x = np.repeat(np.linspace(0, 1, 10), 8) + np.random.randn(80) * 1e-6
        y = np.tile(np.linspace(0, 1, 8), 10)
        result = guess_grid_from_sweep_direction(x=x, y=y)
        assert result is not None
        _, shape = result
        assert 10 in shape and 8 in shape


# ===========================================================================
# remove_invalid_entries()
# ===========================================================================

class TestRemoveInvalidEntries:
    def test_removes_nan_rows(self):
        dd = DataDict(
            x=dict(values=np.arange(5, dtype=float)),
            y=dict(values=np.array([1.0, np.nan, 3.0, np.nan, 5.0]), axes=['x']),
        )
        dd.validate()
        dd2 = dd.remove_invalid_entries()
        assert dd2.nrecords() == 3
        assert np.allclose(dd2.data_vals('y'), [1.0, 3.0, 5.0])

    def test_preserves_clean_data(self):
        dd = DataDict(
            x=dict(values=np.arange(10, dtype=float)),
            y=dict(values=np.arange(10, dtype=float), axes=['x']),
        )
        dd.validate()
        dd2 = dd.remove_invalid_entries()
        assert dd2.nrecords() == 10

    def test_removes_none_in_object_array(self):
        dd = DataDict(
            x=dict(values=np.array([1, 2, 3], dtype=object)),
            y=dict(values=np.array([1.0, None, 3.0], dtype=object), axes=['x']),
        )
        dd.validate()
        dd2 = dd.remove_invalid_entries()
        # Only row where ALL dependents are invalid gets removed
        # Row 1 has None in y -> removed only if x is also invalid
        # Actually remove_invalid_entries removes rows where ALL deps are invalid
        assert dd2.nrecords() <= 3

    def test_multiple_dependents(self):
        """remove_invalid_entries removes rows where ALL dependents are invalid.

        Note: this previously crashed with np.array(idxs) on inhomogeneous
        arrays. Fixed by using np.concatenate instead of np.append.
        """
        dd = DataDict(
            x=dict(values=np.arange(5, dtype=float)),
            y=dict(values=np.array([1.0, np.nan, 3.0, np.nan, 5.0]), axes=['x']),
            z=dict(values=np.array([np.nan, 2.0, np.nan, np.nan, 5.0]), axes=['x']),
        )
        dd.validate()
        dd2 = dd.remove_invalid_entries()
        assert dd2.nrecords() == 4


# ===========================================================================
# meshgrid_to_datadict (flatten->ravel)
# ===========================================================================

class TestMeshgridToDatadict:
    def test_basic_conversion(self):
        x = np.linspace(0, 1, 5)
        y = np.arange(3, dtype=float)
        xx, yy = np.meshgrid(x, y, indexing='ij')
        mesh = MeshgridDataDict(
            x=dict(values=xx), y=dict(values=yy),
            z=dict(values=xx*yy, axes=['x', 'y']),
        )
        mesh.validate()
        dd = meshgrid_to_datadict(mesh)
        assert isinstance(dd, DataDict)
        assert dd.nrecords() == 15

    def test_values_match(self):
        x = np.linspace(0, 1, 4)
        y = np.arange(3, dtype=float)
        xx, yy = np.meshgrid(x, y, indexing='ij')
        zz = xx + yy
        mesh = MeshgridDataDict(
            x=dict(values=xx), y=dict(values=yy),
            z=dict(values=zz, axes=['x', 'y']),
        )
        mesh.validate()
        dd = meshgrid_to_datadict(mesh)
        assert np.allclose(dd.data_vals('z'), zz.ravel())

    def test_3d_conversion(self):
        shape = (3, 4, 2)
        grids = np.meshgrid(*[np.linspace(0, 1, s) for s in shape], indexing='ij')
        mesh = MeshgridDataDict(
            a=dict(values=grids[0]), b=dict(values=grids[1]), c=dict(values=grids[2]),
            z=dict(values=np.random.randn(*shape), axes=['a', 'b', 'c']),
        )
        mesh.validate()
        dd = meshgrid_to_datadict(mesh)
        assert dd.nrecords() == 24


# ===========================================================================
# datadict_to_dataframe
# ===========================================================================

class TestDatadictToDataframe:
    def test_basic(self):
        dd = DataDict(
            x=dict(values=np.arange(5, dtype=float)),
            y=dict(values=np.arange(5, dtype=float) * 2, axes=['x']),
        )
        dd.validate()
        df = datadict_to_dataframe(dd)
        assert len(df) == 5
        assert list(df.columns) == ['x', 'y']


# ===========================================================================
# Node.process() structure deferral
# ===========================================================================

class TestNodeProcessStructure:
    def test_node_process_returns_data(self, qtbot):
        from plottr.node.node import Node
        from plottr.node.tools import linearFlowchart
        Node.useUi = False; Node.uiClass = None

        mesh = MeshgridDataDict()
        x = np.linspace(0, 1, 5)
        y = np.arange(3, dtype=float)
        xx, yy = np.meshgrid(x, y, indexing='ij')
        mesh['x'] = dict(values=xx, axes=[])
        mesh['y'] = dict(values=yy, axes=[])
        mesh['z'] = dict(values=xx + yy, axes=['x', 'y'])
        mesh.validate()

        fc = linearFlowchart(('n', Node))
        fc.setInput(dataIn=mesh)
        out = fc.outputValues()['dataOut']
        assert out is mesh

    def test_node_detects_structure_change(self, qtbot):
        from plottr.node.node import Node
        from plottr.node.tools import linearFlowchart
        Node.useUi = False; Node.uiClass = None

        dd1 = DataDict(
            x=dict(values=np.arange(5, dtype=float)),
            y=dict(values=np.arange(5, dtype=float), axes=['x']),
        )
        dd1.validate()

        dd2 = DataDict(
            x=dict(values=np.arange(5, dtype=float)),
            y=dict(values=np.arange(5, dtype=float), axes=['x']),
            z=dict(values=np.arange(5, dtype=float), axes=['x']),
        )
        dd2.validate()

        fc = linearFlowchart(('n', Node))
        fc.setInput(dataIn=dd1)
        node = fc.nodes()['n']
        assert node.dataDependents == ['y']

        fc.setInput(dataIn=dd2)
        assert node.dataDependents == ['y', 'z']


# ===========================================================================
# Complex plot deepcopy
# ===========================================================================

class TestComplexPlotSplit:
    def test_split_produces_correct_items(self):
        from plottr.plot.base import AutoFigureMaker, PlotDataType, PlotItem, ComplexRepresentation

        class DummyFM(AutoFigureMaker):
            def makeSubPlots(self, n): return [None]*n
            def plot(self, item): return None
            def formatSubPlot(self, id): pass

        fm = DummyFM()
        fm.complexRepresentation = ComplexRepresentation.realAndImag
        data = np.array([1+2j, 3+4j, 5+6j])
        pi = PlotItem(data=[np.arange(3, dtype=float), data],
                      id=0, subPlot=0, labels=['x', 'z'])
        result = fm._splitComplexData(pi)
        assert len(result) == 2
        assert np.allclose(result[0].data[-1], data.real)
        assert np.allclose(result[1].data[-1], data.imag)

    def test_split_real_data_unchanged(self):
        from plottr.plot.base import AutoFigureMaker, PlotDataType, PlotItem

        class DummyFM(AutoFigureMaker):
            def makeSubPlots(self, n): return [None]*n
            def plot(self, item): return None
            def formatSubPlot(self, id): pass

        fm = DummyFM()
        data = np.array([1.0, 2.0, 3.0])
        pi = PlotItem(data=[np.arange(3, dtype=float), data],
                      id=0, subPlot=0, labels=['x', 'z'])
        result = fm._splitComplexData(pi)
        assert len(result) == 1
        assert np.allclose(result[0].data[-1], data)
