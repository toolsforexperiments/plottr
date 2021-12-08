"""
plottr/apps/autoplot.py : tools for simple automatic plotting.
"""

import logging
import os
import time
import argparse
from typing import Union, Tuple, Optional, Type, List, Any, Type
from packaging import version

from .. import QtCore, Flowchart, Signal, Slot, QtWidgets, QtGui
from .. import log as plottrlog
from ..data.datadict import DataDictBase
from ..data.datadict_storage import DDH5Loader
from ..data.qcodes_dataset import QCodesDSLoader
from ..gui import PlotWindow
from ..gui.widgets import MonitorIntervalInput, SnapshotWidget
from ..node.data_selector import DataSelector
from ..node.dim_reducer import XYSelector
from ..node.filter.correct_offset import SubtractAverage
from ..node.scaleunits import ScaleUnits
from ..node.grid import DataGridder, GridOption
from ..node.tools import linearFlowchart
from ..node.node import Node
from ..node.histogram import Histogrammer
from ..plot import PlotNode, makeFlowchartWithPlot, PlotWidget
from ..plot.pyqtgraph.autoplot import AutoPlot as PGAutoPlot
from ..utils.misc import unwrap_optional

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


# TODO: * separate logging window


def logger() -> logging.Logger:
    logger = logging.getLogger('plottr.apps.autoplot')
    logger.setLevel(plottrlog.LEVEL)
    return logger


def autoplot(inputData: Union[None, DataDictBase] = None,
             plotWidgetClass: Optional[Type[PlotWidget]] = None) \
        -> Tuple[Flowchart, 'AutoPlotMainWindow']:
    """
    Sets up a simple flowchart consisting of a data selector, gridder,
    an xy-axes selector, and creates a GUI together with an autoplot
    widget.

    :returns: the flowchart object and the dialog widget
    """

    nodes: List[Tuple[str, Type[Node]]] = [
        ('Data selection', DataSelector),
        ('Grid', DataGridder),
        ('Dimension assignment', XYSelector),
    ]

    widgetOptions = {
        "Data selection": dict(visible=True,
                               dockArea=QtCore.Qt.TopDockWidgetArea),
        "Dimension assignment": dict(visible=True,
                                     dockArea=QtCore.Qt.TopDockWidgetArea),
    }

    fc = makeFlowchartWithPlot(nodes)
    win = AutoPlotMainWindow(fc, widgetOptions=widgetOptions,
                             plotWidgetClass=plotWidgetClass)
    win.show()

    if inputData is not None:
        win.setInput(data=inputData)

    return fc, win


