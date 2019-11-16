"""
Testing how to make a custom app with gui.
"""
import numpy as np
import lmfit

from plottr import QtGui
from plottr.data.datadict import DataDictBase, MeshgridDataDict
from plottr.gui.tools import flowchartAutoPlot
from plottr.node.dim_reducer import XYSelector
from plottr.node.autonode import autonode


def makeData():
    xvals = np.linspace(0, 10, 51)
    reps = np.arange(20)
    xx, rr = np.meshgrid(xvals, reps, indexing='ij')
    data = sinefunc(xx, amp=0.8, freq=0.25, phase=0.1)
    noise = np.random.normal(scale=0.2, size=data.shape)
    data += noise

    dd = MeshgridDataDict(
        x=dict(values=xx),
        repetition=dict(values=rr),
        sine=dict(values=data, axes=['x', 'repetition']),
    )
    return dd


def sinefunc(x, amp, freq, phase):
    return amp * np.sin(2 * np.pi * (freq * x + phase))


@autonode(
    'sineFitter',
    confirm=True,
    frequencyGuess={'initialValue': 1.0, 'type': float},
)
def sinefit(self, dataIn: DataDictBase = None):
    if dataIn is None:
        return None

    if len(dataIn.axes()) > 1 or len(dataIn.dependents()) > 1:
        return dict(dataOut=dataIn)

    axname = dataIn.axes()[0]
    x = dataIn.data_vals(axname)
    y = dataIn.data_vals(dataIn.dependents()[0])

    sinemodel = lmfit.Model(sinefunc)
    p0 = sinemodel.make_params(amp=1, freq=self.frequencyGuess, phase=0)
    result = sinemodel.fit(y, p0, x=x)

    dataOut = dataIn.copy()
    if result.success:
        dataOut['fit'] = dict(values=result.best_fit, axes=[axname,])
        dataOut.add_meta('info', result.fit_report())

    return dict(dataOut=dataOut)


def makeNodeList():
    nodes = [
        ('Dimension selector', XYSelector),
        ('Sine fitter', sinefit)
    ]
    return nodes


def main():
    app = QtGui.QApplication([])

    # flowchart and window
    nodes = makeNodeList()
    win, fc = flowchartAutoPlot(nodes)
    win.show()

    # feed in data
    data = makeData()
    fc.setInput(dataIn=data)

    return app.exec_()


if __name__ == '__main__':
    main()
