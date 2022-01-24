""" plottr.monitr -- a GUI tool for monitoring data files.
"""
import sys
import os
import argparse
import time
from typing import List, Optional, Dict, Any, Union
from functools import partial
import importlib
from multiprocessing import Process
import logging
from enum import Enum, auto
from pathlib import Path
import re

from watchdog.events import FileSystemEvent

from .. import log as plottrlog
from .. import QtCore, QtWidgets, Signal, Slot, QtGui
from ..data.datadict_storage import all_datadicts_from_hdf5
from ..utils.misc import unwrap_optional

from .ui.Monitr_UI import Ui_MainWindow

from plottr.apps.watchdog_classes import WatcherClient


class Monitr_depreceated(QtWidgets.QMainWindow):
    # TODO: keep a list of app processes and monitor them if alive.

    #: Signal(object) -- emitted when a valid data file is selected.
    #: Arguments:
    #:  - a dictionary containing the datadicts found in the file (as top-level groups)
    dataFileSelected = Signal(object)

    def __init__(self, monitorPath: str = '.',
                 refreshInterval: int = 1,
                 parent: Optional[QtWidgets.QMainWindow] = None):

        super().__init__(parent=parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.plotDialogs: Dict[int, dict] = {}
        self.selectedFile: Optional[str] = None
        self.newFiles: List[str] = []

        self.monitorPath = os.path.abspath(monitorPath)
        self.refreshInterval = refreshInterval
        self.refreshFiles = partial(self.ui.fileList.loadFromPath, self.monitorPath,
                                    emitNew=True)
        self.ui.fileList.loadFromPath(self.monitorPath, emitNew=False)

        self.monitor = QtCore.QTimer()
        self.monitor.timeout.connect(self.refreshFiles)
        self.monitor.timeout.connect(self.plotQueuedFiles)
        self.monitor.start(self.refreshInterval * 1000)

    @Slot(str)
    def processFileSelection(self, filePath: str) -> None:
        self.selectedFile = filePath
        groups = all_datadicts_from_hdf5(filePath, structure_only=True)
        self.dataFileSelected.emit(groups)

    @Slot(list)
    def onNewDataFilesFound(self, files: List[str]) -> None:
        if not self.ui.autoPlotNewAction.isChecked():
            return

        self.newFiles += files

    @Slot()
    def plotQueuedFiles(self) -> None:
        if not self.ui.autoPlotNewAction.isChecked():
            return

        # FIXME: sometimes opening a file will never succeed.
        #   we should make sure that we don't try reloading it over and over.
        removeFiles = []
        for f in self.newFiles:
            try:
                contents = all_datadicts_from_hdf5(f, structure_only=True)
            except OSError:
                contents = {}

            if len(contents) > 0:
                for grp in contents.keys():
                    self.plot(f, grp)
                removeFiles.append(f)

        for f in removeFiles:
            self.newFiles.remove(f)

    @Slot(str)
    def plotSelected(self, group: str) -> None:
        self.plot(unwrap_optional(self.selectedFile), group)

    def plot(self, filePath: str, group: str) -> None:
        plotApp = 'plottr.apps.autoplot.autoplotDDH5'
        process = launchApp(plotApp, filePath, group)
        if process.pid is not None:
            self.plotDialogs[process.pid] = dict(
                process=process,
                path=filePath,
                group=group,
            )


def logger() -> logging.Logger:
    logger = plottrlog.getLogger('plottr.apps.monitr')
    plottrlog.enableStreamHandler(True)
    logger.setLevel(plottrlog.LEVEL)
    return logger


class ContentType(Enum):
    """
    Enum class for the types of files that are of interest in the monitored subdirectories. Contains helper methods to
    sort files and assign colors to each file type.
    """
    data = auto()
    tag = auto()
    json = auto()
    unknown = auto()

    @classmethod
    def sort(cls, file: Union[str, Path] = None):
        """
        Classifies a file type.

        :param file: The file trying to be classified.
            Can be a string representation of the directory or a pathlib.Path.
        """
        if not isinstance(file, str):
            file = str(file)
        extension = file.split(".")[-1]
        if extension == 'ddh5':
            return ContentType.data
        elif extension == 'tag':
            return ContentType.tag
        elif extension == 'json':
            return ContentType.json
        else:
            return ContentType.unknown

    @classmethod
    def sort_color(cls, item=None):
        """
        Returns the Qt color for the specified ContentType
        """
        if item == ContentType.data:
            return QtGui.QBrush(QtGui.QColor('red'))
        if item == ContentType.tag:
            return QtGui.QBrush(QtGui.QColor('blue'))
        if item == ContentType.json:
            return QtGui.QBrush(QtGui.QColor('green'))
        if item == ContentType.unknown:
            return QtGui.QBrush(QtGui.QColor('black'))


class TreeWidgetItem(QtWidgets.QTreeWidgetItem):
    """
    Modified class of QtWidgets.QTreeWidgetItem where the only modification is the addition of the path parameter.

    :param path: The path this QTreeWidgetItem represents.
    """

    def __init__(self, path: Path, *args, **kwargs):
        super(TreeWidgetItem, self).__init__(*args, **kwargs)
        self.path = path


# TODO: Check consistency in the type of argument required for the add, delete, modified methods (if they should accept
#  only Path or also strings.
class FileTree(QtWidgets.QTreeWidget):
    """
    QTreeWidget that displays the relevant files. Addition, deletion and modification of items performed by the use of
    pathlib.Path objects.

    All QTreeWidgetItems are stored in self.main_items_dictionary where the key is the path they represent,
    and the value is the actual TreeWidgetItem.
    """

    def __init__(self, dic, monitor_path, parent=None):
        super().__init__(parent=parent)
        self.main_items_dictionary = {}
        self.monitor_path = monitor_path
        self.setHeaderLabel('Files')
        self.refresh_tree(dic)

    def clear(self):
        """
        Clears the tree, including the main_items_dictionary.
        """
        super().clear()
        self.main_items_dictionary = {}

    @QtCore.Slot(str)
    def filter_items(self, filter_str):
        """
        Filters away any item in the tree that does not match with filter_str. If an item is matched, all parents and
        children of the item are shown.

        :param filter_str: The string to filter the tree.
        """
        # If the string is empty show all items in the tree.
        if filter_str == '':
            for item in self.main_items_dictionary.values():
                item.setHidden(False)
        else:
            try:
                filter_pattern = re.compile(filter_str)
                # Hide all items.
                for item in self.main_items_dictionary.values():
                    item.setHidden(True)
                # list of the items with matching paths.
                matches = [value for key, value in self.main_items_dictionary.items() if
                           filter_pattern.search(str(key.name))]

                # Show all the matches and their parents and children.
                for match in matches:
                    self._show_parent_item(match)
                    children = [match.child(i) for i in range(match.childCount())]
                    for child in children:
                        self._show_child_item(child)
            except re.error as e:
                logger().error(f'Regex matching failed: {e}')

    def _show_child_item(self, item: TreeWidgetItem):
        """
        Recursive function to the item passed and all of its children.

        :param item: The item that we want to show.
        """
        if item.childCount() == 0:
            item.setHidden(False)
        else:
            item.setHidden(False)
            for i in range(item.childCount()):
                self._show_child_item(item.child(i))

    def _show_parent_item(self, item: TreeWidgetItem):
        """
        Recursive function to the item passed and all of its parents.

        :param item: The item that we want to show.
        """
        if item.parent() is None:
            item.setHidden(False)
        else:
            item.setHidden(False)
            self._show_parent_item(item.parent())

    def refresh_tree(self, update: Dict):
        """
        Deletes the entire tree and creates it again from scratch based on update.

        :param update: Dictionary with the same format as the main_dictionary in the Monitr class. The structure looks
            like::
                update = {
                    path_of_folder_1_containing_files : {
                        path_of_file_1: ContentType.sort(path_of_file_1)
                        path_of_file_2: ContentType.sort(path_of_file_2)}
                    path_of_folder_2_containing_files : {
                        path_of_file_1: ContentType.sort(path_of_file_1)
                        path_of_file_2: ContentType.sort(path_of_file_2)}
                }
        """
        start_timer = time.time_ns()
        self.clear()
        for folder_path, files_dict in update.items():
            self.sort_and_add_tree_widget_item(folder_path, files_dict)
        final_timer = time.time_ns() - start_timer
        logger().info(f'generating the tree widget took: {final_timer * 10 ** -9}s')

    def sort_and_add_tree_widget_item(self, file_or_folder_path: Union[Path, str], files_dict: Optional[Dict] = None):
        """
        Adds one or more items into the tree. The items are properly sorted and new items are created if required.

        This method can create individual files or groups of them:
            * To create an individual file, one should pass the path of the file to `file_or_folder_path` and
              nothing else.
            * To create multiple files inside a specific folder, one should pass the path of the folder to
              `file_or_folder_path` and a dictionary with the path of every file as keys, and their respective file type
              as values. The combination of both arguments should follow the same format as the `update` argument in the
              `refresh_tree` method, where the key of the entry should be `file_or_folder_path` and the dictionary
               containing it should be `files_dict`.

        :param file_or_folder_path: `Path` of the file or folder being added to the tree.
            Strings of the path also supported.
        :param files_dict: Optional. If adding a file, `files_dict` should be `None`. If adding a folder, this should
            be a dictionary with the file `Path`.
        """
        # Check that the new file or folder are Paths, if not convert them.
        if isinstance(file_or_folder_path, str):
            file_or_folder_path = Path(file_or_folder_path)
        elif isinstance(file_or_folder_path, Path):
            file_or_folder_path = file_or_folder_path
        else:
            file_or_folder_path = Path(file_or_folder_path)

        # Check if the new item should have a parent item. If the new item should have a parent, but this does
        # not yet exist, create it.
        if file_or_folder_path == self.monitor_path:
            parent_item, parent_path = None, None
        elif file_or_folder_path.parent in self.main_items_dictionary:
            parent_item, parent_path = \
                self.main_items_dictionary[file_or_folder_path.parent], file_or_folder_path.parent
        else:
            self.sort_and_add_tree_widget_item(file_or_folder_path.parent, None)
            parent_item, parent_path = \
                self.main_items_dictionary[file_or_folder_path.parent], file_or_folder_path.parent

        # Create the new TreeWidgetItem.
        tree_widget_item = TreeWidgetItem(file_or_folder_path, [str(file_or_folder_path.name)])

        # Create and add child items if necessary.
        if files_dict is not None:
            for file_key, file_type in files_dict.items():
                child = TreeWidgetItem(file_key, [str(file_key.name)])
                child.setForeground(0, ContentType.sort_color(file_type))
                self.main_items_dictionary[file_key] = child
                tree_widget_item.addChild(child)
        if parent_path is None:
            self.main_items_dictionary[file_or_folder_path] = tree_widget_item
            self.insertTopLevelItem(0, tree_widget_item)
        else:
            self.main_items_dictionary[file_or_folder_path] = tree_widget_item
            tree_widget_item.setForeground(0, ContentType.sort_color(ContentType.sort(file_or_folder_path)))
            parent_item.addChild(tree_widget_item)

    def delete_item(self, path: Path):
        """
        Deletes specified item from the tree.

        If the item has any children, these will also be deleted with the indicated Path.

        :param path: Path of the item that should be deleted.
        """
        if path in self.main_items_dictionary:
            item = self.main_items_dictionary[path]
            children = [item.child(i) for i in range(item.childCount())]
            parent_item = item.parent()

            # delete all the children if this item has any. While deleting a QTreeWidgetItem will delete all of its
            # respective children, they are each individually deleted to make sure the internal main_items_dictionary is
            # updated.
            if len(children) > 0:
                for child in children:
                    self.delete_item(child.path)
            if parent_item is None:
                item_index = self.indexOfTopLevelItem(item)
                self.takeTopLevelItem(item_index)
            else:
                item.parent().removeChild(item)
            del self.main_items_dictionary[path]

    def update_item(self, old_path: Path, new_path: Path, new_color: Optional[ContentType] = None):
        """
        Updates text and color of a TreeWidgetItem when the name (or type) of a file or directory changes.

        :param old_path: The path of the TreeWidgetItem that needs to be updated.
        :param new_path: The new Path of the TreeWidgetItem.
        :param new_color: The updated type of file. Used to change the color of the TreeWidgetItem.
        """
        if old_path in self.main_items_dictionary:
            self.main_items_dictionary[new_path] = self.main_items_dictionary.pop(old_path)
            self.main_items_dictionary[new_path].setText(0, str(new_path.name))
            if new_color is not None:
                self.main_items_dictionary[new_path].setForeground(0, ContentType.sort_color(new_color))


# TODO: look over logger and start utilizing in a similar way like instrument server is being used right now.
# TODO: Test deletion of nested folder situations for large da+-ta files to see if this is fast enough.
class Monitr(QtWidgets.QMainWindow):

    def __init__(self, monitorPath: str = '.',
                 parent: Optional[QtWidgets.QMainWindow] = None):

        super().__init__(parent=parent)

        # Instantiate variables.
        self.main_dictionary = {}
        self.monitor_path = Path(monitorPath)

        # Create GUI elements.

        # layout
        self.vertical_layout = QtWidgets.QVBoxLayout()
        self.horizontal_layout = QtWidgets.QHBoxLayout()
        self.dummy_widget = QtWidgets.QWidget()

        # Buttons
        self.expand_all_button = QtWidgets.QPushButton('Expand all.')
        self.collapse_all_button = QtWidgets.QPushButton('Collapse all')
        self.horizontal_layout.addWidget(self.expand_all_button)
        self.horizontal_layout.addWidget(self.collapse_all_button)

        self.filter_line_edit = QtWidgets.QLineEdit()
        self.filter_line_edit.setPlaceholderText('filter items')
        self.tree = FileTree(self.main_dictionary, self.monitor_path)
        self.vertical_layout.addWidget(self.filter_line_edit)
        self.vertical_layout.addWidget(self.tree)

        self.vertical_layout.addLayout(self.horizontal_layout)

        self.dummy_widget.setLayout(self.vertical_layout)
        self.setCentralWidget(self.dummy_widget)

        # Create the first tree.
        self.refresh_files()

        # Set the watcher.
        self.watcher_thread = QtCore.QThread()
        self.watcher = WatcherClient(self.monitor_path)
        self.watcher.moveToThread(self.watcher_thread)
        self.watcher_thread.started.connect(self.watcher.run)

        # Connect the Signals.
        self.watcher.moved.connect(self.file_moved)
        self.watcher.created.connect(self.file_created)
        self.watcher.deleted.connect(self.file_deleted)
        self.watcher.modified.connect(self.file_modified)
        self.watcher.closed.connect(self.file_closed)

        self.expand_all_button.clicked.connect(self.tree.expandAll)
        self.collapse_all_button.clicked.connect(self.tree.collapseAll)
        self.filter_line_edit.textEdited.connect(self.tree.filter_items)

        self.watcher_thread.start()

        self.tree.show()

    def refresh_files(self):
        """
        Refreshes the main dictionary by reading all the files in the monitor path.
        """
        start_timer = time.time_ns()
        walk_results = [i for i in os.walk(self.monitor_path)]

        # Sorts the results of the walk. Creates a dictionary of all the current files and directories in the
        # monitor_path with the following structure:
        # {Directory_1: {file_1: file_type
        #                file_2: file_type}
        #  Directory_2: {file_1: file_type
        #                file_2: file_type}...}
        self.main_dictionary = {Path(walk_entry[0]): {Path(walk_entry[0]).joinpath(file): ContentType.sort(file)
                                                      for file in walk_entry[2]} for walk_entry in walk_results
                                if 'data.ddh5' in walk_entry[2]}
        final_timer = time.time_ns() - start_timer
        logger().info(f'refreshing files took: {final_timer * 10 ** -9}s')
        self.tree.refresh_tree(self.main_dictionary)

    @QtCore.Slot(FileSystemEvent)
    def file_created(self, event: FileSystemEvent):
        """
        Triggered every time a file or directory is created. Identifies if the new created file is relevant and adds it
        to the main dictionary.
        """
        logger().info(f'file created: {event}')
        path = Path(event.src_path)
        # I am never interested in adding a folder into the tree. only interested in folders if a dataset is in them.
        if path.suffix != '':
            if path.suffix == '.ddh5':
                self._add_new_ddh5_file(path)
            else:
                # Checks that we are interested in the folder containing the new file and that the file is not already
                # in the main_dictionary.
                if path.parent in self.main_dictionary:
                    if path not in self.main_dictionary[path.parent]:
                        self.main_dictionary[path.parent].update({path: ContentType.sort(path.name)})
                        self.tree.sort_and_add_tree_widget_item(path)

    @QtCore.Slot(FileSystemEvent)
    def file_deleted(self, event: FileSystemEvent):
        """
        Triggered every time a file or directory is deleted. Identifies if the deleted file is relevant and deletes it
        and any other non-relevant files.
        """
        logger().info(f'file deleted: {event}')
        path = Path(event.src_path)

        # Check if a folder has been deleted.
        if path.suffix == '':
            if path in self.main_dictionary:
                del self.main_dictionary[path]
                self.tree.delete_item(path)

            else:
                # Checks if the deleted folder contains other folders that do hold datasets, even if the deleted folder
                # does not and delete them too.
                children_folders = [key for key in self.main_dictionary.keys() if key.is_relative_to(path)]
                if len(children_folders) >= 1:
                    for child in children_folders:
                        del self.main_dictionary[child]
                    self.tree.delete_item(path)

        else:
            # Check that the deleted file is of interest.
            if path.parent in self.main_dictionary:
                if path in self.main_dictionary[path.parent]:
                    if path.suffix == '.ddh5':
                        # checking if there is another ddh5 file in that directory:
                        all_ddh5_files_in_folder = [file for file in self.main_dictionary[path.parent].keys() if
                                                    file.suffix == '.ddh5']

                        # If there is more than a single ddh5 file in the folder, delete just the deleted file from the
                        # main dictionary.
                        if len(all_ddh5_files_in_folder) > 1:
                            del self.main_dictionary[path.parent][path]
                            self.tree.delete_item(path)
                        else:
                            self._delete_parent_folder(path)
                    else:
                        del self.main_dictionary[path.parent][path]
                        self.tree.delete_item(path)

    @QtCore.Slot(FileSystemEvent)
    def file_moved(self, event: FileSystemEvent):
        """
        Triggered every time a file or folder is moved, this includes a file or folder changing names.
        Updates both the `main_dictionary` and the file tree.
        """
        logger().info(f'moved: {event}')
        src_path = Path(event.src_path)
        dest_path = Path(event.dest_path)
        if event.is_directory:
            if src_path in self.main_dictionary:
                self.main_dictionary[dest_path] = self.main_dictionary.pop(src_path)
                self.tree.update_item(src_path, dest_path)

        elif src_path.suffix != dest_path.suffix:
            # If a file becomes a ddh5, create a new ddh5 and delete the old entry.
            if src_path.suffix != '.ddh5' and dest_path.suffix == '.ddh5':
                # Checks if the new ddh5 is in an already kept track folder. If so delete the out of data info.
                if src_path.parent in self.main_dictionary:
                    del self.main_dictionary[src_path.parent][src_path]
                    self.tree.delete_item(src_path)

                self._add_new_ddh5_file(dest_path)
            # If a file stops being a ddh5.
            elif src_path.suffix == '.ddh5' and dest_path.suffix != '.ddh5':
                # Check how many ddh5 files in the parent folder.
                ddh5_files = [file for file in self.main_dictionary[src_path.parent].keys() if file.suffix == '.ddh5']
                # If just 1 or less, delete the entire folder.
                if len(ddh5_files) <= 1:
                    self._delete_parent_folder(src_path)
                else:
                    del self.main_dictionary[src_path.parent][src_path]
                    self.main_dictionary[src_path.parent][dest_path] = ContentType.sort(dest_path)
                    self.tree.update_item(src_path, dest_path, self.main_dictionary[src_path.parent][dest_path])
            else:
                # A different non-ddh5 has changed type.
                del self.main_dictionary[src_path.parent][src_path]
                self.main_dictionary[src_path.parent][dest_path] = ContentType.sort(dest_path)
                self.tree.update_item(src_path, dest_path, self.main_dictionary[src_path.parent][dest_path])

        # Checks if a file changed names but not the type of file.
        elif src_path.parent in self.main_dictionary:
            del self.main_dictionary[src_path.parent][src_path]
            self.main_dictionary[src_path.parent][dest_path] = ContentType.sort(dest_path)
            self.tree.update_item(src_path, dest_path)

    def _add_new_ddh5_file(self, path: Path):
        """
        Adds a new ddh5 file to the `main_dictionary` and on the file tree.

        :param path: The path of the new ddh5 file.
        """
        if path.parent in self.main_dictionary:
            parent_dict = self.main_dictionary[path.parent]
            if path not in parent_dict:
                # Goes through the parent folder and checks if there are other files that
                # are not in the main_dictionary.
                new_files = {file: ContentType.sort(file) for file in path.parent.iterdir() if
                             file not in parent_dict and str(file.suffix) != ''}
                parent_dict.update(new_files)
                for file_path in new_files.keys():
                    self.tree.sort_and_add_tree_widget_item(file_path)
        else:
            # Gets all the files in the folder containing the new ddh5 file.
            new_entry = {
                path.parent: {file: ContentType.sort(file) for file in path.parent.iterdir() if str(file.suffix) != ''}}
            self.main_dictionary.update(new_entry)
            for file_path in new_entry[path.parent].keys():
                self.tree.sort_and_add_tree_widget_item(file_path)

    def _delete_parent_folder(self, path: Path):
        """
        Deletes the parent folder of a recently deleted ddh5 file. For nested folders, it makes sure to delete the
        outermost folder that does not contain any other important files or folders.

        :param path: The path of the deleted ddh5.
        """
        index_of_deletion = None
        parent_dict = self.main_dictionary.pop(path.parent)
        # Going through all parent folder to check what parent should be removed from the tree. This happens when the
        # deleted folder has parent folders whose only important child folder is the folder being deleted.
        for index, parent in enumerate(path.parents):
            # Checks what children folders in the current parent.
            contains = [folder for folder in self.main_dictionary.keys() if folder.is_relative_to(parent)]

            # Because the folder being deleted has already been removed from the main_directory,
            # any other item in contains is a separate folder that should not be deleted.
            if len(contains) >= 1:
                # The index of deletion is index - 1 because we want to delete the outermost parent that is not shared
                # with any other folder in the main_dict, meaning the child of the current folder.
                index_of_deletion = index - 1
                # break the loop since the folder that should be deleted from the tree was found.
                break
        if index_of_deletion is None:
            # This should never happen. Logging a warning to indicate that something went wrong.
            logger().warning(f'could not find a parent a parent for: {path}. \n Doing nothing for now.')
        # If index_of_deletion is -1 it means that the parent folder of the deleted child contains other folders
        # of interest, so we only want to delete the files from the tree.
        elif index_of_deletion == -1:
            for file_path in parent_dict:
                self.tree.delete_item(file_path)
        else:
            self.tree.delete_item(path.parents[index_of_deletion])

    @QtCore.Slot(FileSystemEvent)
    def file_modified(self, event):
        """
        Gets called every time a file or folder gets modified.
        """
        pass

    @QtCore.Slot(FileSystemEvent)
    def file_closed(self, event):
        """
        Gets called every time a file is closed
        """
        pass


def script() -> int:
    parser = argparse.ArgumentParser(description='Monitr main application')
    parser.add_argument("path", help="path to monitor for data", default=None)
    parser.add_argument("-r", "--refresh_interval", default=2, type=float,
                        help="interval at which to look for changes in the "
                             "monitored path (in seconds)")
    args = parser.parse_args()

    path = os.path.abspath(args.path)
    if not (os.path.exists(path) and os.path.isdir(path)):
        print('Invalid path.')
        sys.exit()

    app = QtWidgets.QApplication([])
    win = Monitr(path)
    win.show()
    return app.exec_()


def launchApp(appPath: str, filepath: str, group: str, **kwargs: Any) -> Process:
    p = Process(target=_runAppStandalone,
                args=(appPath, filepath, group),
                kwargs=kwargs)
    p.start()
    p.join(timeout=0)
    return p


def _runAppStandalone(appPath: str, filepath: str, group: str, **kwargs: Any) -> Any:
    sep = appPath.split('.')
    modName = '.'.join(sep[:-1])
    funName = sep[-1]
    mod = importlib.import_module(modName)
    fun = getattr(mod, funName)

    app = QtWidgets.QApplication([])
    fc, win = fun(filepath, group, **kwargs)
    win.show()
    return app.exec_()
