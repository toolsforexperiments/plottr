""" plottr.monitr -- a GUI tool for monitoring data files.
"""
import sys
import os
import argparse
import time
import importlib

# Uncomment the next 2 lines if the app sudenly crash with no error.
# import cgitb
# cgitb.enable(format = 'text')

import logging
import re
import pprint
import json
from enum import Enum, auto
from pathlib import Path
from multiprocessing import Process
from typing import List, Optional, Dict, Any, Union, Generator, Iterable, Tuple, Sequence
from functools import partial
from itertools import cycle

from watchdog.events import FileSystemEvent

from .. import log as plottrlog
from .. import QtCore, QtWidgets, Signal, Slot, QtGui
from ..data.datadict_storage import all_datadicts_from_hdf5, datadict_from_hdf5
from ..data.datadict import DataDict
from ..utils.misc import unwrap_optional
from ..apps.watchdog_classes import WatcherClient
from ..gui.widgets import Collapsible
from .json_veiwer import JsonModel, JsonTreeView
from ..icons import get_starIcon as get_star_icon, get_trashIcon as get_trash_icon

from .ui.Monitr_UI import Ui_MainWindow

TIMESTRFORMAT = "%Y-%m-%dT%H%M%S"

def logger() -> logging.Logger:
    logger = plottrlog.getLogger('plottr.apps.monitr')
    plottrlog.enableStreamHandler(True)
    logger.setLevel(plottrlog.LEVEL)
    return logger


def html_color_generator() -> Generator[str, None, None]:
    """
    Generator that cycles through string colors for use in html code.
    """
    colors = ['red', 'blue', 'green', 'purple', 'orange', 'brown', 'magenta']
    for color in cycle(colors):
        yield color


class ContentType(Enum):
    """
    Enum class for the types of files that are of interest in the monitored subdirectories. Contains helper methods to
    sort files and assign colors to each file type.
    """
    data = auto()
    tag = auto()
    json = auto()
    md = auto()
    image = auto()
    unknown = auto()

    @classmethod
    def sort(cls, file: Optional[Union[str, Path]] = None) -> "ContentType":
        """
        Classifies a file type.

        :param file: The file trying to be classified.
            Can be a string representation of the directory or a pathlib.Path.
        """
        if not isinstance(file, str):
            file = str(file)
        extension = file.split(".")[-1].lower()
        if extension == 'ddh5':
            return ContentType.data
        elif extension == 'tag':
            return ContentType.tag
        elif extension == 'json':
            return ContentType.json
        elif extension == 'md':
            return ContentType.md
        elif extension == 'jpg' or extension == 'jpeg' or extension == 'png' or extension == 'image':
            return ContentType.image
        else:
            return ContentType.unknown

    @classmethod
    def sort_Qcolor(cls, item: Optional["ContentType"] = None) -> QtGui.QBrush:
        """
        Returns the Qt color for the specified ContentType
        """
        if item == ContentType.data:
            return QtGui.QBrush(QtGui.QColor('red'))
        if item == ContentType.tag:
            return QtGui.QBrush(QtGui.QColor('blue'))
        if item == ContentType.json:
            return QtGui.QBrush(QtGui.QColor('green'))

        return QtGui.QBrush(QtGui.QColor('black'))


class SupportedDataTypes:

    valid_types = ['.ddh5', '.md', '.json']

    @classmethod
    def check_valid_data(cls, file_names: Sequence[Union[str, Path]]) -> bool:
        """
        Function that validates files. Checks if any of the files in file_names passes a regex check with the
        valid_types. If True, a file that marks a dataset is present in file_names

        :param file_names: List of the files to check, they can be a Path, or a str with the name of the file.
        """
        for item in file_names:
            name = item
            if isinstance(item, Path):
                name = item.name
            for tpe in cls.valid_types:
                match_pattern = re.compile(tpe)
                assert isinstance(name, str)
                if match_pattern.search(name):
                    return True
        return False


class Item(QtGui.QStandardItem):
    """
    Basic item of our model.

    :param path: The path of the folder that this item represents
    :param files: Dictionary of all the files present in that folder. The dictionary should have the Path of the files
        as key, and the ContentType as value.
    """

    def __init__(self, path: Path, files: Dict[Path, ContentType] = {}):
        super().__init__()
        self.path = path
        self.files = {}
        self.tags: List[str] = []
        self.tags_widget = ItemTagLabel(self.tags)
        self.star = False
        self.trash = False
        self.scroll_height = 0
        self.show = True
        if files is not None:
            self.files.update(files)
            self.tags = [file.stem for file, file_type in self.files.items() if file_type == ContentType.tag]
            if '__star__' in self.tags and '__trash__' in self.tags:
                star_path = self.path.joinpath('__star__.tag')
                trash_path = self.path.joinpath('__trash__.tag')
                if star_path.is_file() and trash_path.is_file():
                    logger().error(
                        f'The folder: {self.path} contains both the star and trash tag. Both tags will be deleted.')
                    star_path.unlink()
                    trash_path.unlink()
                    self.tags.remove('__star__')
                    self.tags.remove('__trash__')
            elif '__star__' in self.tags:
                self.star = True
                self.tags.remove('__star__')
            elif '__trash__' in self.tags:
                self.trash = True
                self.tags.remove('__trash__')
            self.tags_widget = ItemTagLabel(self.tags)

        self.setText(str(self.path.name))

    def add_file(self, path: Path) -> None:
        """
        Adds a file to the item files. If the file is a tag, changes the widget and runs the model tags_changed
        method.

        :param path: The file to be added.
        """
        file_type = ContentType.sort(path)
        self.files[path] = file_type

        if file_type == ContentType.tag:
            if path.name == '__star__.tag':
                # Check if the item is not already trash.
                trash_path = path.parent.joinpath('__trash__.tag')
                if trash_path.is_file():
                    path.unlink()
                    error_msg = QtWidgets.QMessageBox()
                    error_msg.setText(f'Folder is already trash. Please do not add both __trash__ and __star__ tags in the same folder. '
                                      f' \n {path} was deleted ')
                    error_msg.setWindowTitle(f'Deleting __trash__.tag')
                    error_msg.exec_()
                    return
                else:
                    self.star = True

            elif path.name == '__trash__.tag':
                # Check if the item is not already star.
                star_path = path.parent.joinpath('__star__.tag')
                if star_path.is_file():
                    path.unlink()
                    error_msg = QtWidgets.QMessageBox()
                    error_msg.setText(
                        f'Folder is already star. Please do not add both __trash__ and __star__ tags in the same folder. '
                        f' \n {path} was deleted ')
                    error_msg.setWindowTitle(f'Deleting __star__.tag')
                    error_msg.exec_()
                    return
                else:
                    self.trash = True
            else:
                self.tags.append(path.stem)
                self.tags_widget.add_tag(path.stem)

            model = self.model()
            assert isinstance(model, FileModel)
            model.tags_changed(self)

    def delete_file(self, path: Path) -> None:
        """
        deletes a file from item files. If the file is a tag, changes the widget and runs the model tags_changed
        method.

        :param path: The file to be deleted.
        """
        file_type = ContentType.sort(path)
        self.files.pop(path)

        if file_type == ContentType.tag:
            if path.stem in self.tags:
                self.tags.remove(path.stem)
                self.tags_widget.delete_tag(path.stem)

                if path.name == '__star__.tag':
                    self.star = False
                elif path.name == '__trash__.tag':
                    self.trash = False

                model = self.model()
                assert isinstance(model, FileModel)
                model.tags_changed(self)

    def change_path(self, path: Path) -> None:
        """Changes the internal path of the item as welll as the text of it."""
        self.path = path
        self.setText(str(path.name))

    def removeRow(self, row: int) -> None:
        """
        Checks if this item also needs to be deleted when deleting a children.
        """
        super().removeRow(row)
        files = [file for file in self.files.keys()]
        if not self.hasChildren() and not SupportedDataTypes.check_valid_data(files):
            parent = self.parent()
            if parent is None:
                self.model().delete_root_item(self.row(), self.path)
            else:
                model = self.model()
                assert isinstance(model, FileModel)
                del model.main_dictionary[self.path]
                parent.removeRow(self.row())

    def create_tags(self) -> None:
        """
        Creates the tags widget. When filtering the widgets gets deleted.
        """
        # Deleting the tags_widget widget.
        self.tags_widget = None  # type: ignore[assignment] # This variable gets re populated immediately afterwards.
        self.tags_widget = ItemTagLabel(self.tags)

    def match(self, queries_dict: Dict[str, List[str]]) -> bool:
        """
        Checks if this item matches the queries passed in the queries_dict. To determine the match a regex check is
        performed either on the path of the items (for 'names' queries) or agaisnt all of the files inside the Item
        (for every other type of query). If the Item contains any children, it will perform the same check for all of
        its children recursively. If any of its children matches, this Item will match too.

        :param queries_dict: Dictionary with the queries. The keys for the dictionary should be the different values
            of ContentType in the form of strings, with the exception of the key 'names' (this is to match the path
            of the item, not its files). E.g.:

                queries_dict = {'tag': ["invalid data"],
                                'md': [],
                                'image': ["plot"],
                                'json': [],
                                'name': []}

                The item will pass this check if it has a tag file whose name passes a regex check agaisnt
                "invalid data" and an image file whose name passes a regex check agaisnt "plot".
        """
        # Check the children first.
        children_matches = []
        if self.hasChildren():
            for i in range(self.rowCount()):
                child = self.child(i, 0)
                assert isinstance(child, Item)
                children_matches.append(child.match(queries_dict))
        # If any children passes, this item passes too.
        if True in children_matches:
            return True

        # Start the check for this item

        # Checks specifically for the path name.
        if len(queries_dict['name']) > 0:
            try:
                name_matches = [re.compile(query, flags=re.IGNORECASE).search(str(self.path)) for query in
                                queries_dict['name']]
                if None in name_matches:
                    return False
            except re.error as e:
                logger().error(f'Regex matching failed: {e}')

        # Check the rest of the files.
        if self.files:

            for file_types, queries in queries_dict.items():
                if file_types != 'name':
                    try:
                        if len(queries) > 0:
                            sorted_type = ContentType.sort(file_types)
                            # Get all the matches
                            matches = [re.compile(query, flags=re.IGNORECASE).search(str(file.name)) for file, file_type
                                       in self.files.items() for query in queries if file_type == sorted_type]

                            # Convert the matches into booleans and count them
                            n_matches = 0
                            for match in matches:
                                if match:
                                    n_matches += 1

                            # Multiple files can pass the same query, meaning that the true counts might be higher than the
                            # length of queries.
                            if n_matches < len(queries):
                                return False
                    except re.error as e:
                        logger().error(f'Regex matching failed: {e}')
            return True

        # TODO: Make sure this is correct.
        # If it has no files, it fails the check
        return False


