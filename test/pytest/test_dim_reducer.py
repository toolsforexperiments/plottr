import numpy as np

from plottr.data.datadict import MeshgridDataDict
from plottr.node.dim_reducer import DimensionReducer, ReductionMethod
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
