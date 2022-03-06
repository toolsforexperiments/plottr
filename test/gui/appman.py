"""Test script for the app manager."""

import numpy as np

from plottr import log, qtapp
from plottr.data.datadict import DataDictBase, DataDict
from plottr.apps.autoplot import autoplot
from plottr.apps.appmanager import AppManager


logger = log.getLogger(__name__)


def _make_testdata() -> DataDictBase:
    x, y, z = (np.linspace(-5,5,51) for i in range(3))
    xx, yy, zz = np.meshgrid(x, y, z, indexing='ij')
    vals = np.exp(-yy**2-zz**2) + np.random.normal(loc=0, size=xx.shape)
    return DataDict(
        x=dict(values=xx),
        y=dict(values=yy),
        z=dict(values=zz),
        vals=dict(values=vals, axes=['x', 'y', 'z'])
    )


if __name__ == '__main__':
    log.enableStreamHandler(True)
    logger.setLevel(log.logging.DEBUG)

    application = qtapp()
    appman = AppManager([('regular autoplot', autoplot)])

    # launch an app and set a node option
    from plottr.node.grid import GridOption
    appman.launchApp(0, 'regular autoplot')
    print(appman.message(0, 'Grid', 'grid', (GridOption.guessShape, {})))

    # launch an app and try to set something to a bad target
    appman.launchApp(1, 'regular autoplot')
    print(appman.message(1, 'target', 'property', 'value'))

    # send input data to an app / retrieve output data
    print(appman.message(0, '', 'setInput', {'dataIn': _make_testdata()}))
    print(appman.message(0, '', 'getOutput', None))

    application.exec_()