class FileModel(QtGui.QStandardItemModel):
    """
    Model holding the file structure. Column 0 holds the items that represent datasets, these have all the information
    about them, the files they have, the tags they hold and wether or not they are star or trash. Column 1 are only
    there to display the tags of each item in the same row. The widget displayed in column 1 point towards the
    tag_widget of column 0, so the only thing that needs to be manually changed of them is the icon.

    :param monitor_path: The directory that we are monitoring as a string.
    :param rows: The number of initial rows.
    :param columns: The number of initial columns
    :param Parent: The parent of the model.
    """
    # Signal(Path) -- Emitted when there has been an update to the currently selected folder.
    #: Arguments:
    #:   - The path of the currently selected folder.
    update_me = Signal(Path)

    # Signal() -- Emitted when an item has changed its icon.
    adjust_width = Signal()

    # Signal() -- Emitted when the model gets refreshed.
    model_refreshed = Signal()

    def __init__(self, monitor_path: str, rows: int, columns: int, parent: Optional[Any] = None):
        super().__init__(rows, columns, parent=parent)
        self.monitor_path = Path(monitor_path)
        self.header_labels = ['File path', 'Tags']
        self.currently_selected_folder = None

        # The main dictionary has all the datasets (folders) Path as keys, with the actual item as its value.
        self.main_dictionary: Dict[Path, Item] = {}
        self.load_data()

        # Watcher setup with connected signals.
        self.watcher_thread = QtCore.QThread(parent=self)
        self.watcher = WatcherClient(self.monitor_path)
        self.watcher.moveToThread(self.watcher_thread)
        self.watcher_thread.started.connect(self.watcher.run)

        self.watcher.moved.connect(self.on_file_moved)
        self.watcher.created.connect(self.on_file_created)
        self.watcher.deleted.connect(self.on_file_deleted)
        self.watcher.modified.connect(self.on_file_modified)
        self.watcher.closed.connect(self.on_file_closed)

        self.watcher_thread.start()

        self.itemChanged.connect(self.on_renaming_file)

    @Slot(QtGui.QStandardItem)
    def on_renaming_file(self, item: Item) -> None:
        """
        Triggered every time an item changes.

        If the user changes the name of an item in the view, the item gets the name changed in the actual holder. If an error while changing the name
        happens, the text is not changed and a message pops with the error.

        :param item: QStandardItem, to be renamed
        """
        if item.column() == 1:
            return

        p = item.path
        new_name = item.text()
        if new_name != p.name:
            try:
                target = p.parent.joinpath(new_name)
                p.rename(target)
            except Exception as e:
                item.setText(p.name)
                error_message = QtWidgets.QMessageBox()
                error_message.setText(f"{e}")
                error_message.exec_()

    def refresh_model(self) -> None:
        """
        Deletes all the data from the model and loads it again.
        """
        self.clear()
        self.main_dictionary = {}
        self.load_data()
        self.model_refreshed.emit()

    def load_data(self) -> None:
        """
        Goes through all the files in the monitor path and loads the model.
        """
        # Sets the header data.
        self.setHorizontalHeaderLabels(self.header_labels)

        walk_results = [i for i in os.walk(self.monitor_path)]

        # Sorts the results of the walk. Creates a dictionary of all the current files and directories in the
        # monitor_path with the following structure:
        # {Directory_1: {file_1: file_type
        #                file_2: file_type}
        #  Directory_2: {file_1: file_type
        #                file_2: file_type}...}
        data_dictionary = {
            Path(walk_entry[0]): {Path(walk_entry[0]).joinpath(file): ContentType.sort(file) for file in walk_entry[2]}
            for walk_entry in walk_results if SupportedDataTypes.check_valid_data(file_names=walk_entry[
                2])}

        for folder_path, files_dict in data_dictionary.items():
            self.sort_and_add_item(folder_path, files_dict)

    def sort_and_add_item(self, folder_path: Path, files_dict: Optional[Dict] = None) -> None:
        """
        Adds one or more items into the model. New parent items are created if required.

        :param folder_path: `Path` of the file or folder being added to the tree.
        :param files_dict: Optional. Used to get the tags for showing in the 'Tags' column of the tree. It will check
            for all tag file type and create the item for it. The format should be:
                {path_of_file_1: ContentType.sort(path_of_file_1),
                path_of_file_2: ContentType.sort(path_of_file_2)}
        """

        # Check if the new item should have a parent item. If the new item should have a parent, but this does
        # not yet exist, create it.
        if folder_path.parent == self.monitor_path:
            parent_item, parent_path = None, None
        elif folder_path.parent in self.main_dictionary:
            parent_item, parent_path = \
                self.main_dictionary[folder_path.parent], folder_path.parent
        else:
            parent_folder_files = {file: ContentType.sort(file) for file in folder_path.parent.iterdir() if
                                   file.is_file()}
            self.sort_and_add_item(folder_path.parent, parent_folder_files)
            parent_item, parent_path = \
                self.main_dictionary[folder_path.parent], folder_path.parent

        # Create Item and add it to the model
        if files_dict is None:
            files_dict = {}
        item = Item(folder_path, files_dict)
        tags_item = QtGui.QStandardItem()

        if item.star:
            tags_item.setIcon(get_star_icon())
        elif item.trash:
            tags_item.setIcon(get_trash_icon())
        else:
            tags_item.setIcon(QtGui.QIcon())

        self.main_dictionary[folder_path] = item
        if parent_path is None:
            row = self.rowCount()
            self.setItem(row, 0, item)
            self.setItem(row, 1, tags_item)
        else:
            assert isinstance(parent_item, Item)
            parent_item.appendRow([item, tags_item])

    @Slot(FileSystemEvent)
    def on_file_created(self, event: FileSystemEvent) -> None:
        """
        Gets called everytime a new file or folder gets created. Checks what it is and if it should be added and adds
        data to the model.
        """
        logger().info(f'file created: {event}')

        path = Path(event.src_path)
        # If a folder is created, it will be added when a data file will be created.
        if not path.is_dir():
            # Every folder that is currently in the tree will be in the main dictionary.
            if path.parent in self.main_dictionary:
                parent = self.main_dictionary[path.parent]
                if path not in parent.files:
                    parent.add_file(path)

            # If the parent of the file does not exist, we first need to check that file is valid data.
            elif SupportedDataTypes.check_valid_data([path]):
                new_files_dict = {file: ContentType.sort(file) for file in path.parent.iterdir() if
                                  str(file.suffix) != ''}
                self.sort_and_add_item(path.parent, new_files_dict)
                parent = self.main_dictionary[path.parent]
                # Send signal indicating that current folder requires update
            # TODO: Play with deleting files while you have a the folder selected, this line seem to crash.
            if self.currently_selected_folder is not None and parent.path.is_relative_to(
                    self.currently_selected_folder):
                self.update_me.emit(parent.path)

    @Slot(FileSystemEvent)
    def on_file_deleted(self, event: FileSystemEvent) -> None:
        """
        Triggered every time a file or directory is deleted. Identifies if the deleted file/folder is relevant and
        deletes it and any other non-relevant files.
        """
        logger().info(f'file deleted: {event}')

        path = Path(event.src_path)
        if path.suffix == "":
            if path in self.main_dictionary:
                item = self.main_dictionary[path]

                self._delete_all_children_from_main_dictionary(item)
                del self.main_dictionary[path]

                # Checks if we need to remove a row from a parent item or the root model itself.
                if item.parent() is None:
                    self.removeRow(item.row())
                else:
                    item.parent().removeRow(item.row())

        else:
            if path.parent in self.main_dictionary:
                parent = self.main_dictionary[path.parent]
                if path in parent.files:
                    # Checks if the file is a data file.
                    if SupportedDataTypes.check_valid_data([path]):
                        # Check if there are other data files remaining in the directory.
                        all_folder_files = [file for file in parent.path.iterdir()]

                        # Checks if the folder itself needs to be deleted or only the file
                        if SupportedDataTypes.check_valid_data(
                                all_folder_files) or parent.hasChildren():
                            parent.delete_file(path)
                        else:
                            # If the parent needs to be deleted, removes it from the correct widget.
                            if parent.parent() is None:
                                self.removeRow(parent.row())
                            else:
                                parent.parent().removeRow(parent.row())
                            del self.main_dictionary[parent.path]
                    else:
                        parent.delete_file(path)
                # Send signal indicating that current folder requires update.
                if self.currently_selected_folder is not None and parent.path.is_relative_to(
                        self.currently_selected_folder):
                    self.update_me.emit(parent.path)

    def _delete_all_children_from_main_dictionary(self, item: Item) -> None:
        """
        Helper function that deletes all the children from the item passed.

        :param item: The item whose children should be deleted.
        """
        path = item.path
        children_folders = [key for key in self.main_dictionary.keys() if key.is_relative_to(path) and key != path]
        for child in children_folders:
            child_item = self.main_dictionary[child]
            if child_item.hasChildren():
                self._delete_all_children_from_main_dictionary(child_item)
            del self.main_dictionary[child_item.path]

    @Slot(FileSystemEvent)
    def on_file_moved(self, event: FileSystemEvent) -> None:
        """
        Gets triggered everytime a file is moved or the name of a file (including type) changes.
        """
        logger().info(f'file moved: {event}')

        parent = None

        # File moved gets triggered with None and '', for the event paths. From what I can tell, they are not useful,
        # so we ignore them.
        if event.src_path is not None and event.src_path != '' \
                and event.dest_path is not None and event.dest_path != '':
            src_path = Path(event.src_path)
            dest_path = Path(event.dest_path)

            # If a directory is moved, only need to change the old path for the new path
            if event.is_directory:
                if src_path in self.main_dictionary:
                    changed_item = self.main_dictionary.pop(src_path)
                    self.main_dictionary[dest_path] = changed_item
                    changed_item.change_path(dest_path)

            # Checking for a file becoming a data file.
            elif not SupportedDataTypes.check_valid_data([src_path]) and SupportedDataTypes.check_valid_data(
                    [dest_path]):
                # If the parent exists in the main dictionary, the model already has all the files and its tracking
                # that folder, only updates the file itself.
                if src_path.parent in self.main_dictionary:
                    parent = self.main_dictionary[src_path.parent]
                    del parent.files[src_path]
                    parent.files[dest_path] = ContentType.sort(dest_path)
                elif dest_path.parent in self.main_dictionary:
                    parent = self.main_dictionary[dest_path.parent]
                    del parent.files[src_path]
                    parent.files[dest_path] = ContentType.sort(dest_path)

                # New folder to keep track.
                else:
                    new_entry = {file: ContentType.sort(file) for file in dest_path.parent.iterdir() if
                                 str(file.suffix) != ''}
                    self.sort_and_add_item(dest_path.parent, new_entry)
                    parent = self.main_dictionary[dest_path.parent]

            # Checking if a data file stops being a data file.
            elif SupportedDataTypes.check_valid_data([src_path]) and not SupportedDataTypes.check_valid_data(
                    [dest_path]):
                if src_path.parent in self.main_dictionary:
                    parent = self.main_dictionary[src_path.parent]
                elif dest_path.parent in self.main_dictionary:
                    parent = self.main_dictionary[dest_path.parent]

                if parent is not None:
                    del parent.files[src_path]
                    parent.files[dest_path] = ContentType.sort(dest_path)

                    # Checks if there are other data files in the parent.
                    parent_files = [key for key in parent.files.keys()]
                    if not SupportedDataTypes.check_valid_data(
                            parent_files) and not parent.hasChildren():
                        # If the parent has other children, it means there are more data files down the file tree
                        # and the model should keep track of these folders.
                        del self.main_dictionary[parent.path]

                        # Checks if we need to remove a row from a parent item or the root model itself.
                        if parent.parent() is None:
                            self.removeRow(parent.row())
                            parent = None
                        else:
                            parent_row = parent.row()
                            # Renaming parent to its parent for the update_me check.
                            parent_ = parent.parent()
                            parent_.removeRow(parent_row)

            # A normal file changed.
            else:
                # Find the parent.
                parent = None
                if src_path.parent in self.main_dictionary:
                    parent = self.main_dictionary[src_path.parent]
                elif dest_path.parent in self.main_dictionary:
                    parent = self.main_dictionary[dest_path.parent]

                # Update the file.
                if parent is not None:
                    if src_path in parent.files:
                        parent.delete_file(src_path)
                    if dest_path not in parent.files:
                        parent.add_file(dest_path)

            if self.currently_selected_folder is not None and dest_path.is_relative_to(self.currently_selected_folder):
                # This happenes when a top level item is changed.
                if parent is None:
                    check = self.check_all_files_are_valid(self.main_dictionary[dest_path], dest_path)[0]
                else:
                    check = self.check_all_files_are_valid(parent, parent.path)[0]

                if check:
                    self.update_me.emit(self.currently_selected_folder)

    def check_all_files_are_valid(self, item: Item, first_path: Path) -> Tuple[bool, Path]:
        """
        Checks that all the files inside of the item have a valid path. This is used when changing the name of currently
        selected folders to see if an update to change the folders should be triggered or not.

        :param item: The item we need to do the check.
        :param first_path: The path of the first item. This is needed because the function is recursive and need a way
            of knowing what the original path was.
        :return: Returns a tuple composed of a bool indicating if it passed or not the check and the first_path.
        """
        for file in item.files.keys():
            if not file.is_relative_to(first_path):
                return False, first_path

        if item.hasChildren():
            for i in range(item.rowCount()):
                child = item.child(i, 0)
                assert isinstance(child, Item)
                ret = self.check_all_files_are_valid(child, first_path)
                if not ret[0]:
                    return ret[0], first_path

        return True, first_path

    @Slot(FileSystemEvent)
    def on_file_modified(self, event: FileSystemEvent) -> None:
        """
        Gets triggered everytime a file is modified
        """
        # logger().info(f'file modified: {event}')
        pass

    @Slot(FileSystemEvent)
    def on_file_closed(self, event: FileSystemEvent) -> None:
        """
        Gets triggered everytime a file is closed
        """
        # logger().info(f'file closed: {event}')
        pass

    def delete_root_item(self, row: int, path: Path) -> None:
        """
        Deletes a root item from the model and main_dictionary.
        """
        self.removeRow(row)
        del self.main_dictionary[path]

    def update_currently_selected_folder(self, path: Path) -> None:
        """
        Updates the currently selected folder.
        """
        self.currently_selected_folder = path

    def star_item(self, item_index: QtCore.QModelIndex) -> None:
        """
        Creates the __star__.tag file if it doesn't exist, deletes it if it does, in the folder for the item.
         If it finds __trash__.tag there it will delete it.

        :param item_index: The index of the item that needs to be starred.
        """
        # If the item is of column 1, change it to the sibling at column 0
        if item_index.column() == 1:
            item_index = item_index.siblingAtColumn(0)

        item = self.itemFromIndex(item_index)
        assert isinstance(item, Item)
        path = item.path
        star_path = path.joinpath('__star__.tag')
        trash_path = path.joinpath('__trash__.tag')
        # If a trash file in the star folder exists, delete it.
        if trash_path.is_file():
            trash_path.unlink()

        # If the folder is already a starred folder, un-star it.
        if star_path.is_file():
            star_path.unlink()
        else:
            with open(star_path, 'w') as file:
                file.write('')

    def trash_item(self, item_index: QtCore.QModelIndex) -> None:
        """
        Creates the __trash__.tag file if it doesn't exist, deletes it if it does, in the folder for the item.
         If it finds __star__.tag there it will delete it

        :param index: The index of the item that needs to be trashed.
        """

        # If the item is of column 1, change it to the sibling at column 0
        if item_index.column() == 1:
            item_index = item_index.siblingAtColumn(0)

        item = self.itemFromIndex(item_index)
        assert isinstance(item, Item)
        path = item.path
        star_path = path.joinpath('__star__.tag')
        trash_path = path.joinpath('__trash__.tag')
        # If a star file in the star folder exists, delete it.
        if star_path.is_file():
            star_path.unlink()

        # If the folder is already a trashed folder, un-trash it.
        if trash_path.is_file():
            trash_path.unlink()
        else:
            with open(trash_path, 'w') as file:
                file.write('')

    def delete_item(self, item_index: QtCore.QModelIndex) -> None:
        """
        Currently nothing happens. This is not yet implemented
        """
        item = self.itemFromIndex(item_index)

    def tags_changed(self, item: Item) -> None:
        """
        Gets called when item changes its tags, checks if item is either star, trash or nothing and sets the correct
        icon.

        :param item: The Item that had its tags changed.
        """
        parent = item.parent()
        if parent is None:
            row = item.row()
            item_column_1 = self.item(row, 1)
        else:
            item_column_1 = parent.child(item.row(), 1)

        if item.star:
            item_column_1.setIcon(get_star_icon())
        elif item.trash:
            item_column_1.setIcon(get_trash_icon())
        else:
            item_column_1.setIcon(QtGui.QIcon())

        self.adjust_width.emit()


