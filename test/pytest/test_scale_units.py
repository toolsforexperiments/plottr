from numpy.testing import assert_allclose

from plottr.data.datadict import DataDict
from plottr.node.tools import linearFlowchart
from plottr.node.scaleunits import ScaleUnits

import numpy as np


def test_basic_scale_units(qtbot):

    ScaleUnits.useUi = False
    ScaleUnits.uiClass = None

    fc = linearFlowchart(('scale_units', ScaleUnits))
    node = fc.nodes()['scale_units']

    x = np.arange(0, 5.0e-9, 1.0e-9)
    y = np.linspace(0, 1e9, 5)
    z = np.arange(4.0e6, 6.0e6, 1.0e6)
    xx, yy, zz = np.meshgrid(x, y, z, indexing='ij')
    vv = xx * yy * zz
    x1d, y1d, z1d = xx.flatten(), yy.flatten(), zz.flatten()
    v1d = vv.flatten()
    data = DataDict(
        x=dict(values=x1d, unit='V'),
        y=dict(values=y1d, unit="A"),
        z=dict(values=z1d, unit="Foobar"),
        vals=dict(values=v1d, axes=['x', 'y', 'z'])
    )
    assert data.validate()

    fc.setInput(dataIn=data)

    output = fc.outputValues()['dataOut']

    assert output['x']['unit'] == 'nV'
    assert_allclose(output['x']["values"],
                    (xx*1e9).ravel())

    assert output['y']['unit'] == 'GA'
    assert_allclose(output['y']["values"],
                    (yy / 1e9).ravel())

    assert output['z']["unit"] == '$10^{6}$ Foobar'
    assert_allclose(output['z']["values"],
                    (zz / 1e6).ravel())

    assert output['vals']['unit'] == ''
    assert_allclose(output['vals']['values'],
                    vv.flatten())
