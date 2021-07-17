"""A simple script to play a bit with pyqtgraph plotting.
This has no direct connection to plottr but is just to explore.
"""

import sys

import numpy as np
import pyqtgraph as pg

from plottr import QtWidgets, QtGui, QtCore
from plottr.gui.tools import widgetDialog

pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

def image_test():
    app = QtWidgets.QApplication([])

    # create data
    x = np.linspace(0, 10, 51)
    y = np.linspace(-4, 4, 51)
    xx, yy = np.meshgrid(x, y, indexing='ij')
    zz = np.cos(xx)*np.exp(-(yy-1.)**2)

    # layout widget
    pgWidget = pg.GraphicsLayoutWidget()

    # main plot
    imgPlot = pgWidget.addPlot(title='my image', row=0, col=0)
    img = pg.ImageItem()
    imgPlot.addItem(img)

    # histogram and colorbar
    hist = pg.HistogramLUTItem()
    hist.setImageItem(img)
    pgWidget.addItem(hist)
    hist.gradient.loadPreset('viridis')

    # cut elements
    pgWidget2 = pg.GraphicsLayoutWidget()

    # plots for x and y cuts
    xplot = pgWidget2.addPlot(row=1, col=0)
    yplot = pgWidget2.addPlot(row=0, col=0)

    xplot.addLegend()
    yplot.addLegend()

    # add crosshair to main plot
    vline = pg.InfiniteLine(angle=90, movable=False, pen='r')
    hline = pg.InfiniteLine(angle=0, movable=False, pen='b')
    imgPlot.addItem(vline, ignoreBounds=True)
    imgPlot.addItem(hline, ignoreBounds=True)

    def crossMoved(event):
        pos = event[0].scenePos()
        if imgPlot.sceneBoundingRect().contains(pos):
            origin = imgPlot.vb.mapSceneToView(pos)
            vline.setPos(origin.x())
            hline.setPos(origin.y())
            vidx = np.argmin(np.abs(origin.x()-x))
            hidx = np.argmin(np.abs(origin.y()-y))
            yplot.clear()
            yplot.plot(zz[vidx, :], y, name='vertical cut',
                       pen=pg.mkPen('r', width=2),
                       symbol='o', symbolBrush='r', symbolPen=None)
            xplot.clear()
            xplot.plot(x, zz[:, hidx], name='horizontal cut',
                       pen=pg.mkPen('b', width=2),
                       symbol='o', symbolBrush='b', symbolPen=None)

    proxy = pg.SignalProxy(imgPlot.scene().sigMouseClicked, slot=crossMoved)

    dg = widgetDialog(pgWidget, title='pyqtgraph image test')
    dg2 = widgetDialog(pgWidget2, title='line cuts')

    # setting the data
    img.setImage(zz)
    img.setRect(QtCore.QRectF(0, -4, 10, 8.))
    hist.setLevels(zz.min(), zz.max())

    # formatting
    imgPlot.setLabel('left', "Y", units='T')
    imgPlot.setLabel('bottom', "X", units='A')
    xplot.setLabel('left', 'Z')
    xplot.setLabel('bottom', "X", units='A')
    yplot.setLabel('left', "Y", units='T')
    yplot.setLabel('bottom', "Z")

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtWidgets.QApplication.instance().exec_()

if __name__ == '__main__':
    image_test()