class SortFilterProxyModel(QtCore.QSortFilterProxyModel):

    # Signal() -- Emitted before filtering is going to happen.
    filter_incoming = Signal()

    # Signal() -- Emitted when the filtering has finished.
    filter_finished = Signal()

    def __init__(self, parent: Optional[QtCore.QObject] = None):
        """
        QSortFilterProxyModel with our custom filtering and stars and trash. The parent status always overrides
        the children status, e.g.: If a parent is trash but its children are not, the parent with the children will be
        hidden.
        """
        super().__init__(parent=parent)

        self.only_star = False
        self.hide_trash = False

        self.queries_dict: Optional[Dict[str, List[str]]] = None

    def star_trash_toggle(self, star_status: bool, trash_status: bool) -> None:
        """
        Updates the star and trash status and triggers a filter.

        :param star_status: The new star status. True for showing only starred items.
        :param trash_status: The new trash status. True for hiding all stars.
        """
        self.only_star = star_status
        self.hide_trash = trash_status
        self.trigger_filter()

    def filter_text_changed(self, queries_dict: Optional[Dict[str, List[str]]]) -> None:
        """
        Gets called every time the filter text edit changes and triggers and update.

        :queries_dict: The dictionary with the queries. Same structure as Item.match().
        """
        self.queries_dict = queries_dict
        self.trigger_filter()


    def filterAcceptsRow(self, source_row: int, source_parent: QtCore.QModelIndex) -> bool:
        """
        Override of the QSortFilterProxyModel. Our custom filtering needs are implemented here.
        Checks wether or not to show the item.

        :param source_row: The row of the item.
        :param source_parent: The index of the parent of the item.
        :returns: `True` if the item should be shown or `False` if the item should be hidden.
        """
        # Get the item
        source_model = self.sourceModel()
        assert isinstance(source_model, FileModel)
        parent_item = source_model.itemFromIndex(source_parent)
        if parent_item is None:
            item = source_model.item(source_row, 0)
        else:
            item = parent_item.child(source_row, 0)
        assert isinstance(item, Item)

        # Check if it passes the current queries.
        if self.queries_dict is not None:
            if not item.match(self.queries_dict):
                item.show = False
                return False

        # Checks for star or trash status
        if self.only_star and item.star:
            item.show = True
            return True
        elif self.only_star and not item.star:
            # Checks if their children should be shown, so that this item gets shown too.
            if item.hasChildren():
                if not self.hide_trash:
                    ret = self._check_children_filter(item)
                    item.show = ret
                    return ret
                elif not item.trash:
                    ret = self._check_children_filter(item)
                    item.show = ret
                    return ret
            # If a parent is star, shows the children items too.
            if self._check_parent_filter(item):
                item.show = True
                return True
            item.show = False
            return False
        elif self.hide_trash and not item.trash:
            item.show = True
            return True
        elif self.hide_trash and item.trash:
            item.show = False
            return False
        else:
            item.show = True
            return True

    def _check_children_filter(self, item: Item) -> bool:
        """
        Helper function, recursively checks if any of the children of item should be shown.

        :param item: The item who's children should be checked.
        :return: True if it should be shown, False otherwise.
        """
        for i in range(item.rowCount()):
            child = item.child(i, 0)
            assert isinstance(child, Item)
            if child.hasChildren():
                childs_children_check = self._check_children_filter(child)
                if childs_children_check:
                    return True
            if self.only_star and child.star:
                return True
        return False

    def _check_parent_filter(self, item: Item) -> bool:
        """
        Checks if a parent of the item is starred and star only is is True.

        :param item: The item who's children should be checked.
        :return: True if it should be shown, False otherwise.
        """
        parent = item.parent()
        if parent is not None:
            keep_going = True
            while keep_going:
                assert isinstance(parent, Item)
                if self.only_star and parent.star:
                    return True
                parent = parent.parent()
                if parent is None:
                    keep_going = False
        return False

    def trigger_filter(self) -> None:
        """
        Convenience function for invalidating the filter and triggering the filter_triggered signal.
        """
        self.filter_incoming.emit()
        self.invalidateFilter()
        self.filter_finished.emit()


