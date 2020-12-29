"""
Testing how to make a custom app with gui.
"""
import numpy as np
import lmfit

from plottr import QtGui, QtWidgets
from plottr.data.datadict import DataDictBase, MeshgridDataDict
from plottr.gui.widgets import makeFlowchartWithPlotWindow
from plottr.node.dim_reducer import XYSelector
from plottr.node.fitter_2 import FittingNode, FittingOptions, ParamOptions


def makeData():
    xvals = np.linspace(0, 10, 51)
    reps = np.arange(20)
    xx, rr = np.meshgrid(xvals, reps, indexing='ij')
    data = sinefunc(xx, amp=0.8, freq=0.25, phase=0.1)
    noise = np.random.normal(scale=0.2, size=data.shape)
    data += noise

    amp = ParamOptions(False, 1)
    omega = ParamOptions(False, 2)
    phase = ParamOptions(False, 0)

    parameters = {'amp': amp,
                  'omega': omega,
                  'phase': phase}
    fitting_options = FittingOptions('GenericFunctions.Sinusoidal', parameters)




    dd = MeshgridDataDict(
        x=dict(values=xx),
        repetition=dict(values=rr),
        sine=dict(values=data, axes=['x', 'repetition']),
        __fitting_options__ = fitting_options
    )
    return dd

def sinefunc(x, amp, freq, phase):
    return amp * np.sin(2 * np.pi * (freq * x + phase))




def makeNodeList():
    nodes = [
        ('Dimension selector', XYSelector),
        ('Fitter', FittingNode)
    ]
    return nodes


def main():
    app = QtWidgets.QApplication([])

    # flowchart and window
    nodes = makeNodeList()
    win, fc = makeFlowchartWithPlotWindow(nodes)
    win.show()

    # feed in data
    data = makeData()
    fc.setInput(dataIn=data)

    return app.exec_()


if __name__ == '__main__':
    main()
