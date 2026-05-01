import numpy as np

# from plottr.apps.tools import make_sequential_flowchart
from plottr.node.tools import linearFlowchart
from plottr.node.data_selector import DataSelector
from plottr.utils import testdata


def test_data_extraction(qtbot):
    """
    Test whether extraction of one dependent gives the right data back.
    """
    DataSelector.useUi = False

    data = testdata.three_compatible_3d_sets()
    data_name = data.dependents()[0]
    field_names = [data_name] + data.axes(data_name)

    fc = linearFlowchart(('selector', DataSelector))
    node = fc.nodes()['selector']

    fc.setInput(dataIn=data)
    node.selectedData = data_name
    out = fc.output()['dataOut']

    assert out.dependents() == [data_name]
    for d, _ in out.data_items():
        assert d in field_names

    assert np.all(np.isclose(
        data.data_vals(data_name), out.data_vals(data_name),
        atol=1e-15
    ))


def test_data_extraction2(qtbot):
    """
    Test whether extraction of two dependents gives the right data back.
    """
    DataSelector.useUi = False

    data = testdata.three_compatible_3d_sets()
    data_names = [data.dependents()[0], data.dependents()[1]]
    field_names = data_names + data.axes(data_names[0])

    fc = linearFlowchart(('selector', DataSelector))
    node = fc.nodes()['selector']

    fc.setInput(dataIn=data)
    node.selectedData = data_names
    out = fc.output()['dataOut']

    assert out.dependents() == data_names
    for d, _ in out.data_items():
        assert d in field_names

    assert np.all(np.isclose(
        data.data_vals(data_names[0]), out.data_vals(data_names[0]),
        atol=1e-15
    ))

    assert np.all(np.isclose(
        data.data_vals(data_names[1]), out.data_vals(data_names[1]),
        atol=1e-15
    ))


def test_incompatible_sets(qtbot):
    """
    Test that selecting incompatible data sets give None output.
    """
    DataSelector.useUi = False

    data = testdata.three_incompatible_3d_sets()
    fc = linearFlowchart(('selector', DataSelector))
    node = fc.nodes()['selector']
    fc.setInput(dataIn=data)
    node.selectedData = data.dependents()[0], data.dependents()[1]
    assert fc.output()['dataOut'] == None

    node.selectedData = data.dependents()[0]
    assert fc.output()['dataOut'].dependents() == [data.dependents()[0]]

    node.selectedData = data.dependents()[1]
    assert fc.output()['dataOut'].dependents() == [data.dependents()[1]]


# -- Selection buttons (select all, deselect, 1D, 2D) --

class TestSelectionButtons:
    """Verify Select All / Deselect / 1D / 2D in DataSelectionWidget."""

    @staticmethod
    def _mixed():
        from plottr.data.datadict import DataDictBase
        return DataDictBase(
            trace1d=dict(values=np.arange(10.0), axes=['x']),
            trace1d_b=dict(values=np.arange(10.0), axes=['x']),
            x=dict(values=np.arange(10.0)),
            map2d=dict(values=np.arange(20.0), axes=['x', 'y']),
            map2d_b=dict(values=np.arange(20.0), axes=['x', 'y']),
            y=dict(values=np.arange(20.0)),
        )

    def test_select_all(self, qtbot):
        from plottr.gui.data_display import DataSelectionWidget
        w = DataSelectionWidget(); qtbot.addWidget(w)
        dd = self._mixed(); w.setData(dd, dd.shapes())
        w.selectAll()
        assert set(w.getSelectedData()) == set(dd.dependents())

    def test_deselect_all_selects_first(self, qtbot):
        """deselectAll should select only the first dependent (always keep one)."""
        from plottr.gui.data_display import DataSelectionWidget
        w = DataSelectionWidget(); qtbot.addWidget(w)
        dd = self._mixed(); w.setData(dd, dd.shapes())
        w.selectAll()
        w.deselectAll()
        selected = w.getSelectedData()
        assert len(selected) == 1
        assert selected[0] == dd.dependents()[0]

    def test_select_1d(self, qtbot):
        from plottr.gui.data_display import DataSelectionWidget
        w = DataSelectionWidget(); qtbot.addWidget(w)
        dd = self._mixed(); w.setData(dd, dd.shapes())
        w.selectByNdims(1)
        sel = w.getSelectedData()
        assert 'trace1d' in sel and 'trace1d_b' in sel
        assert 'map2d' not in sel

    def test_select_2d(self, qtbot):
        from plottr.gui.data_display import DataSelectionWidget
        w = DataSelectionWidget(); qtbot.addWidget(w)
        dd = self._mixed(); w.setData(dd, dd.shapes())
        w.selectByNdims(2)
        sel = w.getSelectedData()
        assert 'map2d' in sel and 'map2d_b' in sel
        assert 'trace1d' not in sel

    def test_select_resets_previous(self, qtbot):
        from plottr.gui.data_display import DataSelectionWidget
        w = DataSelectionWidget(); qtbot.addWidget(w)
        dd = self._mixed(); w.setData(dd, dd.shapes())
        w.selectAll()
        w.selectByNdims(1)
        for name in w.getSelectedData():
            assert len(dd.axes(name)) == 1

    def test_has_dependents_with_ndims(self, qtbot):
        from plottr.gui.data_display import DataSelectionWidget
        w = DataSelectionWidget(); qtbot.addWidget(w)
        dd = self._mixed(); w.setData(dd, dd.shapes())
        assert w.has_dependents_with_ndims(1)
        assert w.has_dependents_with_ndims(2)
        assert not w.has_dependents_with_ndims(3)

    def test_batch_emits_single_signal(self, qtbot):
        from plottr.gui.data_display import DataSelectionWidget
        w = DataSelectionWidget(); qtbot.addWidget(w)
        dd = self._mixed(); w.setData(dd, dd.shapes())
        count = [0]
        w.dataSelectionMade.connect(lambda _: count.__setitem__(0, count[0] + 1))
        w.selectAll()
        assert count[0] == 1

    def test_empty_dataset(self, qtbot):
        from plottr.gui.data_display import DataSelectionWidget
        from plottr.data.datadict import DataDictBase
        w = DataSelectionWidget(); qtbot.addWidget(w)
        w.setData(DataDictBase(), {})
        w.selectAll()
        assert w.getSelectedData() == []