class FileTreeView(QtWidgets.QTreeView):
    # Signal(Path) -- Emitted when the selected item changes.
    #: Arguments:
    #:  - The current selected item index, the previously selected item index.
    selection_changed = Signal(QtCore.QModelIndex, QtCore.QModelIndex)

    # Signal(Path) -- Emitted when the star action has been clicked.
    #: Arguments:
    #:  - The index of the currently selected item.
    item_starred = Signal(QtCore.QModelIndex)

    # Signal(Path) -- Emitted when the trash action has been clicked.
    #: Arguments:
    #:  - The index of the currently selected item.
    item_trashed = Signal(QtCore.QModelIndex)

    # Signal(Path) -- Emitted when the delete action has been clicked.
    #: Arguments:
    #:  - The index of the currently selected item.
    item_deleted = Signal(QtCore.QModelIndex)

    def __init__(self, proxy_model: SortFilterProxyModel, parent: Optional[Any] = None):
        """
        The TreeView used in the FileExplorer widget.
        """
        super().__init__(parent)

        self.proxy_model = proxy_model
        model = proxy_model.sourceModel()
        assert isinstance(model, FileModel)
        self.model_ = model
        self.collapsed_state: Dict[Path, bool] = {}
        self.star_text = 'Star'
        self.un_star_text = 'Un-star'
        self.trash_text = 'Trash'
        self.un_trash_text = 'Un-trash'

        self.context_menu = QtWidgets.QMenu(self)
        self.star_action = QtWidgets.QAction('Star')
        self.trash_action = QtWidgets.QAction('Trash')
        self.delete_action = QtWidgets.QAction('Delete')

        self.star_action.triggered.connect(self.on_emit_item_starred)
        self.trash_action.triggered.connect(self.on_emit_item_trashed)
        self.delete_action.triggered.connect(self.on_emit_item_delete)
        self.proxy_model.filter_incoming.connect(self.on_filter_incoming_event)
        self.proxy_model.filter_finished.connect(self.on_filter_ended_event)

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.on_context_menu_requested)

        self.setUniformRowHeights(True)
        self.setSortingEnabled(True)

        self.setModel(self.proxy_model)

    @Slot()
    def on_filter_incoming_event(self) -> None:
        """
        Gets called everytime the proxy model emmits the filter_incoming_event signal.
        """
        self.create_collapsed_state()

    def on_filter_ended_event(self) -> None:
        """
        Gets called everytime the proxy model emmits the filter_ended_event signal.
        The tags need to be reset after a filtering event happens.
        """
        self.set_all_tags()
        self.restore_previous_collapsed_state()

    def set_all_tags(self) -> None:
        """
        Sets the tag label widget for all the rows.
        """
        for i in range(self.model_.rowCount()):
            item = self.model_.item(i, 0)
            if item is not None and isinstance(item, Item):
                self._set_widget_for_item_and_children(item)
        self.on_adjust_column_width()

    def _set_widget_for_item_and_children(self, item: Item) -> None:
        """
        Helper function of set_all_tags, goes throguh the passed item and all of its children and sets all of the
        tag widget from column 0 for the items in row 1.

        :param item: The item that its setting the widget for.
        """
        parent = item.parent()
        if parent is None:
            tags_item = self.model_.item(item.row(), 1)
        else:
            tags_item = parent.child(item.row(), 1)

        tags_index = self.model_.indexFromItem(tags_item)
        proxy_tag_index = self.proxy_model.mapFromSource(tags_index)
        item.create_tags()  # The tags get created every time because they get deleted after filtering.
        self.setIndexWidget(proxy_tag_index, item.tags_widget)
        if item.hasChildren():
            for i in range(item.rowCount()):
                child = item.child(i)
                assert isinstance(child, Item)
                self._set_widget_for_item_and_children(child)

    @Slot(QtCore.QPoint)
    def on_context_menu_requested(self, pos: QtCore.QPoint) -> None:
        """
        Shows the context menu when a right click happens.

        :param pos: The position of the mouse when the call happens
        """
        proxy_index = self.indexAt(pos)
        if proxy_index.column() == 1:
            proxy_index = proxy_index.siblingAtColumn(0)
        index = self.proxy_model.mapToSource(proxy_index)
        item = self.model_.itemFromIndex(index)
        # if the selected item is None, no menu should be shown.
        if item is None:
            return

        assert isinstance(item, Item)
        # Sets the correct the correct text for the context menu depending on the state of the item.
        if item.star:
            self.star_action.setText(self.un_star_text)
        else:
            self.star_action.setText(self.star_text)
        if item.trash:
            self.trash_action.setText(self.un_trash_text)
        else:
            self.trash_action.setText(self.trash_text)

        self.context_menu.addAction(self.star_action)
        self.context_menu.addAction(self.trash_action)
        self.context_menu.addSeparator()
        self.context_menu.addAction(self.delete_action)
        self.context_menu.exec_(self.mapToGlobal(pos))

    @Slot()
    def on_emit_item_starred(self) -> None:
        """
        Gets called when the user press the star action. Emits the star_item signal.
        """
        item_proxy_index = self.currentIndex()
        item_index = self.proxy_model.mapToSource(item_proxy_index)
        self.model_.star_item(item_index)

    @Slot()
    def on_emit_item_trashed(self) -> None:
        """
        Gets called when the user press the trash action. Emits the trash_item signal.
        """
        item_proxy_index = self.currentIndex()
        item_index = self.proxy_model.mapToSource(item_proxy_index)
        self.model_.trash_item(item_index)

    @Slot()
    def on_emit_item_delete(self) -> None:
        """
        Gets called when the user press the delete action. Emits the delete_item signal.
        """
        item_proxy_index = self.currentIndex()
        item_index = self.proxy_model.mapToSource(item_proxy_index)
        self.model_.delete_item(item_index)

    @Slot()
    def on_adjust_column_width(self) -> None:
        """
        Gets called when the model changed the icon of an item. When changing an item icons that has the tag widget
        displaying tags, the icon would be superimposed with the widget, moving the column_width by 1 pixel and
        setting it back fixes it.
        """
        column_width = self.columnWidth(1)
        self.setColumnWidth(1, column_width + 1)
        self.setColumnWidth(1, column_width - 1)

    def currentChanged(self, current: QtCore.QModelIndex, previous: QtCore.QModelIndex) -> None:
        """
        Gets called everytime the selection of the tree changes. Emits a signal indicating the current and previous
        selected item.

        :param current: The QModelIndex of the current selected item.
        :param previous: The QModelIndex of the previously selected item.
        """
        self.selection_changed.emit(current, previous)

    def create_collapsed_state(self, incoming_item: Optional[Item] = None) -> None:
        """
        Updates the self.collapsed_state dictionary with the currently shown items.
        Gets called recursively to update all items.
        """
        if incoming_item is None:
            for i in range(self.model_.rowCount()):
                item = self.model_.item(i, 0)
                assert isinstance(item, Item)
                # If the item is not shown, the collapsed setting don't change.
                if item.show:
                    source_index = self.model_.index(i, 0, QtCore.QModelIndex())
                    index = self.proxy_model.mapFromSource(source_index)
                    self.collapsed_state[item.path] = self.isExpanded(index)
                    if item.hasChildren():
                        self.create_collapsed_state(incoming_item=item)

        else:
            for i in range(incoming_item.rowCount()):
                child = incoming_item.child(i, 0)
                assert isinstance(child, Item)
                # If the item is not shown, the collapsed setting don't change.
                if child.show:
                    source_index = self.model_.indexFromItem(child)
                    child_index = self.proxy_model.mapFromSource(source_index)
                    self.collapsed_state[child.path] = self.isExpanded(child_index)
                    if child.hasChildren():
                        self.create_collapsed_state(incoming_item=child)

    def restore_previous_collapsed_state(self) -> None:
        """
        Sets every item in the collapsed_state dictionary the correct collapsed setting.
        """
        for path, state in self.collapsed_state.items():
            source_index = self.model_.indexFromItem(self.model_.main_dictionary[path])
            proxy_index = self.proxy_model.mapFromSource(source_index)
            self.setExpanded(proxy_index, state)


# TODO: Figure out the parent situation going on here.
class FileExplorer(QtWidgets.QWidget):
    """
    Helper widget to unify the FileTree with the line edit and status buttons.
    """

    def __init__(self, proxy_model: SortFilterProxyModel, parent: Optional[Any]=None,
                 *args: Any, **kwargs: Any):
        super().__init__(parent=parent, *args, **kwargs)  # type: ignore[misc] # I suspect this error comes from having parent possibly be a kwarg too.

        # Tree and model initialization
        self.proxy_model = proxy_model
        self.model = proxy_model.sourceModel()
        assert isinstance(self.model, FileModel)
        self.file_tree = FileTreeView(proxy_model=proxy_model, parent=self)
        self.file_tree.set_all_tags()
        self.model.adjust_width.connect(self.file_tree.on_adjust_column_width)
        self.model.model_refreshed.connect(self.file_tree.set_all_tags)

        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.filter_and_buttons_layout = QtWidgets.QHBoxLayout()
        self.bottom_buttons_layout = QtWidgets.QHBoxLayout()

        self.filter_line_edit = QtWidgets.QLineEdit()
        self.filter_line_edit.setPlaceholderText('Filter Items')

        self.star_button = QtWidgets.QPushButton('Star')
        self.trash_button = QtWidgets.QPushButton('Hide Trash')
        self.refresh_button = QtWidgets.QPushButton('Refresh')
        self.expand_button = QtWidgets.QPushButton('Expand')
        self.collapse_button = QtWidgets.QPushButton('Collapse')

        self.star_button.setCheckable(True)
        self.trash_button.setCheckable(True)

        self.filter_and_buttons_layout.addWidget(self.filter_line_edit)
        self.filter_and_buttons_layout.addWidget(self.star_button)
        self.filter_and_buttons_layout.addWidget(self.trash_button)
        self.bottom_buttons_layout.addWidget(self.refresh_button)
        self.bottom_buttons_layout.addWidget(self.expand_button)
        self.bottom_buttons_layout.addWidget(self.collapse_button)
        self.main_layout.addLayout(self.filter_and_buttons_layout)
        self.main_layout.addWidget(self.file_tree)
        self.main_layout.addLayout(self.bottom_buttons_layout)

        self.star_button.clicked.connect(self.star_trash_clicked)
        self.trash_button.clicked.connect(self.star_trash_clicked)
        self.expand_button.clicked.connect(self.file_tree.expandAll)
        self.collapse_button.clicked.connect(self.file_tree.collapseAll)

        self.filter_line_edit.textChanged.connect(self.on_filter_line_edit_text_change)


    @Slot()
    def star_trash_clicked(self) -> None:
        """
        Updates the status of the buttons to the FileTree.
        """
        self.proxy_model.star_trash_toggle(self.star_button.isChecked(), self.trash_button.isChecked())

    @Slot(str)
    def on_filter_line_edit_text_change(self, filter_str: str) -> None:
        """
        Gets called everytime the filter line edit changes texts. Process the text in the line edit, separtes them into
        the different queries and triggers the filtering in the proxy model.

        Queries are separated by commas (','). Empty queries or composed of only
        a single whitespace are ignored. It also ignores the first character of a query if this is a whitespace.

        It accepts 5 kinds of queries:
            * tags: queries starting with, 'tag:', 't:', or 'T:'.
            * Markdown files: queries starting with, 'md:', 'm:', or 'M:'.
            * Images: queries starting with, 'image:', 'i:', or 'I:'.
            * Json files: queries starting with, 'json:', 'j:', or 'J:'.
            * Folder names: any other query.

        :param filter_str: The str that is currently in the filter line text edit.
        """
        raw_queries = filter_str.split(',')
        queries_with_empty_spaces = [item[1:] if len(item) >= 1 and item[0] == " " else item for item in raw_queries]
        queries = [item for item in queries_with_empty_spaces if item != '' and item != ' ']

        if len(queries) == 0:
            queries_dict = None
            self.proxy_model.filter_text_changed(queries_dict)
            return

        tag_queries = []
        md_queries = []
        image_queries = []
        json_queries = []
        name_queries = []
        for query in queries:
            if query != '':
                if query[:4] == 'tag:':
                    tag_queries.append(query[4:])
                elif query[:2] == 't:' or query[:2] == 'T:':
                    tag_queries.append(query[2:])
                elif query[:3] == 'md:':
                    md_queries.append(query[3:])
                elif query[:2] == 'm:' or query[:2] == 'M:':
                    md_queries.append(query[2:])
                elif query[:6] == 'image:':
                    image_queries.append(query[6:])
                elif query[:2] == 'i:' or query[:2] == 'I:':
                    image_queries.append(query[2:])
                elif query[:5] == 'json:':
                    json_queries.append(query[5:])
                elif query[:2] == 'j:' or query[:2] == 'J:':
                    json_queries.append(query[2:])
                else:
                    name_queries.append(query)

            queries_dict = {'tag': tag_queries,
                            'md': md_queries,
                            'image': image_queries,
                            'json': json_queries,
                            'name': name_queries, }

        self.proxy_model.filter_text_changed(queries_dict)