class UpdateToolBar(QtWidgets.QToolBar):
    """
    A very simple toolbar to enable monitoring or triggering based on a timer.
    Contains a timer whose interval can be set.
    The toolbar will then emit a signal each interval.
    """

    #: Signal emitted after each trigger interval
    trigger = Signal()

    def __init__(self, name: str, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(name, parent)

        self.monitorInput = MonitorIntervalInput()
        self.monitorInput.setToolTip('Set to 0 for disabling triggering')
        self.monitorInput.intervalChanged.connect(self.setMonitorInterval)
        self.addWidget(self.monitorInput)

        self.monitor = QtCore.QTimer()
        self.monitor.timeout.connect(self.monitorTriggered)

    @Slot()
    def monitorTriggered(self) -> None:
        """
        Is called whenever the monitor timer triggers, and emit the
        :attr:`trigger` Signal.
        """
        logger().debug('Emit trigger')
        self.trigger.emit()

    @Slot(float)
    def setMonitorInterval(self, val: float) -> None:
        """
        Start a background timer that is triggered every `val' seconds.

        :param val: trigger interval in seconds
        """
        self.monitor.stop()
        if val > 0:
            self.monitor.start(int(val * 1000))

        self.monitorInput.spin.setValue(val)

    @Slot()
    def stop(self) -> None:
        """
        Stop the timer.
        """
        self.monitor.stop()


class AutoPlotMainWindow(PlotWindow):

    def __init__(self, fc: Flowchart,
                 parent: Optional[QtWidgets.QMainWindow] = None,
                 monitor: bool = False,
                 monitorInterval: Union[float, None] = None,
                 loaderName: Optional[str] = None,
                 plotWidgetClass: Optional[Type[PlotWidget]] = None,
                 **kwargs: Any):

        super().__init__(parent, fc=fc, plotWidgetClass=plotWidgetClass,
                         **kwargs)

        self.fc = fc
        self.loaderNode: Optional[Node] = None
        if loaderName is not None:
            self.loaderNode = fc.nodes()[loaderName]

        # a flag we use to set reasonable defaults when the first data
        # is processed
        self._initialized = False

        windowTitle = "Plottr | Autoplot"
        self.setWindowTitle(windowTitle)

        # status bar
        self.status = QtWidgets.QStatusBar()
        self.setStatusBar(self.status)

        # menu bar
        self.menu = self.menuBar()
        self.fileMenu = self.menu.addMenu('&Data')

        if self.loaderNode is not None:
            refreshAction = QtWidgets.QAction('&Refresh', self)
            refreshAction.setShortcut('R')
            refreshAction.triggered.connect(self.refreshData)
            self.fileMenu.addAction(refreshAction)

        # add monitor if needed
        if monitor:
            self.monitorToolBar: Optional[UpdateToolBar] = UpdateToolBar('Monitor data')
            self.addToolBar(self.monitorToolBar)
            self.monitorToolBar.trigger.connect(self.refreshData)
            if monitorInterval is not None:
                self.setMonitorInterval(monitorInterval)
        else:
            self.monitorToolBar = None

        # set some sane defaults any time the data is significantly altered.
        if self.loaderNode is not None:
            self.loaderNode.dataFieldsChanged.connect(self.onChangedLoaderData)

    def setMonitorInterval(self, val: float) -> None:
        if self.monitorToolBar is not None:
            self.monitorToolBar.setMonitorInterval(val)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """
        When closing the inspectr window, do some house keeping:
        * stop the monitor, if running
        """
        if self.monitorToolBar is not None:
            self.monitorToolBar.stop()
        return super().closeEvent(event)

    def showTime(self) -> None:
        """
        Displays current time and DS info in the status bar.
        """
        tstamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.status.showMessage(f"loaded: {tstamp}")

    @Slot()
    def onChangedLoaderData(self) -> None:
        assert self.loaderNode is not None
        data = self.loaderNode.outputValues()['dataOut']
        if data is not None:
            self.setDefaults(self.loaderNode.outputValues()['dataOut'])

    @Slot()
    def refreshData(self) -> None:
        """
        Refresh the dataset by calling `update' on the dataset loader node.
        """
        if self.loaderNode is not None:

            self.loaderNode.update()
            self.showTime()

            if not self._initialized and self.loaderNode.nLoadedRecords > 0:
                self.onChangedLoaderData()
                self._initialized = True

    def setInput(self, data: DataDictBase, resetDefaults: bool = True) -> None:
        """
        Set input to the flowchart. Can only be used when no loader node is
        defined.
        """
        if self.loaderNode is not None:
            logger().warning("A loader node is defined. Use that for inserting data.")
        else:
            self.fc.setInput(dataIn=data)
            if resetDefaults or not self._initialized:
                self.setDefaults(data)
                self._initialized = True

    def setDefaults(self, data: DataDictBase) -> None:
        """
        try to set some reasonable defaults so there's a plot right away.
        """
        selected = data.dependents()
        if len(selected) > 0:
            selected = selected[:1]

        axes = data.axes(selected)
        drs = dict()
        if len(axes) >= 2:
            drs = {axes[-1]: 'x-axis', axes[-2]: 'y-axis'}
        if len(axes) == 1:
            drs = {axes[0]: 'x-axis'}

        try:
            self.fc.nodes()['Data selection'].selectedData = selected
            self.fc.nodes()['Grid'].grid = GridOption.guessShape, {}
            self.fc.nodes()['Dimension assignment'].dimensionRoles = drs
        # FIXME: this is maybe a bit excessive, but trying to set all the defaults
        #   like this can result in many types of errors.
        #   a better approach would be to inspect the data better and make sure
        #   we can set defaults reliably.
        except:
            pass
        unwrap_optional(self.plotWidget).update()


class QCAutoPlotMainWindow(AutoPlotMainWindow):
    """
    Main Window for autoplotting a qcodes dataset.

    Comes with menu options for refreshing the loaded dataset,
    and a toolbar for enabling live-monitoring/refreshing the loaded
    dataset.
    """

    def __init__(self, fc: Flowchart,
                 parent: Optional[QtWidgets.QMainWindow] = None,
                 pathAndId: Optional[Tuple[str, int]] = None, **kw: Any):

        super().__init__(fc, parent, **kw)

        windowTitle = "Plottr | QCoDeS autoplot"
        if pathAndId is not None:
            path = os.path.abspath(pathAndId[0])
            windowTitle += f" | {os.path.split(path)[1]} [{pathAndId[1]}]"
            pathAndId = path, pathAndId[1]
        self.setWindowTitle(windowTitle)

        if pathAndId is not None and self.loaderNode is not None:
            self.loaderNode.pathAndId = pathAndId

        if self.loaderNode is not None and self.loaderNode.nLoadedRecords > 0:
            self.setDefaults(self.loaderNode.outputValues()['dataOut'])
            self._initialized = True

    def setDefaults(self, data: DataDictBase) -> None:
        super().setDefaults(data)
        import qcodes as qc
        qcodes_support = (version.parse(qc.__version__) >=
                          version.parse("0.20.0"))
        if data.meta_val('qcodes_shape') is not None and qcodes_support:
            self.fc.nodes()['Grid'].grid = GridOption.metadataShape, {}
        else:
            self.fc.nodes()['Grid'].grid = GridOption.guessShape, {}


def autoplotQcodesDataset(log: bool = False,
                          pathAndId: Union[Tuple[str, int], None] = None) \
        -> Tuple[Flowchart, QCAutoPlotMainWindow]:
    """
    Sets up a simple flowchart consisting of a data selector,
    an xy-axes selector, and creates a GUI together with an autoplot
    widget.

    returns the flowchart object and the mainwindow widget
    """

    fc = linearFlowchart(
        ('Data loader', QCodesDSLoader),
        ('Data selection', DataSelector),
        ('Grid', DataGridder),
        ('Dimension assignment', XYSelector),
        ('Subtract average', SubtractAverage),
        ('Scale units', ScaleUnits),
        ('plot', PlotNode)
    )

    widgetOptions = {
        "Data selection": dict(visible=True,
                               dockArea=QtCore.Qt.TopDockWidgetArea),
        "Dimension assignment": dict(visible=True,
                                     dockArea=QtCore.Qt.TopDockWidgetArea),
    }

    win = QCAutoPlotMainWindow(fc, pathAndId=pathAndId,
                               widgetOptions=widgetOptions,
                               monitor=True,
                               loaderName='Data loader')
    win.show()

    return fc, win


def autoplotDDH5(filepath: str = '', groupname: str = 'data') \
        -> Tuple[Flowchart, AutoPlotMainWindow]:

    fc = linearFlowchart(
        ('Data loader', DDH5Loader),
        ('Data selection', DataSelector),
        ('Grid', DataGridder),
        ('Histogram', Histogrammer),
        ('Dimension assignment', XYSelector),
        ('plot', PlotNode)
    )

    widgetOptions = {
        "Data selection": dict(visible=True,
                               dockArea=QtCore.Qt.TopDockWidgetArea),
        "Histogram": dict(visible=False,
                          dockArea=QtCore.Qt.TopDockWidgetArea),
        "Dimension assignment": dict(visible=True,
                                     dockArea=QtCore.Qt.TopDockWidgetArea),
    }

    win = AutoPlotMainWindow(fc, loaderName='Data loader',
                             widgetOptions=widgetOptions,
                             monitor=True,
                             monitorInterval=5.0)
    win.show()

    fc.nodes()['Data loader'].filepath = filepath
    fc.nodes()['Data loader'].groupname = groupname
    win.refreshData()
    win.setMonitorInterval(5.0)

    return fc, win


def main(f: str, g: str) -> int:
    app = QtWidgets.QApplication([])
    fc, win = autoplotDDH5(f, g)

    return app.exec_()


def script() -> None:
    parser = argparse.ArgumentParser(
        description='plottr autoplot .dd.h5 files.'
    )
    parser.add_argument('--filepath', help='path to .dd.h5 file',
                        default='')
    parser.add_argument('--groupname', help='group in the hdf5 file',
                        default='data')
    args = parser.parse_args()

    main(args.filepath, args.groupname)
