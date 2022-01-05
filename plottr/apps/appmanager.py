"""This module contains tools for launching plottr apps and managing currently
running apps."""

from typing import List, Tuple, Callable, Optional, Type, Any
from multiprocessing import Process, Pipe
from multiprocessing.connection import Connection
from traceback import print_exception

import numpy as np

from plottr import QtCore, QtWidgets, Flowchart, Signal, Slot
from plottr.gui.widgets import PlotWindow
from plottr.data.datadict import DataDictBase, DataDict
from plottr.apps.autoplot import autoplot


AppType = Callable[[], Tuple[Flowchart, PlotWindow]]


class Listener(QtCore.QObject):
    """Simple object that we can run in a separate thread to listen
    to commands from the manager."""

    #: Signal(str, str, object) -- emitted when a message is received.
    #: Arguments:
    #:  * the target (node name, or '', 'fc', or 'flowchart' for the flowchart)
    #:  * target property (node property name, or 'setInput' or 'getOutput' for the flowchart)
    #:  * property value to set
    messageReceived = Signal(str, str, object)

    #: Signal() -- emitted when listener is stopped.
    listeningStopped = Signal()

    def __init__(self, conn: Connection):
        super().__init__()
        self.conn = conn
        self.listening = True

    @Slot()
    def startListening(self):
        while self.listening:
            if self.conn.poll():
                message: Tuple[str, str, Any] = self.conn.recv()
                targetName, targetProperty, value = message
                self.messageReceived.emit(targetName, targetProperty, value)

    @Slot()
    def stopListening(self):
        self.listening = False
        self.listeningStopped.emit()


class App(QtCore.QObject):

    # TODO: on closing the window, notify the app manager

    def __init__(self, func: AppType, conn: Connection) -> None:
        super().__init__()

        self.fc: Optional[Flowchart] = None
        self.win: Optional[PlotWindow] = None
        self.setup: AppType = func
        self.conn = conn

        self.listenThread = QtCore.QThread(parent=self)
        self.listener = Listener(conn)
        self.listener.moveToThread(self.listenThread)
        self.listener.messageReceived.connect(self.onMessageReceived)
        self.listenThread.started.connect(self.listener.startListening)
        self.listener.listeningStopped.connect(self.listenThread.quit)

    def launch(self) -> None:
        self.fc, self.win = self.setup()
        assert isinstance(self.fc, Flowchart)
        assert isinstance(self.win, PlotWindow)

        self.win.windowClosed.connect(self.quit)

        self.listenThread.start()

    @Slot()
    def quit(self) -> None:
        self.listener.stopListening()
        if not self.listenThread.wait(1000):
            self.listenThread.terminate()
            self.listenThread.wait()
        self.deleteLater()

    @Slot(str, str, object)
    def onMessageReceived(self, targetName, targetProperty, value) -> None:
        if targetName in ['', 'fc', 'flowchart']:
            if  targetProperty == 'setInput':
                self.conn.send(self.fc.setInput(**value))
            elif targetProperty == 'getOutput':
                self.conn.send(self.fc.outputValues())
            else:
                self.conn.send(ValueError(f"Flowchart supports only setting input values ('setInput') "
                                          f"or getting output values ('getOutput'). "
                                          f"'{targetProperty}' is not known."))
        else:
            try:
                node = self.fc.nodes()[targetName]
                self.conn.send(f'pong: {targetName}: {targetProperty} -> {value}')
            except Exception as e:
                self.conn.send(e)


    # @Slot(dict)
    # def setInput(self, data: Dict[str, Optional[DataDictBase]]) -> None:
    #     self.fc.setInput(**data)



# this is the function we use as target for Process
def runApp(func: AppType, conn: Connection):
    qtapp = QtWidgets.QApplication([])
    app = App(func, conn)
    app.launch()
    assert app.win is not None
    app.win.show()
    return qtapp.exec_()


class AppManager(QtCore.QObject):

    # TODO: consider checking on the apps in intervals to see if they're still alive
    #   (with a ping method or so)
    # TODO: add a way to prepend/append stuff? might require some thinking.

    def __init__(self,
                 apps: List[Tuple[str, AppType]],
                 parent: Optional[QtWidgets.QWidget] = None):

        super().__init__(parent)

        self.availableApps = {title: func for title, func in apps}
        self.activeApps = {}

    def launchApp(self, id: Any, appTitle: str):
        conn1, conn2 = Pipe()
        process = Process(
            target=runApp,
            args=(self.availableApps[appTitle], conn2),
        )
        process.start()
        self.activeApps[id] = {
            'appTitle': appTitle,
            'process': process,
            'conn': conn1,
        }

    def message(self, id: Any, targetName: str, targetProperty: str, value: Any) -> Any:
        if id not in self.activeApps:
            raise ValueError(f"no app with ID <{id}> running.")
        self.activeApps.get(id)['conn'].send((targetName, targetProperty, value))
        response = self.activeApps.get(id)['conn'].recv()
        if isinstance(response, Exception):
            print(f'Exception occurred in app <{id}>:')
            print_exception(type(response), response, response.__traceback__)
        return response


# testing methods here
def _make_testdata():
    x, y, z = (np.linspace(-5,5,101) for i in range(3))
    xx, yy, zz = np.meshgrid(x, y, z, indexing='ij')
    vals = np.exp(-yy**2-zz**2) + np.random.normal(loc=0, size=xx.shape)
    return DataDict(
        x=dict(values=xx),
        y=dict(values=yy),
        z=dict(values=zz),
        vals=dict(values=vals, axes=['x', 'y', 'z'])
    )


if __name__ == '__main__':
    qtapp = QtWidgets.QApplication([])
    appman = AppManager([('regular autoplot', autoplot)])

    appman.launchApp(0, 'regular autoplot')
    print(appman.message(0, 'target', 'property', 'value'))

    appman.launchApp(1, 'regular autoplot')
    print(appman.message(1, 'target_1', 'property_1', 'value_1'))

    print(appman.message(0, '', 'setInput', {'dataIn': _make_testdata()}))
    print(appman.message(0, '', 'getOutput', None))

    qtapp.exec_()