# TODO: Right now the data display only updates when you click on the parent folder. What happens if data is created
#   while the folder display is open. It should absolutely update.
class DataTreeWidget(QtWidgets.QTreeWidget):
    """
    Widget that displays all ddh5 files passed in incoming_data. All items must be in ordered lists with their names,
    paths and DataDicts for the widget to laod properly.

    :param incoming_data: Dictionary containing all the information required to load all ddh5 files. The dictionary
        should contain 3 different items with they keys being: "paths", "names", and "data", each containing a list
        of (in order): Path, str, DataDict. All 3 lists should be ordered by index (meaning for example that index
        number 3 represents a single datadicts). E.g.:
            incoming_data = {"paths": [Path(r"~/data/measurement_1"),
                                       Path(r"~/data/measurement_2"),],
                             "names": ["measurement_1/data",
                                       "measurement_2/data],
                             "data": [{'__creation_time_sec__': 1641938645.0,
                                       '__creation_time_str__': '2022-01-11 16:04:05',
                                       'x': {'__creation_time_sec__': 1641938645.0,
                                             '__creation_time_str__': '2022-01-11 16:04:05',
                                             '__shape__': (1444, 1444),
                                             'axes': [],
                                             'label': '',
                                             'unit': '',
                                             'values': array([[-721.68783649, ....]]) ...
    """

    # Signal(Path) -- Emitted when the user selects the plot option in the popup menu.
    #: Arguments:
    #:   - The path of the ddh5 with the data for the requested plot.
    plot_requested = Signal(Path)

    # incoming_data: Dict[str, Union[Path, str, DataDict]]
    def __init__(self, paths: List[Path], names: List[str], data: DataDict, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        header_item = self.headerItem()
        assert isinstance(header_item, QtWidgets.QTreeWidgetItem)
        header_item.setText(0, "Object")
        header_item.setText(1, "Content")
        header_item.setText(2, "Type")
        self.paths = paths
        self.names = names
        self.data = data

        # Popup menu.
        self.plot_popup_action = QtWidgets.QAction('Plot')
        self.popup_menu = QtWidgets.QMenu(self)

        self.plot_popup_action.triggered.connect(self.emit_plot_requested_signal)

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.on_context_menu_requested)

        self.set_data()

    def set_data(self) -> None:
        """
        Fills the QTreeWidget with the data loaded in the self.data variable.
        """

        for index, data in enumerate(self.data):
            parent_tree_widget = TreeWidgetItem(self.paths[index], None, False, False, self, [self.names[index]])

            data_parent = QtWidgets.QTreeWidgetItem(parent_tree_widget, ['Data'])
            meta_parent = QtWidgets.QTreeWidgetItem(parent_tree_widget, ['Meta'])

            for name, value in data.data_items():
                column_content = [name, str(data.meta_val('shape', name))]
                if name in data.dependents():
                    column_content.append(f'Depends on {str(tuple(data.axes(name)))}')
                else:
                    column_content.append(f'Independent')

                parameter_item = QtWidgets.QTreeWidgetItem(data_parent, column_content)

                for meta_name, meta_value in data.meta_items(name):
                    parameter_meta_item = QtWidgets.QTreeWidgetItem(parameter_item, [meta_name, str(meta_value)])

            for name, value in data.meta_items():
                parameter_meta_item = QtWidgets.QTreeWidgetItem(meta_parent, [name, str(value)])

            parent_tree_widget.setExpanded(True)
            data_parent.setExpanded(True)

            for i in range(self.columnCount() - 1):
                self.resizeColumnToContents(i)

    @Slot(QtCore.QPoint)
    def on_context_menu_requested(self, pos: QtCore.QPoint) -> None:
        """
        Gets called when the user right-clicks on an item.
        """
        item = self.itemAt(pos)
        assert isinstance(item, QtWidgets.QTreeWidgetItem)
        parent_item = item.parent()
        # Check that the item is in fact a top level item and open the popup menu
        if item is not None and parent_item is None:
            self.popup_menu.addAction(self.plot_popup_action)
            self.popup_menu.exec_(self.mapToGlobal(pos))
            self.popup_menu.removeAction(self.plot_popup_action)

    @Slot()
    def emit_plot_requested_signal(self) -> None:
        """
        Emits the signal when the user selects the plot option in the popup menu. The signal is emitted with the Path of
        the current selected item as an argument.
        """
        current_item = self.currentItem()
        assert isinstance(current_item, TreeWidgetItem)
        self.plot_requested.emit(current_item.path)

    def sizeHint(self) -> QtCore.QSize:
        height = 2 * self.frameWidth()  # border around tree
        header_width = 0
        if not self.isHeaderHidden():
            header = self.header()
            headerSizeHint = header.sizeHint()
            height += headerSizeHint.height()
            header_width += headerSizeHint.width()
        rows = 0
        it = QtWidgets.QTreeWidgetItemIterator(self)
        while it.value() is not None:
            rows += 1
            index = self.indexFromItem(it.value())
            height += self.rowHeight(index)
            it += 1  # type: ignore[assignment, operator] # Taken from this example:
# https://riverbankcomputing.com/pipermail/pyqt/2014-May/034315.html

        # calculating width:
        width = 2 * self.frameWidth()
        for i in range(self.columnCount()):
            width += self.sizeHintForColumn(i)

        return QtCore.QSize(width, height)


class FloatingButtonWidget(QtWidgets.QPushButton):
    """
    Floating button inside the textbox showing any md file. Allows editing or saving the file.

    Class taken from: https://www.deskriders.dev/posts/007-pyqt5-overlay-button-widget/
    """

    # Signal() -- Emitted when the user activates save mode.
    save_activated = Signal()

    # Signal() -- Emitted when the user activates edit mode.
    edit_activated = Signal()

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)
        self.padding_right = 5
        self.edit_text = 'Edit'
        self.save_text = 'Save'

        # Start in save mode (True), since you cannot edit the text. Clicks the edit button to switch to edit mode and
        # vice versa.
        self.state = True
        self.setText(self.edit_text)

    def update_position(self) -> None:
        """
        Updates the position of the button if the textbox moves or changes shape.
        """
        parent = self.parent()
        assert isinstance(parent, QtWidgets.QWidget)
        if hasattr(parent, 'viewport'):
            parent_rect = parent.viewport().rect()  # type: ignore[attr-defined] # I am checking for viewport the previous line.
        else:
            parent_rect = parent.rect()

        if not parent_rect:
            return

        x = parent_rect.width() - self.width() - self.padding_right
        y = parent_rect.height() - self.height()
        self.setGeometry(x, y, self.width(), self.height())

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        """
        Gets called every time the resizeEvents gets triggered.
        """
        super().resizeEvent(event)
        self.update_position()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """
        Gets called when the user clicks the button. Decides in which state the button is and what signal to emit.
        Changes the state of the button afterwards.
        """
        if self.state:
            self.edit_activated.emit()
            self.state = False
            self.setText(self.save_text)
        else:
            self.save_activated.emit()
            self.state = True
            self.setText(self.edit_text)


