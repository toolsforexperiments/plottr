import numpy as np

from plottr.data.datadict import MeshgridDataDict, DataDict
from plottr.node.tools import linearFlowchart
from plottr.node.filter.correct_offset import SubtractAverage
from plottr.utils import num


def test_average_subtraction(qtbot):
    """Test the subtract average filter node"""

    SubtractAverage.useUi = False
    SubtractAverage.uiClass = None

    fc = linearFlowchart(
        ('Subtract Average', SubtractAverage),
    )
    node = fc.nodes()['Subtract Average']

    x = np.arange(11) - 5.
    y = np.linspace(0, 10, 51)
    xx, yy = np.meshgrid(x, y, indexing='ij')
    zz = np.sin(yy) + xx
    zz_ref_avg_y = np.sin(yy) - np.sin(yy).mean()

    data = MeshgridDataDict(
        x = dict(values=xx),
        y = dict(values=yy),
        z = dict(values=zz, axes=['x', 'y'])
    )
    assert data.validate()

    fc.setInput(dataIn=data)
    assert num.arrays_equal(
        zz,
        fc.outputValues()['dataOut'].data_vals('z')
    )

    node.averagingAxis = 'y'
    assert num.arrays_equal(
        zz_ref_avg_y,
        fc.outputValues()['dataOut'].data_vals('z'),
    )
