"""This module contains tools for launching plottr apps and managing currently
running apps.

An `app` as used in plottr is defined as a function that returns a
:class:`plottr.node.node.Flowchart` and :class:`plottr.gui.widgets.PlotWindow`.

An app can be launched in a separate process using :func:`.runApp`. This way
of running the app also provides a way to communicate with the newly launched
process by wrapping it with the :class:`.App` class.

The role of the :class:`.AppManager` is to launch, manage, and communicate with
app processes.
"""

from typing import List, Tuple, Callable, Optional, Any, Union, Dict
from multiprocessing import Process, Pipe
from multiprocessing.connection import Connection
from traceback import print_exception

import psutil

from plottr import QtCore, QtWidgets, Flowchart, Signal, Slot, log, qtapp, qtsleep
from plottr.gui.widgets import PlotWindow


#: The type of a plottr app
AppType = Callable[[], Tuple[Flowchart, PlotWindow]]


logger = log.getLogger(__name__)


class Listener(QtCore.QObject):
    """Simple helper object that we can run in a separate thread to listen
    to commands from the manager."""

    #: Signal(str, str, object) -- emitted when a message is received.
    #: Arguments:
    #:  * the target (node name, or '', 'fc', or 'flowchart' for the flowchart)
    #:  * target property (node property name, or 'setInput' or 'getOutput' for the flowchart)
    #:  * property value to set
    messageReceived = Signal(str, str, object)

    #: Signal() -- emitted when listener is stopped.
    listeningStopped = Signal()

    def __init__(self, conn: Connection) -> None:
        """Constructor for :class:`.Listener`.

        :param conn: connection on which messages are received (we're using the
            Pipe communication model from python's multiprocessing)
        """
        super().__init__()
        self.conn = conn
        self.listening = True

    @Slot()
    def startListening(self) -> None:
        """start listening on the connection provided."""
        while self.listening:
            if self.conn.poll():
                message: Tuple[str, str, Any] = self.conn.recv()
                targetName, targetProperty, value = message
                self.messageReceived.emit(targetName, targetProperty, value)
            qtsleep(0.05)

    @Slot()
    def stopListening(self) -> None:
        self.listening = False
        self.listeningStopped.emit()


class App(QtCore.QObject):
    """Object that effectively wraps a plottr app.
    Runs a :class:`.Listener` in a separate thread, which allows sending messages
    from the parent :class:`.AppManager` to the app.
    """

    def __init__(self, func: AppType, conn: Connection) -> None:
        """Constructor for :class:`.App`.

        :param func: function that creates the app.
        :param conn: connection (Pipe end) that the app will receive messages
            with.
        """
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
        """Launch the app and the thread that receives messages for the app."""
        self.fc, self.win = self.setup()
        assert isinstance(self.fc, Flowchart)
        assert isinstance(self.win, PlotWindow)

        self.win.windowClosed.connect(self.quit)
        self.listenThread.start()

    @Slot()
    def quit(self) -> None:
        """Terminates the messaging thread and initiates deleting this object."""
        self.listener.stopListening()
        if not self.listenThread.wait(1000):
            self.listenThread.terminate()
            self.listenThread.wait()
        self.deleteLater()

    @Slot(str, str, object)
    def onMessageReceived(self,
                          targetName: str,
                          targetProperty: str,
                          value: Any) -> None:
        """Handles message reception and forwarding to the app.

        :param targetName: name of the target object in the app.
            This may be the app :class:`plottr.node.node.Flowchart`
            (on names ```` (empty string), ``fc``, or ``flowchart``;
            or any :class:`plottr.node.node.Node` in the flowchart
            (on name of the node in the app flowchart).

        :param targetProperty:

            * if the target is a node, then this should be the name of a property
              of the node.

            * if the target is the flowchart, then ``setInput`` or ``getInput`` are
              supported as target properties.

        :param value: a valid value that the target property can be set to.
            for the ``setInput`` option of the flowchart, this should be data, i.e.,
            a dictionary with ``str`` keys and  :class:`plottr.data.datadict.DataDictBase`
            values. Commonly ``{'dataIn': someData}`` for most flowcharts.
            for the ``setInput`` option of the flowchart, this may be any object
            and will be ignored.
        """
        assert self.fc is not None and self.win is not None

        if targetName in ['', 'fc', 'flowchart']:
            if targetProperty == 'setInput':
                self.conn.send(self.fc.setInput(**value))
            elif targetProperty == 'getOutput':
                self.conn.send(self.fc.outputValues())
            else:
                self.conn.send(ValueError(f"Flowchart supports only setting input values ('setInput') "
                                          f"or getting output values ('getOutput'). "
                                          f"'{targetProperty}' is not known."))
        else:
            ret: Union[bool, Exception]
            try:
                node = self.fc.nodes()[targetName]
                setattr(node, targetProperty, value)
                ret = True
            except Exception as e:
                ret = e
            self.conn.send(ret)


