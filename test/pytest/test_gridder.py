import numpy as np

from plottr.data.datadict import MeshgridDataDict, DataDict
from plottr.node.tools import linearFlowchart
from plottr.node.grid import DataGridder, GridOption
from plottr.utils import testdata
from plottr.utils import num


def test_basic_gridding(qtbot):
    """Test simple gridding tasks"""

    DataGridder.useUi = False
    DataGridder.uiClass = None

    fc = linearFlowchart(('grid', DataGridder))
    node = fc.nodes()['grid']

    x = np.arange(5.0)
    y = np.linspace(0, 1, 5)
    z = np.arange(4.0, 6.0, 1.0)
    xx, yy, zz = np.meshgrid(x, y, z, indexing='ij')
    vv = xx * yy * zz
    x1d, y1d, z1d = xx.flatten(), yy.flatten(), zz.flatten()
    v1d = vv.flatten()
    data = DataDict(
        x=dict(values=x1d),
        y=dict(values=y1d),
        z=dict(values=z1d),
        vals=dict(values=v1d, axes=['x', 'y', 'z'])
    )
    assert data.validate()

    fc.setInput(dataIn=data)
    assert num.arrays_equal(
        fc.outputValues()['dataOut'].data_vals('vals'),
        v1d,
    )

    node.grid = GridOption.guessShape, dict()
    assert num.arrays_equal(
        fc.outputValues()['dataOut'].data_vals('vals'),
        vv,
    )

    node.grid = GridOption.specifyShape, dict(shape=(5, 5, 2))
    assert num.arrays_equal(
        fc.outputValues()['dataOut'].data_vals('vals'),
        vv,
    )

