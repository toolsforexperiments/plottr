from logging import getLogger
from pathlib import Path
from typing import Union

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

    def __init__(self, closed_signal: Signal,
                 deleted_signal: Signal,
                 moved_signal: Signal,
                 created_signal: Signal,
                 modified_signal: Signal):
        super().__init__()
        self.closed_signal = closed_signal
        self.deleted_signal = deleted_signal
        self.moved_signal = moved_signal
        self.created_signal = created_signal
        self.modified_signal = modified_signal

    def on_closed(self, event: FileSystemEvent) -> None:
        self.closed_signal.emit(event)  # type: ignore[attr-defined]

    def on_deleted(self, event: FileSystemEvent) -> None:
        self.deleted_signal.emit(event)  # type: ignore[attr-defined]

    def on_moved(self, event: FileSystemEvent) -> None:
        self.moved_signal.emit(event)  # type: ignore[attr-defined]

    def on_created(self, event: FileSystemEvent) -> None:
        self.created_signal.emit(event)  # type: ignore[attr-defined]

    def on_modified(self, event: FileSystemEvent) -> None:
        self.modified_signal.emit(event)  # type: ignore[attr-defined]


class WatcherClient(QtCore.QObject):
    """
    QObject running on a separate thread. Contains the watchdog handler that is triggers the file events. Its main
    purpose is to connect the watchdog functionality with a Qt app. Contains all the signals that are emitted by the
    QtHandler.
    """
    # Signal(FileSystemEvent) -- Emitted when a file is closed.
    #: Arguments:
    #:   - The FileSystemEvent with the information for the closed directory event.
    closed = Signal(FileSystemEvent)

    # Signal(FileSystemEvent) -- Emitted when a file is deleted.
    #: Arguments:
    #:   - The FileSystemEvent with the information for the deleted directory event.
    deleted = Signal(FileSystemEvent)

    # Signal(FileSystemEvent) -- Emitted when a file is moved.
    #: Arguments:
    #:   - The FileSystemEvent with the information for the moved directory event.
    moved = Signal(FileSystemEvent)

    # Signal(FileSystemEvent) -- Emitted when a file is created.
    #: Arguments:
    #:   - The FileSystemEvent with the information for the created directory event.
    created = Signal(FileSystemEvent)

    # Signal(FileSystemEvent) -- Emitted when a file is modified.
    #: Arguments:
    #:   - The FileSystemEvent with the information for the modified directory event.
    modified = Signal(FileSystemEvent)

    def __init__(self, directory: Path):
        super().__init__()
        self.directory = directory
        self.observer = Observer()
        self.handler = QtHandler(closed_signal=self.closed,  # type: ignore[arg-type]
                                 deleted_signal=self.deleted,  # type: ignore[arg-type]
                                 moved_signal=self.moved,  # type: ignore[arg-type]
                                 created_signal=self.created,  # type: ignore[arg-type]
                                 modified_signal=self.modified)  # type: ignore[arg-type]

    def run(self) -> None:
        logger.info('starting the watcher')
        self.observer.schedule(self.handler, self.directory, recursive=True)
        self.observer.start()
        try:
            while self.observer.is_alive():
                self.observer.join(1)
        finally:
            self.observer.stop()
            self.observer.join()

