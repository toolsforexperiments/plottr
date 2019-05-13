"""
Testing how to make a custom app with gui.
"""
import sys

import numpy as np
import lmfit

from plottr import QtGui
from plottr.data.datadict import DataDictBase
from plottr.data.qcodes_dataset import QCodesDSLoader
from plottr.node.tools import linearFlowchart
from plottr.node.data_selector import DataSelector
from plottr.node.grid import DataGridder
from plottr.node.dim_reducer import XYSelector
from plottr.node.autonode import autonode
from plottr.plot.mpl import PlotNode
from plottr.apps.autoplot import QCAutoPlotMainWindow


# specify the sine function we're fitting to
def sinefunc(x, amp, freq, phase):
    return amp * np.sin(2 * np.pi * (freq * x + phase))

# this is the node. Using the autonode decorator, we only need
# to specify the processing function.
@autonode(
    'sineFitter',
    confirm=True,
    frequencyGuess={'initialValue': 1.0, 'type': float},
)
def sinefit(self, dataIn: DataDictBase = None):
    if dataIn is None:
        return None

    # this is just a ghetto example: only support very simple datasets
    naxes = len(dataIn.axes())
    ndeps = len(dataIn.dependents())
    if not (naxes == 1 and ndeps == 1):
        return dict(dataOut=dataIn)

    # getting the data
    axname = dataIn.axes()[0]
    x = dataIn.data_vals(axname)
    y = dataIn.data_vals(dataIn.dependents()[0])

    # try to fit
    sinemodel = lmfit.Model(sinefunc)
    p0 = sinemodel.make_params(amp=1, freq=self.frequencyGuess, phase=0)
    result = sinemodel.fit(y, p0, x=x)

    # if the fit works, add the fit result to the output
    dataOut = dataIn.copy()
    if result.success:
        dataOut['fit'] = dict(values=result.best_fit, axes=[axname,])
        dataOut.add_meta('info', result.fit_report())
    else:
        dataOut.add_meta('info', 'Could not fit sine.')

    return dict(dataOut=dataOut)


def main(pathAndId):
    app = QtGui.QApplication([])

    # flowchart and window
    fc = linearFlowchart(
        ('Dataset loader', QCodesDSLoader),
        ('Data selection', DataSelector),
        ('Grid', DataGridder),
        ('Dimension assignment', XYSelector),
        ('Sine fit', sinefit),
        ('plot', PlotNode),
    )

    win = QCAutoPlotMainWindow(fc, pathAndId=pathAndId)
    win.show()

    return app.exec_()


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('need to specify .db path and run id.')
    else:

        pathAndId = sys.argv[1], sys.argv[2]
        print('try to open:', pathAndId)
        main(pathAndId)