# this is the function we use as target for Process
def runApp(func: AppType, conn: Connection) -> int:
    """Run an app in a separate process."""
    application = qtapp()
    app = App(func, conn)
    app.launch()
    assert app.win is not None
    app.win.show()
    return application.exec_()


class AppManager(QtWidgets.QWidget):
    """A widget that launches, manages, and communicates with app instances
    that run in separate processes."""

    #: Signal(object, str) -- emitted when an app was launched.
    #: Arguments:
    #:  * the app instance id
    #:  * name of the app
    appLaunched = Signal(object, str)

    #: Signal(object) -- emitted when an app has been detected as closed
    #: Arguments:
    #:  * the app instance id
    appClosed = Signal(object)

    def __init__(self,
                 apps: List[Tuple[str, AppType]],
                 parent: Optional[QtWidgets.QWidget] = None) -> None:
        """Constructor.

        :param apps: available apps that can be launched; a list of tuples
            of app titles (names) and app-returning functions
        :param parent: parent widget.
        """

        super().__init__(parent)

        self.availableApps = {title: func for title, func in apps}
        self.activeApps: Dict[Any, Dict[str, Any]] = {}
        self.appClosed.connect(self._onAppClosed)

    def launchApp(self, id: Any, appTitle: str) -> None:
        """Lauch a new app instance.

        :param id: unique ID for the instance.
        :param appTitle: which app to run (title must mach one of the available
            apps with which the instance was created).
        """
        conn1, conn2 = Pipe()
        process = Process(
            target=runApp,
            args=(self.availableApps[appTitle], conn2),
        )
        process.start()
        while not process.is_alive():
            qtsleep(0.001)

        monitor = QtCore.QTimer(self)
        monitor.timeout.connect(lambda: self.checkIfAppIsAlive(id))
        monitor.start(1000)

        self.activeApps[id] = {
            'appTitle': appTitle,
            'process': process,
            'conn': conn1,
            'monitor': monitor,
        }
        self.appLaunched.emit(id, appTitle)

    def message(self, id: Any, targetName: str, targetProperty: str, value: Any) -> Any:
        """Send a message to an app instance.

        :param id: ID of the app instance.

        :param targetName: name of the target object in the app.
            This may be the app :class:`plottr.node.node.Flowchart`
            (on names ```` (empty string), ``fc``, or ``flowchart``;
            or any :class:`plottr.node.node.Node` in the flowchart
            (on name of the node in the app flowchart).

        :param targetProperty:

            * if the target is a node, then this should be the name of a property
              of the node.

            * if the target is the flowchart, then ``setInput`` or ``getInput`` are
              supported as target properties.

        :param value: a valid value that the target property can be set to.
            for the ``setInput`` option of the flowchart, this should be data, i.e.,
            a dictionary with ``str`` keys and  :class:`plottr.data.datadict.DataDictBase`
            values. Commonly ``{'dataIn': someData}`` for most flowcharts.
            for the ``setInput`` option of the flowchart, this may be any object
            and will be ignored.

        :returns: the response to the message. Can be:

            *  an exception if the message resulted in an exception being raised.

            * ``True`` if a property was set successfully

            * data, if flowchart data was requested.

            * ``None``, otherwise.
        """
        if id not in self.activeApps:
            raise ValueError(f"no app with ID <{id}> running.")
        else:
            app = self.activeApps[id]
            app['conn'].send((targetName, targetProperty, value))
            response = app['conn'].recv()

        if isinstance(response, Exception):
            logger.warning(f'Exception occurred in app <{id}>:')
            print_exception(type(response), response, response.__traceback__)

        return response

    def checkIfAppIsAlive(self, id: Any) -> bool:
        """Check if the process of the app instance with ID ``id`` is still alive."""

        pid = self.activeApps[id]['process'].pid
        if not psutil.pid_exists(pid):
            running = False
        else:
            proc = psutil.Process(pid)
            running = proc.status() not in [psutil.STATUS_DEAD, psutil.STATUS_STOPPED, psutil.STATUS_ZOMBIE]
        if not running:
            self.appClosed.emit(id)
        return running

    def _onAppClosed(self, id: Any) -> None:
        if id in self.activeApps:
            self.activeApps[id]['monitor'].stop()
            del self.activeApps[id]
