"""
Testing how to make a custom app with gui.
"""
import numpy as np

from plottr import QtGui
from plottr.data.datadict import MeshgridDataDict
from plottr.gui.tools import flowchartAutoPlot
from plottr.node.dim_reducer import XYSelector


def makeData():
    xvals = np.linspace(0, 10, 51)
    reps = np.arange(20)
    xx, rr = np.meshgrid(xvals, reps, indexing='ij')
    data = np.sin(xx)
    noise = np.random.normal(scale=0.5, size=data.shape)
    data += noise

    dd = MeshgridDataDict(
        x=dict(values=xx),
        repetition=dict(values=rr),
        sine=dict(values=data, axes=['x', 'repetition']),
    )

    return dd


def makeNodeList():
    nodes = [
        ('Dimension selector', XYSelector),
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
