from pyqtgraph.flowchart import Flowchart
from pyqtgraph.Qt import QtGui, QtCore
from pyqtgraph.flowchart import library as fclib
from pyqtgraph.Qt import QtGui, QtCore
from pyqtgraph.dockarea import Dock, DockArea

from plottr import log as plottrlog


def make_sequential_flowchart(clsList, inputData=None):
    nNodes = len(clsList)

    nodelib = fclib.NodeLibrary()
    for cls in clsList:
        cls.debug = True
        nodelib.addNodeType(cls, [('Basic')])

    fc = Flowchart(terminals={
        'dataIn': {'io': 'in'},
        'dataOut': {'io': 'out'}
    })
    fc.library = nodelib

    nodes = []
    for cls in clsList:
        nodes.append(fc.createNode(cls.nodeName))

    fc.connectTerminals(fc['dataIn'], nodes[0]['dataIn'])
    for i in range(nNodes-1):
        fc.connectTerminals(nodes[i]['dataOut'], nodes[i+1]['dataIn'])
    fc.connectTerminals(nodes[nNodes-1]['dataOut'], fc['dataOut'])

    if inputData is not None:
        fc.setInput(dataIn=inputData)

    return nodes, fc


def make_sequential_flowchart_with_gui(clsList, inputData=None, log=True):
    nodes, fc = make_sequential_flowchart(clsList, inputData=inputData)

    win = QtGui.QMainWindow()
    area = DockArea()
    win.setCentralWidget(area)

    for node in nodes:
        if node.useUi and node.uiClass is not None:
            nodeDock = Dock(node.name())
            nodeDock.addWidget(node.ui)
            area.addDock(nodeDock)

    if log:
        logDock = Dock('Log')
        logDock.addWidget(plottrlog.setupLogging(makeDialog=False))
        area.addDock(logDock, 'bottom')

    win.show()

    return nodes, fc, win
