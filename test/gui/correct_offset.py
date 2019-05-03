import numpy as np

from plottr import QtGui
from plottr.data.datadict import MeshgridDataDict
from plottr.gui.tools import flowchartAutoPlot
from plottr.node.filter.correct_offset import SubtractAverage


def subtractAverage():
    x = np.arange(11) - 5.
    y = np.linspace(0, 10, 51)
    xx, yy = np.meshgrid(x, y, indexing='ij')
    zz = np.sin(yy) + xx
    data = MeshgridDataDict(
        x=dict(values=xx),
        y=dict(values=yy),
        z=dict(values=zz, axes=['x', 'y'])
    )
    data.validate()

    x = np.arange(11) - 5.
    y = np.linspace(0, 10, 51)
    xx, yy = np.meshgrid(x, y, indexing='ij')
    zz = np.sin(yy) + xx
    data2 = MeshgridDataDict(
        reps=dict(values=xx),
        y=dict(values=yy),
        z=dict(values=zz, axes=['reps', 'y'])
    )
    data2.validate()

    # make app and gui, fc
    app = QtGui.QApplication([])
    win, fc = flowchartAutoPlot([
        ('sub', SubtractAverage)
    ])
    win.show()

    # feed in data
    fc.setInput(dataIn=data)
    fc.setInput(dataIn=data2)

    return app.exec_()


if __name__ == '__main__':
    subtractAverage()