class TextEditWidget(QtWidgets.QTextEdit):
    """
    Widget that displays md files that are in the same folder as a ddh5 file.

    It contains a floating button that allows for editing and saving changes done in the editing phase. Text is not
    editable before clicking the button.
    """

    def __init__(self, path: Path, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.path = path

        self.floating_button = FloatingButtonWidget(parent=self)
        self.floating_button.hide()

        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        self.setSizePolicy(size_policy)

        try:
            with open(path) as file:
                self.file_text = file.read()
        except FileNotFoundError as e:
            logger().error(e)
            self.file_text = 'Comment file could not load. Do not edit as this could rewrite the original comment.'
        self.setReadOnly(True)
        self.setPlainText(self.file_text)
        document = QtGui.QTextDocument(self.file_text, parent=self)
        self.setDocument(document)
        self.text_before_edit = self.toPlainText()
        self.floating_button.save_activated.connect(self.save_activated)
        self.floating_button.edit_activated.connect(self.edit_activated)
        self.document().contentsChanged.connect(self.size_change)

        # Arbitrary threshold height.
        self.max_threshold_height = 211
        self.min_threshold_height = 2
        self.size_change()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        """
        Called every time the size of the widget changes. Triggers the change in position of the floating button.
        """
        super().resizeEvent(event)
        self.floating_button.update_position()

    def size_change(self) -> None:
        """
        Changes the minimum height of the widget. Gets called every time the document changes.
        """
        doc_height = round(self.document().size().height())
        if doc_height <= self.min_threshold_height:
            self.setMinimumHeight(self.min_threshold_height)
        if doc_height <= self.max_threshold_height:
            self.setMinimumHeight(doc_height)
        elif doc_height > self.max_threshold_height:
            self.setMinimumHeight(self.max_threshold_height)

    def sizeHint(self) -> QtCore.QSize:
        super_hint = super().sizeHint()
        height = super_hint.height()
        width = super_hint.width()
        if height >= self.document().size().height():
            height = round(self.document().size().height())

        return QtCore.QSize(width, height)

    def enterEvent(self, *args: Any, **kwargs: Any) -> None:
        super().enterEvent(*args, **kwargs)
        self.floating_button.show()

    def leaveEvent(self, *args: Any, **kwargs: Any) -> None:
        super().enterEvent(*args, **kwargs)
        self.floating_button.hide()

    # TODO: Add a shortcut to finish editing both here and in the future the add comment line too with the same command.
    # TODO: When the saving fails, it completely deletes the old data that's in the markdown. Develop a system where you
    #   try creating a new file, only once you have the new file replace the old one. To test this you need to pass the
    #   wrong type of object to the file.write line and it will fail.
    @Slot()
    def save_activated(self) -> None:
        """
        Saves the file with the current status of the text. Disables the ability to edit the text.
        """
        self.setReadOnly(True)
        try:
            with open(self.path, 'w') as file:
                file.write(self.toPlainText())
        except Exception as e:
            # Set text how it was before
            self.setText(self.text_before_edit)
            # Show the error message
            error_msg = QtWidgets.QMessageBox()
            error_msg.setText(f"{e}")
            error_msg.setWindowTitle(f'Error trying to save markdown edit.')
            error_msg.exec_()

    @Slot()
    def edit_activated(self) -> None:
        """
        Gets called when the user clicks the edit floating button. Allows the user to edit the textbox.
        """
        self.setReadOnly(False)
        self.text_before_edit = self.toPlainText()


class TextInputFloatingButton(QtWidgets.QPushButton):
    """
    Floating button for the text input

    Class taken from: https://www.deskriders.dev/posts/007-pyqt5-overlay-button-widget/
    """

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)
        self.paddingLeft = 5
        self.paddingTop = 5
        self.save_text = 'Save'

        self.setText(self.save_text)

    def update_position(self) -> None:
        """
        Updates the position of the button if the textbox moves or changes shape.
        """
        parent = self.parent()
        assert isinstance(parent, QtWidgets.QWidget)
        if hasattr(parent, 'viewport'):
            parent_rect = parent.viewport().rect()  # type: ignore[attr-defined] # I am checking for viewport the
            # previous line.
        else:
            parent_rect = parent.rect()

        if not parent_rect:
            return

        x = parent_rect.width() - self.width() - self.paddingLeft
        y = parent_rect.height() - self.height() - self.paddingTop
        self.setGeometry(x, y, self.width(), self.height())

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        """
        Gets called every time the resizeEvents gets triggered.
        """
        super().resizeEvent(event)
        self.update_position()


