import numpy as np

from plottr.data.datadict import MeshgridDataDict
from plottr.node.dim_reducer import DimensionReducer, ReductionMethod, XYSelector
from plottr.node.tools import linearFlowchart
from plottr.utils import num


def test_reduction(qtbot):
    """Test basic dimension reduction."""
    DimensionReducer.uiClass = None

    fc = linearFlowchart(('dim_red', DimensionReducer))
    node = fc.nodes()['dim_red']

    x = np.arange(5.0)
    y = np.linspace(0, 1, 5)
    z = np.arange(4.0, 6.0, 1.0)
    xx, yy, zz = np.meshgrid(x, y, z, indexing='ij')
    vals = xx * yy * zz
    data = MeshgridDataDict(
        x=dict(values=xx),
        y=dict(values=yy),
        z=dict(values=zz),
        vals=dict(values=vals, axes=['x', 'y', 'z'])
    )
    assert data.validate()

    fc.setInput(dataIn=data)
    assert num.arrays_equal(
        fc.outputValues()['dataOut'].data_vals('vals'),
        vals
    )

    node.reductions = {'y': (np.mean, [], {})}

    out = fc.outputValues()['dataOut']
    assert num.arrays_equal(
        vals.mean(axis=1),
        out.data_vals('vals')
    )
    assert out.axes('vals') == ['x', 'z']

    node.reductions = {
        'y': (ReductionMethod.elementSelection, [], {'index': 0}),
        'z': (ReductionMethod.average,)
    }

    out = fc.outputValues()['dataOut']
    assert num.arrays_equal(
        vals[:, 0, :].mean(axis=-1),
        out.data_vals('vals')
    )
    assert out.axes('vals') == ['x']


def test_xy_selector(qtbot):
    """Basic XY selector node test."""

    XYSelector.uiClass = None

    fc = linearFlowchart(('xysel', XYSelector))
    node = fc.nodes()['xysel']

    x = np.arange(5.0)
    y = np.linspace(0, 1, 5)
    z = np.arange(4.0, 6.0, 1.0)
    xx, yy, zz = np.meshgrid(x, y, z, indexing='ij')
    vals = xx * yy * zz
    data = MeshgridDataDict(
        x=dict(values=xx),
        y=dict(values=yy),
        z=dict(values=zz),
        vals=dict(values=vals, axes=['x', 'y', 'z'])
    )
    assert data.validate()

    fc.setInput(dataIn=data)

    # this should return None, because no x/y axes were set.
    assert fc.outputValues()['dataOut'] is None

    # now select two axes, and test that the other one is correctly selected
    node.xyAxes = ('x', 'y')
    assert num.arrays_equal(
        fc.outputValues()['dataOut'].data_vals('vals'),
        vals[:,:,0]
    )

    # try a different reduction on the third axis
    node.reductions = {'z': (ReductionMethod.average, [], {})}
    assert num.arrays_equal(
        fc.outputValues()['dataOut'].data_vals('vals'),
        vals.mean(axis=-1)
    )

    # Test transposing the data by flipping x/y
    node.xyAxes = ('y', 'x')
    assert num.arrays_equal(
        fc.outputValues()['dataOut'].data_vals('vals'),
        vals.mean(axis=-1).transpose((1, 0))
    )

def test_xy_selector_with_roles(qtbot):
    """Testing XY selector using the roles 'meta' property."""

    XYSelector.uiClass = None

    fc = linearFlowchart(('xysel', XYSelector))
    node = fc.nodes()['xysel']

    x = np.arange(5.0)
    y = np.linspace(0, 1, 5)
    z = np.arange(4.0, 6.0, 1.0)
    xx, yy, zz = np.meshgrid(x, y, z, indexing='ij')
    vals = xx * yy * zz
    data = MeshgridDataDict(
        x=dict(values=xx),
        y=dict(values=yy),
        z=dict(values=zz),
        vals=dict(values=vals, axes=['x', 'y', 'z'])
    )
    assert data.validate()

    fc.setInput(dataIn=data)

    # this should return None, because no x/y axes were set.
    assert fc.outputValues()['dataOut'] is None

    # now select two axes, and test that the other one is correctly selected
    node.xyAxes = ('x', 'y')

    assert num.arrays_equal(
        fc.outputValues()['dataOut'].data_vals('vals'),
        vals[:,:,0]
    )
    assert node.dimensionRoles == {
        'x': 'x-axis',
        'y': 'y-axis',
        'z': (ReductionMethod.elementSelection, [], {'index': 0, 'axis': 2})
    }

    # now set the role directly through the meta property
    node.dimensionRoles = {
        'x': 'y-axis',
        'y': (ReductionMethod.average, [], {}),
        'z': 'x-axis',
    }

    assert node.xyAxes == ('z', 'x')
    assert num.arrays_equal(
        fc.outputValues()['dataOut'].data_vals('vals'),
        vals[:,:,:].mean(axis=1).transpose((1, 0))
    )
