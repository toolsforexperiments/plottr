from logging import getLogger

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from plottr import QtCore, Signal


logger = getLogger(__name__)


class QtHandler(FileSystemEventHandler):
    """
    Watchdog handler that emits the QtCore.Signal when the watchdog FileSystemEvent is triggered.

    :param closed_signal: The signal that will be emitted when the watchdog FileSystemEvent for a closed
        file is emitted.
    :param deleted_signal: The signal that will be emitted when the watchdog FileSystemEvent for a deleted
        file is emitted.
    :param moved_signal: The signal that will be emitted when the watchdog FileSystemEvent for a moved
        file is emitted.
    :param created_signal: The signal that will be emitted when the watchdog FileSystemEvent for a created
        file is emitted.
    :param modified_signal: The signal that will be emitted when the watchdog FileSystemEvent for a modified
        file is emitted.

    """

    def __init__(self, closed_signal, deleted_signal, moved_signal, created_signal, modified_signal):
        super().__init__()
        self.closed_signal = closed_signal
        self.deleted_signal = deleted_signal
        self.moved_signal = moved_signal
        self.created_signal = created_signal
        self.modified_signal = modified_signal

    def on_closed(self, event):
        self.closed_signal.emit(event)

    def on_deleted(self, event):
        self.deleted_signal.emit(event)

    def on_moved(self, event):
        self.moved_signal.emit(event)

    def on_created(self, event):
        self.created_signal.emit(event)

    def on_modified(self, event):
        self.modified_signal.emit(event)


class WatcherClient(QtCore.QObject):
    """
    QObject running on a separate thread. Contains the watchdog handler that is triggers the file events. Its main
    purpose is to connect the watchdog functionality with a Qt app. Contains all the signals that are emitted by the
    QtHandler.
    """
    # Signal(FileSystemEvent) -- Emitted when a file is closed.
    closed = Signal(FileSystemEvent)

    # Signal(FileSystemEvent) -- Emitted when a file is deleted.
    deleted = Signal(FileSystemEvent)

    # Signal(FileSystemEvent) -- Emitted when a file is moved.
    moved = Signal(FileSystemEvent)

    # Signal(FileSystemEvent) -- Emitted when a file is created.
    created = Signal(FileSystemEvent)

    # Signal(FileSystemEvent) -- Emitted when a file is modified.
    modified = Signal(FileSystemEvent)

    def __init__(self, directory):
        super().__init__()
        self.directory = directory
        self.observer = Observer()
        self.handler = QtHandler(closed_signal=self.closed,
                                 deleted_signal=self.deleted,
                                 moved_signal=self.moved,
                                 created_signal=self.created,
                                 modified_signal=self.modified)

    def run(self):
        logger.info('starting the watcher')
        self.observer.schedule(self.handler, self.directory, recursive=True)
        self.observer.start()
        try:
            while self.observer.is_alive():
                self.observer.join(1)
        finally:
            self.observer.stop()
            self.observer.join()