# TODO: Make sure that I always have the up to date folder dictionary for the automatic comment name function
class TextInput(QtWidgets.QTextEdit):
    """
    Widget that allows to add new comment in the form of md files to the currently selected folder.

    Contains a button for saving and a text edit to write the comment.

    :param path: The Path of the folder where the file should be saved.
    """
    def __init__(self, path: Path, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.path = path

        self.save_button = TextInputFloatingButton(parent=self)
        self.save_button.hide()

        self.save_button.clicked.connect(self.create_md_file)
        self.document().contentsChanged.connect(self.size_change)

        # Arbitrary threshold height.
        self.max_threshold_height = 211
        self.min_threshold_height = 45
        self.size_change()

    def create_md_file(self) -> None:
        """
        Saves the new comment in a new md file.

        When the user clicks the save button a dialog appears to input name. A default name is selected based on the
        number of md files that already exists in that folder.
        """
        current_text = self.toPlainText()
        t = time.localtime()

        time_str = time.strftime(TIMESTRFORMAT, t)
        dialog_text, response = QtWidgets.QInputDialog.getText(self, "Input comment name", "Name:",)

        if response:
            if dialog_text[-3:] != '.md':
                if dialog_text == '':
                    dialog_text = time_str + '.md'
                else:
                    dialog_text = time_str + '_' + dialog_text + '.md'
            try:
                comment_path = self.path.joinpath(dialog_text)
                if not comment_path.is_file():
                    with open(comment_path, 'w') as file:
                        file.write(current_text)
                    self.setText('')
                else:
                    error_msg = QtWidgets.QMessageBox()
                    error_msg.setText(f"File: {comment_path} already exists, please select a different file name.")
                    error_msg.setWindowTitle(f'Error trying to save comment.')
                    error_msg.exec_()

            except Exception as e:
                # Show the error message
                error_msg = QtWidgets.QMessageBox()
                error_msg.setText(f"{e}")
                error_msg.setWindowTitle(f'Error trying to save comment.')
                error_msg.exec_()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        """
        Called every time the size of the widget changes. Triggers the change in position of the floating button.
        """
        super().resizeEvent(event)
        self.save_button.update_position()

    def enterEvent(self, *args: Any, **kwargs: Any) -> None:
        super().enterEvent(*args, **kwargs)
        self.save_button.show()

    def leaveEvent(self, *args: Any, **kwargs: Any) -> None:
        super().enterEvent(*args, **kwargs)
        self.save_button.hide()

    def size_change(self) -> None:
        """
        Changes the minimum height of the widget. Gets called every time the document changes.
        """
        doc_height = round(self.document().size().height())
        if doc_height <= self.min_threshold_height:
            self.setMinimumHeight(self.min_threshold_height)
        elif doc_height <= self.max_threshold_height:
            self.setMinimumHeight(doc_height)
        elif doc_height > self.max_threshold_height:
            self.setMinimumHeight(self.max_threshold_height)

    def sizeHint(self) -> QtCore.QSize:
        super_hint = super().sizeHint()
        height = super_hint.height()
        width = super_hint.width()
        if height >= self.document().size().height():
            height = round(self.document().size().height())
        return QtCore.QSize(width, height)


class ImageViewer(QtWidgets.QLabel):
    """
    Widget to display images that scale for the space given.

    :param path_file: The path of the image.
    """
    def __init__(self, path_file: Path, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self.path = path_file

        try:
            self.pixmap_ = QtGui.QPixmap(str(path_file))
            self.original_height = self.pixmap_.height()
            self.original_width = self.pixmap_.width()
            self.setPixmap(self.pixmap_)

        # except Exception as e:
        except FileNotFoundError as e:
            self.setText(f'Image could not me displayed')
            logger().error(e)

        self.setMinimumWidth(1)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self.scale_image()

    def scale_image(self) -> None:
        """
        Scales the image, gets called every time the widget changes size.
        """
        parent = self.parent()
        assert isinstance(parent, QtWidgets.QWidget)
        parent_width = parent.width()

        self.setPixmap(self.pixmap_.scaled(parent_width, parent_width, QtCore.Qt.KeepAspectRatio))


class VerticalScrollArea(QtWidgets.QScrollArea):
    """
    Custom QScrollArea. Allows for only vertical scroll instead of vertical and horizontal.
    """
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.first_scroll = False
        self.scroll_height = 0

        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)
        # self.verticalScrollBar().actionTriggered.connect(self.on_action_triggered)
        self.verticalScrollBar().rangeChanged.connect(self.on_range_changed)

    def eventFilter(self, a0: QtCore.QObject, a1: QtCore.QEvent) -> bool:
        self.setMinimumWidth(self.widget().minimumSizeHint().width())
        return super().eventFilter(a0, a1)
    
    @Slot(int)
    def on_range_changed(self) -> None:
        if self.first_scroll is True:
            bar = self.verticalScrollBar()
            if bar is not None:
                if bar.maximum() > 0 and bar.maximum() >= self.scroll_height:
                    bar.setValue(self.scroll_height)
                    self.first_scroll = False
    
    def viewportEvent(self, a0: QtCore.QEvent) -> bool:
        ret = super().viewportEvent(a0)
        return ret

class TagLabel(QtWidgets.QWidget):
    """
    Widget that displays the tags passed in the argument. The tags will each be displayed in a different color.

    :param tags: List of each tag that should be displayed.
    :param tree_item: Indicates if this widget is used on the right side of the app or in the treeWidget.
    """

    def __init__(self, tags: List[str], tree_item: bool = False, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self.tags = tags
        self.html_tags: List[str] = []
        self.tree_item = tree_item
        self.tags_str = ''

        if not tags:
            self.tags_str = 'No labels present.'
        else:
            self.generate_tag_string()

        self.tags_label = QtWidgets.QLabel(self.tags_str, parent=self)

        # Final underscore fixes mypy errors.
        self.layout_ = QtWidgets.QVBoxLayout()

        if not self.tree_item:
            self.tags_label.setWordWrap(True)
            self.header_label = QtWidgets.QLabel('This is tagged by:', parent=self)
            self.layout_.addWidget(self.header_label)
            self.tags_label.setIndent(30)

        self.layout_.addWidget(self.tags_label)

        self.setLayout(self.layout_)

        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        self.setSizePolicy(size_policy)

    def add_tag(self, tag: str) -> None:
        """
        Adds a new tag to the list.

        :param tag: The new tag.
        """
        self.tags.append(tag)
        self.generate_tag_string()
        if self.tree_item:
            self.tags_label.setText(self.tags_str)

    def delete_tag(self, tag: str) -> None:
        """
        Deletes a tag.

        :param tag: The deleted tag.
        """
        if tag in self.tags:
            self.tags.remove(tag)

        self.generate_tag_string()
        if self.tree_item:
            self.tags_label.setText(self.tags_str)

    def generate_tag_string(self) -> None:
        """
        Converts the list of tags into the html formated string.
        """
        self.tags_str = ''
        self.html_tags = []
        color_generator = html_color_generator()

        # Add every tag followed by a coma, except the last item.
        for i in range(len(self.tags) - 1):
            html_str = f'<font color={next(color_generator)}>{self.tags[i]}, </font>'
            self.html_tags.append(html_str)

        # Last item is followed by a dot instead of a coma.
        html_str = f'<font color={next(color_generator)}>{self.tags[-1]}.</font>'
        self.html_tags.append(html_str)

        self.tags_str = ''.join(self.html_tags)


class ItemTagLabel(QtWidgets.QLabel):
    """
    Qlabel wisget used in the FileTree to display the tags in an item of the model.

    :param tags: List with the tags that should be displayed.
    """

    def __init__(self, tags: List[str], *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.tags = tags.copy()
        self.tags_str = ""
        self.html_tags: List[str] = []
        self.generate_tag_string()
        self.setText(self.tags_str)

    def add_tag(self, tag: str) -> None:
        """
        Adds a new tag to the list.

        :param tag: The new tag.
        """
        if tag not in self.tags:
            self.tags.append(tag)
            self.generate_tag_string()
            self.setText(self.tags_str)

    def delete_tag(self, tag: str) -> None:
        """
        Deletes a tag.

        :param tag: The deleted tag.
        """
        if tag in self.tags:
            self.tags.remove(tag)

        self.generate_tag_string()
        self.setText(self.tags_str)


    def generate_tag_string(self) -> None:
        """
        Converts the list of tags into the html formated string.
        """
        self.tags_str = ''
        self.html_tags = []

        if self.tags:
            color_generator = html_color_generator()

            # Add every tag followed by a coma, except the last item.
            for i in range(len(self.tags) - 1):
                html_str = f'<font color={next(color_generator)}>{self.tags[i]}, </font>'
                self.html_tags.append(html_str)

            # Last item is followed by a dot instead of a coma.
            html_str = f'<font color={next(color_generator)}>{self.tags[-1]}.</font>'
            self.html_tags.append(html_str)

            self.tags_str = ''.join(self.html_tags)


class TagCreator(QtWidgets.QLineEdit):
    """
    A QLineEdit that allows for the creation of tags in the selected folder.

    Multiple tags can be created simultaneously by separating them with commas.
    """

    def __init__(self, current_folder_path: Path, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self.current_folder_path = current_folder_path
        self.setPlaceholderText('Create new tags')

        self.returnPressed.connect(self.create_new_tags)

    @Slot()
    def create_new_tags(self) -> None:
        """
        Gets called when the TagCreator is being selected and the user presses enter. Creates the tags that are
        currently in the TagCreator.
        """
        text = self.text()

        raw_text = text.split(',')
        text_with_empty_spaces = [item[1:] if len(item) >= 1 and item[0] == " " else item for item in raw_text]
        new_tags = [item for item in text_with_empty_spaces if item != '' and item != ' ']

        for tag in new_tags:
            tag_path = self.current_folder_path.joinpath(f'{tag}.tag')
            if not tag_path.exists():
                f = open(tag_path, 'x')

        self.setText('')


class Monitr(QtWidgets.QMainWindow):
    def __init__(self, monitorPath: str = '.',
                 parent: Optional[QtWidgets.QMainWindow] = None):
        super().__init__(parent=parent)

        # Instantiating variables.
        self.monitor_path = monitorPath
        self.current_selected_folder = Path()
        self.previous_selected_folder = Path()
        self.collapsed_state_dictionary: Dict[Path, bool] = {}
        self.setWindowTitle('Monitr')

        self.model = FileModel(self.monitor_path, 0, 2)
        self.model.update_me.connect(self.on_update_right_side_window)
        self.proxy_model = SortFilterProxyModel(parent=self)  # Used for filtering.
        self.proxy_model.setSourceModel(self.model)

        # Setting up main window
        self.main_partition_splitter = QtWidgets.QSplitter()
        self.setCentralWidget(self.main_partition_splitter)

        # Set left side layout
        self.left_side_layout = QtWidgets.QVBoxLayout()
        self.left_side_dummy_widget = QtWidgets.QTreeWidget()
        self.left_side_dummy_widget.setLayout(self.left_side_layout)

        left_side_dummy_size_ploicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                                                          QtWidgets.QSizePolicy.Preferred)
        left_side_dummy_size_ploicy.setHorizontalStretch(1)
        left_side_dummy_size_ploicy.setVerticalStretch(0)
        self.left_side_dummy_widget.setSizePolicy(left_side_dummy_size_ploicy)

        # Load left side layout
        self.file_explorer = FileExplorer(proxy_model=self.proxy_model, parent=self.left_side_dummy_widget)
        self.left_side_layout.addWidget(self.file_explorer)

        # When the refresh button of the file explorer is pressed, refresh the model
        self.file_explorer.refresh_button.clicked.connect(self.model.refresh_model)
        self.file_explorer.file_tree.selection_changed.connect(self.on_current_item_selection_changed)

        # Right side items
        self.right_side_dummy_widget = QtWidgets.QWidget()
        self.right_side_layout = QtWidgets.QVBoxLayout()
        self.right_side_dummy_widget.setLayout(self.right_side_layout)

        self.data_window: Optional[Collapsible] = None
        self.text_input: Optional[Collapsible] = None
        self.file_windows: List[Collapsible] = []
        self.scroll_area: Optional[VerticalScrollArea] = None
        self.tags_label: Optional[TagLabel] = None
        self.tags_creator: Optional[TagCreator] = None
        self.invalid_data_label: Optional[QtWidgets.QLabel] = None

        # Debug items
        self.debug_layout = QtWidgets.QHBoxLayout()
        self.model_button = QtWidgets.QPushButton(f'Print model data')
        self.model_main_dictionary_button = QtWidgets.QPushButton('Print model main dictionary')
        self.extra_action_button = QtWidgets.QPushButton('Extra action')  # For when you want to trigger a specific thing.
        self.debug_layout.addWidget(self.model_button)
        self.debug_layout.addWidget(self.model_main_dictionary_button)
        self.debug_layout.addWidget(self.extra_action_button)
        self.model_button.clicked.connect(self.print_model_data)
        self.model_main_dictionary_button.clicked.connect(self.print_model_main_dictionary)
        self.extra_action_button.clicked.connect(self.extra_action)
        self.left_side_layout.addLayout(self.debug_layout)


        self.main_partition_splitter.addWidget(self.left_side_dummy_widget)

    def print_model_data(self) -> None:
        """
        Debug function, goes through the model, creates a dictionary with the info and prints it.
        """

        def create_inner_dictionary(item: Item) -> Dict:
            step_dictionary: dict = {}
            if item.hasChildren():
                n_children = item.rowCount()
                for j in range(n_children):
                    child = item.child(j, 0)
                    assert isinstance(child, Item)
                    child_dictionary = create_inner_dictionary(child)
                    step_dictionary[child.path.name] = child_dictionary

            step_dictionary['files'] = item.files
            step_dictionary['star'] = item.star
            step_dictionary['trash'] = item.trash
            return step_dictionary

        print('==================================================================================')
        n_rows = self.model.rowCount()
        print(f'The model has {n_rows} rows')

        printable_dict = {}
        for i in range(n_rows):
            main_item = self.model.item(i, 0)
            assert isinstance(main_item, Item)
            item_dictionary = create_inner_dictionary(main_item)
            assert isinstance(main_item.path, Path)
            printable_dict[main_item.path.name] = item_dictionary
        print(f'here comes the dictionary')
        pprint.pprint(printable_dict)


    def print_model_main_dictionary(self) -> None:
        """
        Prints the main dictionary.
        """
        print('---------------------------------------------------------------------------------')
        print(f'Here comes the model main dictionary')
        pprint.pprint(self.model.main_dictionary)
        print(f'the length of the items in the main dictionary is: {len(self.model.main_dictionary)}')

    def extra_action(self) -> None:
        """
        Miscellaneous button action. Used to trigger any specific action during testing.
        """
        print(f'NOTHING HAPPENS HERE IS EMPTY SPACE')
        print(f'\n \n \n \n \n \n \n \n \n \n \n \n .')


    @Slot(QtCore.QModelIndex, QtCore.QModelIndex)
    def on_current_item_selection_changed(self, current: QtCore.QModelIndex, previous: QtCore.QModelIndex) -> None:
        """
        Gets called everytime the selected item gets changed. Converts the model index from the proxy sorting model,
        into an index from self.model and gets the current and previous item. Triggers the right side window creation.

        :param current: QModelIndex of the proxy model of the currently selected item.
        :param previous: QModelIndex of the proxy model of the previously selected item.
        """
        # When the user clicks on column 1, converts those items to their siblings at column 0
        # (the one were all the data is)
        if current.column() == 1:
            current = current.siblingAtColumn(0)
        if previous.column() == 1:
            previous = previous.siblingAtColumn(0)

        current_model_index = self.proxy_model.mapToSource(current)
        previous_model_index = self.proxy_model.mapToSource(previous)

        current_item = self.model.itemFromIndex(current_model_index)
        previous_item = self.model.itemFromIndex(previous_model_index)

        if current_item is not None:
            assert isinstance(current_item, Item)
            self.current_selected_folder = current_item.path
            self.model.update_currently_selected_folder(self.current_selected_folder)
            # The first time the user clicks on a folder, the previous item is None.
            if previous_item is not None:
                assert isinstance(previous_item, Item)
                self.previous_selected_folder = previous_item.path

            self.generate_right_side_window()

    def generate_right_side_window(self) -> None:
        """
        Generates the right side window. Clears the window first, gets all the necesary data and loads all of the
        widgets.
        """
        # Check that the folder passed is a dataset.
        if self.current_selected_folder in self.model.main_dictionary:

            # If it's the first time, create the right side scroll area and add it to the splitter.
            if self.scroll_area is None:
                self.scroll_area = VerticalScrollArea()
                self.scroll_area.setWidget(self.right_side_dummy_widget)
                self.main_partition_splitter.addWidget(self.scroll_area)

            self.clear_right_layout()
            files_meta = self.gather_all_right_side_window_data(
                self.model.main_dictionary[self.current_selected_folder])

            self.add_tag_label(files_meta['tag_labels'])
            self.add_data_window(files_meta['data_files'])
            self.add_text_input(self.current_selected_folder)
            self.add_all_files(files_meta['extra_files']['paths'], files_meta['extra_files']['names'], files_meta['extra_files']['type'])

            # Sets the stretch factor so when the main window expands, the files get the extra real-state instead
            # of the file tree
            self.main_partition_splitter.setStretchFactor(0, 0)
            self.main_partition_splitter.setStretchFactor(1, 255)

            current_item = self.model.main_dictionary[self.current_selected_folder]
            assert self.scroll_area is not None
            self.scroll_area.scroll_height = current_item.scroll_height
            self.scroll_area.first_scroll = True

    def clear_right_layout(self) -> None:
        """
        Records the scroll height of the previous item if the scroll bar exists. Then clears every item on the right side of the screen.
        """
        if self.previous_selected_folder != Path() and self.scroll_area is not None:
            bar = self.scroll_area.verticalScrollBar()
            if bar is not None:
                previous_item = self.model.main_dictionary[self.previous_selected_folder]
                previous_item.scroll_height = bar.value()

        if self.tags_label is not None:
            self.right_side_layout.removeWidget(self.tags_label)
            self.tags_label.deleteLater()
            self.tags_label = None

        if self.tags_creator is not None:
            self.right_side_layout.removeWidget(self.tags_creator)
            self.tags_creator.deleteLater()
            self.tags_creator = None

        if self.data_window is not None:
            self.right_side_layout.removeWidget(self.data_window)
            self.data_window.deleteLater()
            self.data_window = None

        if self.invalid_data_label is not None:
            self.right_side_layout.removeWidget(self.invalid_data_label)
            self.invalid_data_label.deleteLater()
            self.invalid_data_label = None

        if self.text_input is not None:
            self.right_side_layout.removeWidget(self.text_input)
            self.text_input.deleteLater()
            self.text_input = None

        if len(self.file_windows) >= 1:
            # Save the collapsed state before deleting them.
            current_collapsed_state = {window.widget.path: window.btn.isChecked() for window in self.file_windows if  # type: ignore[attr-defined] # The hasattr already checks if the widget has a path attribute.
                                       hasattr(window.widget,
                                               'path')}

            self.collapsed_state_dictionary.update(current_collapsed_state)

            for window in self.file_windows:
                self.right_side_layout.removeWidget(window)
                window.deleteLater()
            self.file_windows = []

    @classmethod
    def gather_all_right_side_window_data(cls, item: Item) ->\
            dict:
        """
        Static method used to create a dictionary with all the necessary information (file names, paths, etc.)
         of an item of the model to create the right side window. This function will also go through all the children the item might have, and add the
         names of each nested folders in front of the windows titles. Utilizes 2 helper functions to do this.

        :param item: Item of the model to generate the dictionary
        :return: A dictionary with the following structure:
            return {'tag_labels': [str],
                    'data_files': {'paths': [Path],
                                   'names': [str],
                                   'data': [DataDict]},
                    'extra_files': {'paths': [Path],
                                    'names': [str],
                                    'type': [ContentType]}}
        """
        data = {'tag_labels': [],
                'data_files': {'paths': [],
                               'names': [],
                               'data': []},
                'extra_files': {'paths': [],
                                'names': [],
                                'type': []}}

        data = cls._fill_dict(data, item.files, '')

        # Get the data of all of the children.
        for i in range(item.rowCount()):
            child = item.child(i, 0)
            assert isinstance(child, Item)
            data = cls._check_children_data(child, data, 1)
        return data

    @classmethod
    def _fill_dict(cls, data_in: dict, files_dict: Dict[Path, ContentType], prefix_text: str) -> dict:
        """
        Helper method for gather_all_right_sice_window_data. Fills in the data dictionary with the files inside of
        files_dict and adds prefix text to all tittles.

        :param data_in: Dictionary with the same structure as the data dictionary of gather_all_right_sice_window_data.
        :param files_dict: Dictionary with Path of files as keys and their ContentType as values.
        :param prefix_text: String to add to the front of the titles for the widgets. Used to specify from which
            specific nested folder this file is coming from.
        :return: data_in with the files of files_dict in it.
        """

        for file, file_type in files_dict.items():
            if file_type == ContentType.tag:
                data_in['tag_labels'].append(prefix_text + str(file.stem))
            elif file_type == ContentType.data:
                data_in['data_files']['paths'].append(file)
                data_in['data_files']['names'].append(prefix_text + str(file.stem))
                # There might be an error with the ddh5 trying to be loaded.
                try:
                    data_dict = datadict_from_hdf5(str(file))
                    data_in['data_files']['data'].append(data_dict)
                except Exception as e:
                    logger().error(f'Failed to load the data file: {file} \n {e}')
            elif file_type == ContentType.json or file_type == ContentType.md or file_type == ContentType.image:
                data_in['extra_files']['paths'].append(file)
                data_in['extra_files']['names'].append(prefix_text + str(file.name))
                data_in['extra_files']['type'].append(file_type)
        return data_in

    @classmethod
    def _check_children_data(cls, child_item: Item, data_in: dict, deepness: int) -> dict:
        """
        Helper function for gather_all_right_side_window_data. Fills the data_in dictionary with the files of
         child_item and all of its children. Returns the filled dictionary with the information of child_item and all

        :param child_item: Item for which files and children the data should be gathered.
        :param data_in: Already partially filled dictionary with the parent data. Same structure as data from
            gather_all_right_side_window_data
        :param deepness: int marking the level of recursion. If calling this function for the first level children of an
            item should be 1, for the children of the first children should be 2 and so on.
        :return: data_in with the data of all of the children.
        """

        child_path = child_item.path
        prefix_text = ''
        # Make the prefix text. Should be all the parent folders until the original parent item.
        for i in range(deepness):
            prefix_text = child_path.parts[-i - 1] + '/' + prefix_text

        data_in = cls._fill_dict(data_in, child_item.files, prefix_text)

        for i in range(child_item.rowCount()):
            child = child_item.child(i, 0)
            assert isinstance(child, Item)
            data_in = cls._check_children_data(child, data_in, deepness + 1)

        return data_in

    def add_tag_label(self, tags: List[str]) -> None:
        """
        Add the tags present in the folder selected.

        :param path: List with the tags that should be displayed.
        """
        self.tags_label = TagLabel(tags)
        self.tags_creator = TagCreator(self.current_selected_folder)
        self.right_side_layout.addWidget(self.tags_label)
        self.right_side_layout.addWidget(self.tags_creator)

    def add_data_window(self, data_files: Dict) -> None:
        """
        Creates the widget to display the data.

        :param data_files: Dictionary containing all the information required to load all ddh5 files. The dictionary
            should contain 3 different items with they keys being: "paths", "names", and "data", each containing a list
            of (in order): Path, str, DataDict. All 3 lists should be ordered by index (meaning for example that index
            number 3 represents a single datadicts). E.g.:
                incoming_data = {"paths": [Path(r"~/data/measurement_1"),
                                           Path(r"~/data/measurement_2"),],
                                 "names": ["measurement_1/data",
                                           "measurement_2/data],
                                 "data": [{'__creation_time_sec__': 1641938645.0,
                                           '__creation_time_str__': '2022-01-11 16:04:05',
                                           'x': {'__creation_time_sec__': 1641938645.0,
                                                 '__creation_time_str__': '2022-01-11 16:04:05',
                                                 '__shape__': (1444, 1444),
                                                 'axes': [],
                                                 'label': '',
                                                 'unit': '',
                                                 'values': array([[-721.68783649, ....]]) ...
        """
        # Checks that there is data to display, if not just create a Qlabel indicating that there is no valid data.
        if len(data_files['data']) < 1:
                self.invalid_data_label = QtWidgets.QLabel(f'No data to display.')
                self.right_side_layout.addWidget(self.invalid_data_label)
                return

        self.data_window = Collapsible(DataTreeWidget(data_files['paths'], data_files['names'], data_files['data']),
                                       'Data Display')
        assert isinstance(self.data_window.widget, DataTreeWidget)
        self.data_window.widget.plot_requested.connect(self.on_plot_data)

        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.data_window.setSizePolicy(size_policy)

        self.right_side_layout.addWidget(self.data_window)

    @Slot(Path)
    def on_plot_data(self, path: Path) -> None:
        """
        Gets called when the user clicks plot on the context menu of the data viewer. Opens an autoplot app for the
        selected ddh5 file.

        :param path: The path of the ddh5 file that should be displayed.
        :return:
        """
        plot_app = 'plottr.apps.autoplot.autoplotDDH5'
        process = launchApp(plot_app, str(path), 'data')

    def add_text_input(self, path: Path) -> None:
        """
        Adds the widget to add a comment in the selected folder.

        :param path: The path of the folder being selected
        """
        self.text_input = Collapsible(TextInput(path), title='Add Comment:')
        self.right_side_layout.addWidget(self.text_input)

    def add_all_files(self, paths: List[Path], names: List[str], type: List[ContentType]) -> None:
        """
        Adds all other md, json or images files on the right side of the screen.

        :param file_dict: Dictionary containing 3 lists with the required infromation of all the files that should
            be displayed in the right side window. The items of the 3 lists should be ordered such that a specific
            index referes to the same file in all 3 lists. The format looks like this:
                'extra_files': {'paths': [Path],
                                'names': [str],
                                'type': [ContentType]}
        """
        for file, name, file_type in zip(paths, names, type):
            if file_type == ContentType.json:

                expand = False
                if file in self.collapsed_state_dictionary:
                    expand = self.collapsed_state_dictionary[file]
                json_view = Collapsible(widget=JsonTreeView(path=file), title=name, expanding=expand)
                json_view.widget.setVisible(expand)
                json_view.btn.setChecked(expand)
                if expand:
                    json_view.btn.setText(json_view.expandedTitle)
                else:
                    json_view.btn.setText(json_view.collapsedTitle)

                json_model = JsonModel(json_view)
                assert isinstance(json_view.widget, JsonTreeView)
                json_view.widget.setModel(json_model)

                with open(file) as json_file:
                    json_model.load(json.load(json_file))

                for i in range(len(json_model._headers)):
                    json_view.widget.resizeColumnToContents(i)

                self.file_windows.append(json_view)
                self.right_side_layout.addWidget(json_view)

            elif file_type == ContentType.md:
                expand = True
                if file in self.collapsed_state_dictionary:
                    expand = self.collapsed_state_dictionary[file]
                plain_text_edit = Collapsible(widget=TextEditWidget(path=file),
                                              title=name, expanding=expand)

                plain_text_edit.widget.setVisible(expand)
                plain_text_edit.btn.setChecked(expand)
                if expand:
                    plain_text_edit.btn.setText(plain_text_edit.expandedTitle)
                else:
                    plain_text_edit.btn.setText(plain_text_edit.collapsedTitle)

                self.file_windows.append(plain_text_edit)
                self.right_side_layout.addWidget(plain_text_edit)

            elif file_type == ContentType.image:
                expand = True
                if file in self.collapsed_state_dictionary:
                    expand = self.collapsed_state_dictionary[file]
                label = Collapsible(ImageViewer(file, parent=self.right_side_dummy_widget),
                                    title=name, expanding=expand)
                label.widget.setVisible(expand)
                label.btn.setChecked(expand)
                if expand:
                    label.btn.setText(label.expandedTitle)
                else:
                    label.btn.setText(label.collapsedTitle)
                self.file_windows.append(label)
                self.right_side_layout.addWidget(label)

    @Slot(Path)
    def on_update_right_side_window(self, path: Path) -> None:
        """
        Gets called everytime the model emits the update_me signal. This happen when the model thinks the right side
        window should be changed. The method checks if the path of the item that has the change is related to the
        currently selected one.

        :param path: The path of the item that has changed.
        """
        if path.is_relative_to(self.current_selected_folder):
            self.generate_right_side_window()


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
