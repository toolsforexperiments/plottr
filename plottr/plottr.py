import sys
import numpy as np

import pyqtgraph as pg
from pyqtgraph.metaarray import MetaArray
from pyqtgraph.Qt import QtCore, QtGui


def get_test_data():
    x = np.linspace(0, np.pi*2, 37)
    y = np.linspace(-3, 3, 31)
    p = np.array([1, 2])
    xx, yy, pp = np.meshgrid(x, y, p, indexing='ij')
    zz = (np.cos(xx) * np.exp(-yy**2/2.)) ** pp
    data = MetaArray(zz, info=[
        {'name' : 'cosine axis', 'values' : x},
        {'name' : 'gaussian axis', 'values' : y},
        {'name' : 'power', 'cols' : [
            {'name' : 'linear'},
            {'name' : 'quadratic'},
        ]},
        {'name' : 'some really silly data'},
    ])
    return data


class DataInfo(pg.TreeWidget):
    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)
        
        self.setColumnCount(3)
        self.setHeaderLabels(['data', 'shape', 'dtype'])


    def validateData(self, data):
        pass
    
    def addData(self, data):
        naxes = len(data.shape)
        shp = str(data.shape)
        name = data.axisName(naxes)
        if name == naxes:
            name = '<data>'
        dt = str(data.dtype)

        head = QtGui.QTreeWidgetItem([name, shp, dt])
        self.addTopLevelItem(head)

        n = len(data.shape)
        for i in range(n):
            name = data.axisName(i)
            shp = str(data.shape[i])
            if data.axisHasValues(i):
                dt = str(data.axisValues(i).dtype)
            elif data.axisHasColumns(i):
                dt = '<columns>'
            else:
                dt = '<index>'

            axis = QtGui.QTreeWidgetItem([name, shp, dt])
            head.addChild(axis)

            if data.axisHasColumns(i):
                nc = data.shape[i]
                for j in range(nc):
                    name = data.columnName(i, j)
                    col = QtGui.QTreeWidgetItem([name, '', ''])
                    axis.addChild(col)


def main():
    app = QtGui.QApplication([])
    w = DataInfo()
    w.show()
    w.setWindowTitle('Data inspector')

    data = get_test_data()
    w.addData(data)

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()


if __name__ == '__main__':
    main()
    
