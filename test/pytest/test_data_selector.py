import numpy as np

from plottr.apps.tools import make_sequential_flowchart
from plottr.node.data_selector import DataSelector
from ..common import data as testdata


def test_data_extraction(qtbot):
    """
    Test whether extraction of one dependent gives the right data back.
    """
    DataSelector.useUi = False

    data = testdata.three_compatible_3d_sets()
    data_name = data.dependents()[0]
    field_names = [data_name] + data.axes(data_name)

    nodes, fc = make_sequential_flowchart([DataSelector], inputData=data)
    nodes[0].selectedData = data_name
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

    nodes, fc = make_sequential_flowchart([DataSelector], inputData=data)
    nodes[0].selectedData = data_names
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
    nodes, fc = make_sequential_flowchart([DataSelector], inputData=data)
    nodes[0].selectedData = data.dependents()[0], data.dependents()[1]
    assert fc.output()['dataOut'] == {}

    nodes[0].selectedData = data.dependents()[0]
    assert fc.output()['dataOut'].dependents() == [data.dependents()[0]]

    nodes[0].selectedData = data.dependents()[1]
    assert fc.output()['dataOut'].dependents() == [data.dependents()[1]]
