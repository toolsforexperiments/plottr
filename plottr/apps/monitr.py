""" plottr.monitr -- a GUI tool for monitoring data files.
"""
import sys
import os
import argparse
import time
import importlib

import logging
import re
import pprint
import json
from enum import Enum, auto
from pathlib import Path
from multiprocessing import Process
from typing import List, Optional, Dict, Any, Union, Generator, Iterable
from functools import partial
from itertools import cycle

from watchdog.events import FileSystemEvent

from .. import log as plottrlog
from .. import QtCore, QtWidgets, Signal, Slot, QtGui
from ..data.datadict_storage import all_datadicts_from_hdf5, datadict_from_hdf5
from ..utils.misc import unwrap_optional
from ..apps.watchdog_classes import WatcherClient
from ..gui.widgets import Collapsible
from .json_veiwer import JsonModel
from ..icons import get_starIcon as get_star_icon, get_trashIcon as get_trash_icon

from .ui.Monitr_UI import Ui_MainWindow

TIMESTRFORMAT = "%Y-%m-%dT%H%M%S"


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
        elif extension == 'jpg' or extension == 'jpeg' or extension == 'png':
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


class TreeWidgetItem(QtWidgets.QTreeWidgetItem):
    """
    Modified class of QtWidgets.QTreeWidgetItem where the only modification is the addition of the path parameter.

    :param path: The path this QTreeWidgetItem represents.
    :param tags: A list of the tags associated with this item.
    :param star: Indicates if this item is star.
    :param trash: Indicates if this item is trash.
    """

    def __init__(self, path: Path, tags: Optional[List[str]] = None,
                 star: bool = False, trash: bool = False, *args: Any, **kwargs: Any):
        super(TreeWidgetItem, self).__init__(*args, **kwargs)
        self.path = path
        self.star = star
        self.trash = trash

        if tags is not None:
            self.tags_widget = TagLabel(tags, True)

    def resize_tags(self, size: int) -> None:
        """
        Gets called everytime the 'Tags' column changes sizes. Set the new maximum size for the tags widget.
        """
        self.tags_widget.setMaximumWidth(size)


# TODO: Check consistency in the type of argument required for the add, delete, modified methods (if they should accept
#  only Path or also strings.
class FileTree(QtWidgets.QTreeWidget):
    """
    QTreeWidget that displays the relevant files. Addition, deletion and modification of items performed by the use of
    pathlib.Path objects.

    All QTreeWidgetItems are stored in self.main_items_dictionary where the key is the path they represent,
    and the value is the actual TreeWidgetItem.
    """
    # Signal(Path) -- Emitted when the user selects the plot option in the popup menu.
    #: Arguments:
    #:   - The path of the ddh5 with the data for the requested plot.
    plot_requested = Signal(Path)

    # Signal(Path) -- Emitted when the user clicks on an item.
    #: Arguments:
    #:   - The path that the item represents.
    item_selected = Signal(Path)

    # Signal(Path) -- Emitted when the clicks on star_popup_action.
    #: Arguments:
    #:   - The path that the item represents.
    item_starred = Signal(Path)

    # Signal(Path) -- Emitted when the clicks on trash_popup_action.
    #: Arguments:
    #:   - The path that the item represents.
    item_trashed = Signal(Path)

    def __init__(self, dic: Dict[Path, Any], monitor_path: Path,
                 parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent=parent)
        self.main_items_dictionary: Dict[Path, TreeWidgetItem] = {}
        self.monitor_path = monitor_path

        # Holds the current filtering settings.
        self.current_filter_matches = None
        self.star_filter_status = False
        self.hide_trash_status = False

        self.star_text = 'Star'
        self.un_star_text = 'Un-star'
        self.trash_text = 'Trash'
        self.un_trash_text = 'Un-trash'

        self.setColumnCount(2)
        self.setHeaderLabels(['Files', 'Tags'])
        self.refresh_tree(dic)
        self.header().swapSections(1, 0)

        # Popup menu.
        self.delete_popup_action = QtWidgets.QAction('Delete')
        self.plot_popup_action = QtWidgets.QAction('Plot')
        self.star_popup_action = QtWidgets.QAction('Star')
        self.trash_popup_action = QtWidgets.QAction('Trash')

        self.popup_menu = QtWidgets.QMenu(self)

        # Connect different signals
        self.plot_popup_action.triggered.connect(self.emit_plot_requested_signal)
        self.delete_popup_action.triggered.connect(self.delete_selected_item_from_directory)
        self.star_popup_action.triggered.connect(self.emit_item_starred)
        self.trash_popup_action.triggered.connect(self.emit_item_trashed)

        self.itemChanged.connect(self.renaming_item)
        self.itemClicked.connect(self.item_clicked)

        self.header().sectionResized.connect(self.columnResized)

    def columnResized(self, column: int, oldSize: int, newSize: int) -> None:
        """
        Gets called every time a column gets resized. Used to pass the new width to the column for correct tags
        displaying.
        """
        super().columnResized(column, oldSize, newSize)
        if column == 1:
            for item in self.main_items_dictionary.items():
                item[1].resize_tags(newSize)

    def clear(self) -> None:
        """
        Clears the tree, including the main_items_dictionary.
        """
        super().clear()
        self.main_items_dictionary = {}

    def update_filter_matches(self, fil: Optional[List[Path]] = None) -> None:
        """
        Updates current_filter_matches by converting the Path items from filter into the TreeWidgetItems they represent.
        calls filter_items afterwards.

        :param fil: List of paths that should be shown. If the list is empty, no item will be shown. If the list
            is None, everything will be shown.
        """
        filtered_objects = None
        if fil is not None:
            filtered_objects = [self.main_items_dictionary[path] for path in fil]

        self.current_filter_matches = filtered_objects
        self.filter_items()

    def refresh_tree(self, update: Dict[Path, Any]) -> None:
        """
        Deletes the entire tree and creates it again from scratch based on update.

        :param update: Dictionary with the same format as the main_dictionary in the Monitr class. The structure looks
            like::
                update = {
                    path_of_folder_1_containing_files : {
                        path_of_file_1: ContentType.sort(path_of_file_1),
                        path_of_file_2: ContentType.sort(path_of_file_2)},
                    path_of_folder_2_containing_files : {
                        path_of_file_1: ContentType.sort(path_of_file_1),
                        path_of_file_2: ContentType.sort(path_of_file_2)}
                }
        """
        start_timer = time.time_ns()
        self.clear()
        for folder_path, files_dict in update.items():
            self.sort_and_add_tree_widget_item(folder_path, files_dict)
        final_timer = time.time_ns() - start_timer
        logger().info(f'generating the tree widget took: {final_timer * 10 ** -9}s')

    def sort_and_add_tree_widget_item(self, folder_path: Union[Path, str], files_dict: Optional[Dict] = None) -> None:
        """
        Adds one or more items into the tree. The items are properly sorted and new items are created if required.

        :param folder_path: `Path` of the file or folder being added to the tree.
            Strings of the path also supported.
        :param files_dict: Optional. Used to get the tags for showing in the 'Tags' column of the tree. It will check
            for all tag file type and create the item for it. The format should be:
                {path_of_file_1: ContentType.sort(path_of_file_1),
                path_of_file_2: ContentType.sort(path_of_file_2)}
        """
        # TODO: optimize the conversion of path.
        # Check that the new file or folder are Paths, if not convert them.
        if isinstance(folder_path, str):
            folder_path = Path(folder_path)
        elif isinstance(folder_path, Path):
            folder_path = folder_path
        else:
            folder_path = Path(folder_path)

        # Check if the new item should have a parent item. If the new item should have a parent, but this does
        # not yet exist, create it.
        if folder_path.parent == self.monitor_path:
            parent_item, parent_path = None, None
        elif folder_path.parent in self.main_items_dictionary:
            parent_item, parent_path = \
                self.main_items_dictionary[folder_path.parent], folder_path.parent
        else:
            self.sort_and_add_tree_widget_item(folder_path.parent, None)
            parent_item, parent_path = \
                self.main_items_dictionary[folder_path.parent], folder_path.parent

        # Get the tags this item has.
        tags = []
        if files_dict is not None:
            tags = [key.stem for key, item in files_dict.items() if item == ContentType.tag]

        # Create the new TreeWidgetItem.
        tree_widget_item = TreeWidgetItem(folder_path, tags, False, False, [str(folder_path.name)])
        tree_widget_item.setFlags(tree_widget_item.flags() | QtCore.Qt.ItemIsEditable)

        if parent_path is None:
            self.main_items_dictionary[folder_path] = tree_widget_item
            self.insertTopLevelItem(0, tree_widget_item)
        else:
            self.main_items_dictionary[folder_path] = tree_widget_item
            tree_widget_item.setForeground(0, ContentType.sort_Qcolor(ContentType.sort(folder_path)))
            assert isinstance(parent_item, TreeWidgetItem)
            parent_item.addChild(tree_widget_item)

            # Sort the children after you add a new one.
            parent_item.sortChildren(0, QtCore.Qt.DescendingOrder)

        if len(tree_widget_item.tags_widget.tags) >= 1:
            self.setItemWidget(tree_widget_item, 1, tree_widget_item.tags_widget)
        self.resizeColumnToContents(1)
        tree_widget_item.resize_tags(self.columnWidth(1))

    def delete_item(self, path: Path) -> None:
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
                    assert isinstance(child, TreeWidgetItem)
                    self.delete_item(child.path)
            if parent_item is None:
                item_index = self.indexOfTopLevelItem(item)
                self.takeTopLevelItem(item_index)
            else:
                item.parent().removeChild(item)
            del self.main_items_dictionary[path]

    def update_item(self, old_path: Path, new_path: Path) -> None:
        """
        Updates text of a TreeWidgetItem when the name (or type) of a file or directory changes.

        :param old_path: The path of the TreeWidgetItem that needs to be updated.
        :param new_path: The new Path of the TreeWidgetItem.
        """
        if old_path in self.main_items_dictionary:
            self.main_items_dictionary[new_path] = self.main_items_dictionary.pop(old_path)
            self.main_items_dictionary[new_path].path = new_path
            self.main_items_dictionary[new_path].setText(0, str(new_path.name))
        elif old_path.parent in self.main_items_dictionary:
            tree_item = self.main_items_dictionary[old_path.parent]

            if old_path.stem in tree_item.tags_widget.tags and old_path.suffix == '.tag':
                tree_item.tags_widget.delete_tag(old_path.stem)

            if new_path.stem not in tree_item.tags_widget.tags and new_path.suffix == '.tag':
                tree_item.tags_widget.add_tag(new_path.stem)

    @Slot(QtCore.QPoint)
    def on_context_menu_requested(self, pos: QtCore.QPoint) -> None:
        """Shows the context menu when a right click happens"""
        item = self.itemAt(pos)
        if item is not None:
            assert isinstance(item, TreeWidgetItem)
            # If the item clicked is ddh5, also show the plot option.
            if ContentType.sort(item.path) == ContentType.data:
                self.popup_menu.addAction(self.plot_popup_action)
                self.popup_menu.addSeparator()
                self.popup_menu.addAction(self.delete_popup_action)
                self.popup_menu.exec_(self.mapToGlobal(pos))
                self.popup_menu.removeAction(self.plot_popup_action)
                self.popup_menu.removeAction(self.delete_popup_action)
            else:
                # Sets the text of the star and trash actions according to the state of the item clicked.
                if item.star:
                    self.star_popup_action.setText(self.un_star_text)
                else:
                    self.star_popup_action.setText(self.star_text)

                if item.trash:
                    self.trash_popup_action.setText(self.un_trash_text)
                else:
                    self.trash_popup_action.setText(self.trash_text)

                self.popup_menu.addAction(self.star_popup_action)
                self.popup_menu.addAction(self.trash_popup_action)
                self.popup_menu.addSeparator()
                self.popup_menu.addAction(self.delete_popup_action)
                self.popup_menu.exec_(self.mapToGlobal(pos))
                self.popup_menu.removeAction(self.delete_popup_action)

    def delete_selected_item_from_directory(self) -> None:
        """Gets triggered when the user clicks on the delete option of the popup menu.

        Creates a warning before deleting the file or folder. If a folder is being deleted creates a second warning.
        """
        item = self.currentItem()
        assert isinstance(item, TreeWidgetItem)
        warning_msg = QtWidgets.QMessageBox()
        ret = warning_msg.question(self, 'WARNING', f'Are you sure you want to delete: {item.path} \n '
                                                    f'This process is COMPLETELY IRREVERSIBLE. '
                                                    f'The file will NOT be possible to recover '
                                                    f'at ALL after deletion.',
                                   warning_msg.No | warning_msg.Yes)
        if ret == warning_msg.Yes:
            if item.path.is_file():
                item.path.unlink()
            if item.path.is_dir():
                second_warning = QtWidgets.QMessageBox()
                second_ret = second_warning.question(self, 'WARNING', f'{item.path} is about to be deleted with'
                                                                      f' anything inside of it. Please confirm again'
                                                                      f' you want to delete this entire directory'
                                                                      f' with all of its containing subdirectories',
                                                     second_warning.No | second_warning.Yes)
                if second_ret == second_warning.Yes:
                    self._delete_entire_folder(item.path)
                else:
                    second_warning.information(self, 'WARNING', f'folder will not be deleted.')
        else:
            warning_msg.information(self, 'WARNING', 'file will not be deleted.')

    def _delete_entire_folder(self, folder_path: Path) -> None:
        """
        Deletes every itme inside the folder_path, including any subdirectories.

        :param folder_path: The folder that is going to be deleted.
        """
        for item in folder_path.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                self._delete_entire_folder(item)
        folder_path.rmdir()

    @Slot(QtWidgets.QTreeWidgetItem, int)  # The item has to be a TreeWidget Item. It is a QTreeWidgetItem because
    # we are using a built in signal that sends a QTreeWidgetItem
    def renaming_item(self, item: QtWidgets.QTreeWidgetItem, column: int) -> None:
        """
        Triggered every time an item changes this includes the icon of the item changing.

        If the text of the item changed because the file changed name, the file gets the name changed again for the
        same name so nothing happens. If the user changes the name in the GUI, the file or folder gets the name changed
        and that triggers the watchdog event that updates the rest of the program. If an error while changing the name
        happens, the text is not changed and a message pops with the error. If the icon of the item changes, nothing
        happens
        """
        if column == 0:
            assert isinstance(item, TreeWidgetItem)
            new_text = item.text(column)
            path = item.path
            # Checking if either a file or folder exists for the path. If it does it mean that the change was the icon and
            # nothing happens.
            if new_text != path.name:
                try:
                    new_path = path.rename(path.parent.joinpath(new_text))
                except Exception as e:
                    # Reset the text of the item
                    self.main_items_dictionary[path].setText(0, str(path.name))
                    # Show the error message
                    error_msg = QtWidgets.QMessageBox()
                    error_msg.setText(f"{e}")
                    error_msg.setWindowTitle(f'Could not rename directory.')
                    error_msg.exec_()

    @Slot()
    def emit_plot_requested_signal(self) -> None:
        """
        Emits the signal when the user selects the plot option in the popup menu. The signal is emitted with the Path of
        the current selected item as an argument.
        """
        current_item = self.currentItem()
        assert isinstance(current_item, TreeWidgetItem)
        self.plot_requested.emit(current_item.path)

    @Slot(QtWidgets.QTreeWidgetItem, int)
    def item_clicked(self, item: QtWidgets.QTreeWidgetItem, column: int) -> None:
        """
        Gets called every time the user clicks on an item. Emits item_selected signal.
        """
        assert isinstance(item, TreeWidgetItem)
        self.item_selected.emit(item.path)

    @Slot()
    def emit_item_starred(self) -> None:
        """
        Emits item_starred Signal.
        """
        current_item = self.currentItem()
        assert isinstance(current_item, TreeWidgetItem)
        self.item_starred.emit(current_item.path)

    @Slot()
    def emit_item_trashed(self) -> None:
        """
        Emits item_trashed Signal.
        """
        current_item = self.currentItem()
        assert isinstance(current_item, TreeWidgetItem)
        self.item_trashed.emit(current_item.path)

    def star_item(self, path: Path) -> None:
        """
        Changes the star status of the item in path.

        If the item is un-starred, stars the item if the item is not already trash and changes its icon. If the item
        is starred, un-stars the item and changes the icon if the item is not already trash. Triggers a check for its
        parent item and a filter_items.

        :param path: The path of the item whose star status should change
        """
        if path in self.main_items_dictionary:
            item = self.main_items_dictionary[path]
            if item.star:
                item.star = False
                if not item.trash:
                    item.setIcon(1, QtGui.QIcon())

            else:
                if not item.trash:
                    item.star = True
                    item.setIcon(1, get_star_icon())

            if path.parent in self.main_items_dictionary:
                self.star_parent_item(path)
            self.filter_items()

    def star_parent_item(self, path: Path) -> None:
        """
        Checks if the parent of the path should be starred.

        The parent of the path should only be starred if all of its children are starred too. If they are, star the path
        parent and change its icon. If they are not, un-star the item and change its icon if it's not already trash.

        :param path: The path of the child of the item we should check. It checks the parent of the path, not the
            path itself.
        """
        item = self.main_items_dictionary[path.parent]

        # the next 4 lines (not counting comments) can be simplified to a single list comprehension but mypy complains
        # because we have no way of checking that the childs are TreeWidgetItem instead of QTreeWidgetItem.
        children = [item.child(i) for i in range(item.childCount())]
        children_star = []
        for child in children:
            assert isinstance(child, TreeWidgetItem)
            children_star.append(child.star)

        if all(children_star):
            item.star = True
            item.setIcon(1, get_star_icon())
        else:
            item.star = False
            if not item.trash:
                item.setIcon(1, QtGui.QIcon())

        parent_item = item.parent()
        if parent_item is not None:
            self.star_parent_item(path.parent)

    def trash_item(self, path: Path) -> None:
        """
        Changes the trash status of the item in path.

        If the item is un-trashed, trashes the item if the item is not already starred and changes its icon. If the item
        is trash, un-trash the item and changes the icon if the item is not already starred. Triggers a check for its
        parent item and a filter_items.

        :param path: The path of the item whose star status should change
        """
        if path in self.main_items_dictionary:
            item = self.main_items_dictionary[path]
            if item.trash:
                item.trash = False
                if not item.star:
                    item.setIcon(1, QtGui.QIcon())
            else:
                if not item.star:
                    item.trash = True
                    item.setIcon(1, get_trash_icon())

            self.trash_parent_item(path)
            self.filter_items()

    def trash_parent_item(self, path: Path) -> None:
        """
        Checks if the parent of the path should be trashed.

        The parent of the path should only be trashed if all of its children are trashed too. If they are,
        trash the path parent and change its icon. If they are not, un-trash the item and change its icon if it's not
        already star.

        :param path: The path of the child of the item we should check. It checks the parent of the path, not the
            path itself.
        """
        item = self.main_items_dictionary[path.parent]

        # the next 4 lines (not counting comments) can be simplified to a single list comprehension but mypy complains
        # because we have no way of checking that the childs are TreeWidgetItem instead of QTreeWidgetItem.
        children = [item.child(i) for i in range(item.childCount())]
        children_trash = []
        for child in children:
            assert isinstance(child, TreeWidgetItem)
            children_trash.append(child.trash)

        if all(children_trash):
            item.trash = True
            item.setIcon(1, get_trash_icon())
        else:
            item.trash = False
            if not item.star:
                item.setIcon(1, QtGui.QIcon())

        parent_item = item.parent()
        if parent_item is not None:
            self.trash_parent_item(path.parent)

    def update_filter_status(self, star_status: bool = False, trash_status: bool = False) -> None:
        """
        Update the filter status variables and triggers a filtering of items.

        :param star_status: The status of the star button.
        :param trash_status: The status of the trash button.
        """
        self.star_filter_status = star_status
        self.hide_trash_status = trash_status

        self.filter_items()

    def filter_items(self) -> None:
        """
        Filters the items according to the status of the star and trash buttons and the filter line edit.

        Checks each possible case and filters appropriately. For text matches, shows all children and parents of the
        match.
        """
        if not self.star_filter_status and not self.hide_trash_status:
            if self.current_filter_matches is None:
                for item in self.main_items_dictionary.values():
                    item.setHidden(False)
            else:
                for item in self.main_items_dictionary.values():
                    if item in self.current_filter_matches:
                        self._show_parent_item(item)
                        children = [item.child(i) for i in range(item.childCount())]
                        for child in children:
                            self._show_child_item(child)
                    else:
                        item.setHidden(True)

        elif self.star_filter_status and not self.hide_trash_status:
            if self.current_filter_matches is None:
                for item in self.main_items_dictionary.values():
                    if item.star:
                        self._show_parent_item(item)
                    else:
                        item.setHidden(True)
            else:
                for item in self.main_items_dictionary.values():
                    if item in self.current_filter_matches and item.star:
                        self._show_parent_item(item)
                        children = [item.child(i) for i in range(item.childCount())]
                        for child in children:
                            self._show_child_item(child)
                    else:
                        item.setHidden(True)

        elif not self.star_filter_status and self.hide_trash_status:
            if self.current_filter_matches is None:
                for item in self.main_items_dictionary.values():
                    if item.trash:
                        item.setHidden(True)
                    else:
                        item.setHidden(False)
            else:
                for item in self.main_items_dictionary.values():
                    if item in self.current_filter_matches and not item.trash:
                        self._show_parent_item(item)
                        children = [item.child(i) for i in range(item.childCount())]
                        for child in children:
                            self._show_child_item(child)
                    else:
                        item.setHidden(True)

        elif self.star_filter_status and self.hide_trash_status:
            if self.current_filter_matches is None:
                for item in self.main_items_dictionary.values():
                    if item.star:
                        self._show_parent_item(item)
                    else:
                        item.setHidden(True)
            else:
                for item in self.main_items_dictionary.values():
                    if item in self.current_filter_matches and item.star and not item.trash:
                        self._show_parent_item(item)
                        children = [item.child(i) for i in range(item.childCount())]
                        for child in children:
                            self._show_child_item(child)
                    else:
                        item.setHidden(True)

    def _show_child_item(self, item: QtWidgets.QTreeWidgetItem) -> None:
        """
        Helper recursive function to the item passed and all of its children.

        :param item: The item that we want to show.
        """
        if item.childCount() == 0:
            item.setHidden(False)
        else:
            item.setHidden(False)
            for i in range(item.childCount()):
                self._show_child_item(item.child(i))

    def _show_parent_item(self, item: QtWidgets.QTreeWidgetItem) -> None:
        """
        Helper recursive function to the item passed and all of its parents.

        :param item: The item that we want to show.
        """
        if item.parent() is None:
            item.setHidden(False)
        else:
            item.setHidden(False)
            self._show_parent_item(item.parent())

    def new_tag_created(self, path: Path) -> None:
        """
        Adds the tag to the correct tree_item tag widget and displays it.

        :param path: The path of the new tag.
        """
        if path.parent in self.main_items_dictionary:
            tree_item = self.main_items_dictionary[path.parent]
            tree_item.tags_widget.add_tag(path.stem)

    def tag_deleted(self, path: Path) -> None:
        """
        Deletes a tag that was in the correct tree_item tag widget.

        :param path: The path of the deleted tag.
        """
        if path.parent in self.main_items_dictionary:
            tree_item = self.main_items_dictionary[path.parent]
            tree_item.tags_widget.delete_tag(path.stem)


class FileExplorer(QtWidgets.QWidget):
    """
    Helper widget to unify the FileTree with the line edit and status buttons.
    """

    def __init__(self, dic:  Dict[Path, Any], monitor_path: Path,
                 *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self.file_tree = FileTree(dic, monitor_path, parent=self)
        self.monitor_path = monitor_path

        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.filter_and_buttons_layout = QtWidgets.QHBoxLayout()

        self.filter_line_edit = QtWidgets.QLineEdit()
        self.filter_line_edit.setPlaceholderText('Filter Items')

        self.star_button = QtWidgets.QPushButton('Star')
        self.trash_button = QtWidgets.QPushButton('Hide Trash')

        self.star_button.setCheckable(True)
        self.trash_button.setCheckable(True)

        self.filter_and_buttons_layout.addWidget(self.filter_line_edit)
        self.filter_and_buttons_layout.addWidget(self.star_button)
        self.filter_and_buttons_layout.addWidget(self.trash_button)
        self.main_layout.addLayout(self.filter_and_buttons_layout)
        self.main_layout.addWidget(self.file_tree)

        self.file_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self.file_tree.on_context_menu_requested)
        self.star_button.clicked.connect(self.star_button_clicked)
        self.trash_button.clicked.connect(self.trash_button_clicked)

    @Slot()
    def star_button_clicked(self) -> None:
        """
        Updates the status of the buttons to the FileTree.
        """
        self.file_tree.update_filter_status(self.star_button.isChecked(), self.trash_button.isChecked())

    @Slot()
    def trash_button_clicked(self) -> None:
        """
        Updates the status of the buttons to the FileTree.
        """
        self.file_tree.update_filter_status(self.star_button.isChecked(), self.trash_button.isChecked())


# TODO: Right now the data display only updates when you click on the parent folder. What happens if data is created
#   while the folder display is open. It should absolutely update.
class DataTreeWidget(QtWidgets.QTreeWidget):
    """
    Widget that displays the data of all ddh5 files inside a folder.

    Displays all basic metadata of each ddh5 file. Also opens a popup menu in the ddh5 parent item to plot it.
    """

    # Signal(Path) -- Emitted when the user selects the plot option in the popup menu.
    #: Arguments:
    #:   - The path of the ddh5 with the data for the requested plot.
    plot_requested = Signal(Path)

    def __init__(self, data_paths: List[Path], *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        header_item = self.headerItem()
        assert isinstance(header_item, QtWidgets.QTreeWidgetItem)
        header_item.setText(0, "Object")
        header_item.setText(1, "Content")
        header_item.setText(2, "Type")
        self.paths = data_paths
        self.data = [datadict_from_hdf5(str(data_file)) for data_file in self.paths]

        # Popup menu.
        self.plot_popup_action = QtWidgets.QAction('Plot')
        self.popup_menu = QtWidgets.QMenu(self)

        self.plot_popup_action.triggered.connect(self.emit_plot_requested_signal)

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.on_context_menu_requested)

        self.set_data()

        # TODO: Test if the try-except statement here is truly necessary.
        # try:
        #     self.data = [datadict_from_hdf5(str(data_file)) for data_file in self.paths]
        #     self.set_data()
        # except Exception as e:
        #     error_msg = QtWidgets.QMessageBox()
        #     error_msg.setText(f'Could not load data: \n {e}')
        #     error_msg.setWindowTitle(f'Data File Invalid.')
        #     error_msg.exec_()

    def set_data(self) -> None:
        """
        Fills the QTreeWidget with the data loaded in the self.data variable.
        """

        for index, data in enumerate(self.data):
            parent_tree_widget = TreeWidgetItem(self.paths[index], None, False, False, self, [str(self.paths[index].name)])

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

        with open(path) as file:
            self.file_text = file.read()
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
        self.pixmap_ = QtGui.QPixmap(str(path_file))
        self.original_height = self.pixmap_.height()
        self.original_width = self.pixmap_.width()
        self.setPixmap(self.pixmap_)

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

        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)

    def eventFilter(self, a0: QtCore.QObject, a1: QtCore.QEvent) -> bool:
        self.setMinimumWidth(self.widget().minimumSizeHint().width())
        return super().eventFilter(a0, a1)


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
        self.tag_str = ''

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

        # Add every tag followed by a come, except the last item.
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


class SingleFolderItem(QtWidgets.QSplitter):
    def __init__(self, folder_path, items_dictionary, parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.folder_path = folder_path
        self.items_dictionary = items_dictionary
        self.tags = [file.stem for file, file_type in items_dictionary.items() if file_type == ContentType.tag]
        self.tag_label = None
        self.items = {}
        self.children_ = []

        self.left_side_widget_dummy = QtWidgets.QWidget(parent=self)
        self.left_side_layout = QtWidgets.QVBoxLayout()
        self.left_side_widget_dummy.setLayout(self.left_side_layout)
        self.addWidget(self.left_side_widget_dummy)
        # self.left_side_widget_dummy.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)

        self.right_side_widget_dummy = QtWidgets.QWidget(parent=self)
        self.right_side_layout = QtWidgets.QVBoxLayout()
        self.right_side_widget_dummy.setLayout(self.right_side_layout)
        self.addWidget(self.right_side_widget_dummy)

        self.folder_name_label = QtWidgets.QLabel(self.folder_path.name, parent=self)
        self.folder_name_label.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        self.folder_name_label.setWordWrap(True)
        self.left_side_layout.addWidget(self.folder_name_label)

        self.tag_label = TagLabel(self.tags, parent=self)
        self.tag_label.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        self.left_side_layout.addWidget(self.tag_label)

        self.left_side_layout.addStretch()

        files = [(file, file_type) for file, file_type in self.items_dictionary.items()
                 if file_type == ContentType.json or
                 file_type == ContentType.md or
                 file_type == ContentType.image]

        # Adding extra check if multiple files get deleted at once to update with files that do exists
        files = [file for file in files if file[0].is_file()]

        files = sorted(files, key=lambda x: str.lower(x[0].name), reverse=True)

        for row, (file, file_type) in enumerate(files):
            if file_type == ContentType.md:
                text_edit = Collapsible(widget=TextEditWidget(path=file), title=file.name, parent=self)
                self.items[file] = text_edit
                self.right_side_layout.addWidget(text_edit)

            elif file_type == ContentType.image:
                image_viewer = Collapsible(widget=ImageViewer(file), title=file.name, parent=self)
                self.items[file] = image_viewer
                self.right_side_layout.addWidget(image_viewer)


class GenericParent(QtWidgets.QWidget):
    def __init__(self, path, parent_item, parent_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.path = path
        self.parent_item = parent_item
        self.parent_path = parent_path
        self.children_ = []
        self.children_separators = []

        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.setLayout(self.main_layout)

        self.separator = QtWidgets.QFrame(self)
        self.separator.setFrameShape(QtWidgets.QFrame.HLine)
        self.separator.setStyleSheet('background-color: black;')
        self.main_layout.addWidget(self.separator)

        self.name_label = QtWidgets.QLabel(self.path.name)
        self.name_label.setWordWrap(True)
        self.main_layout.addWidget(self.name_label)

    def add_child(self, item) -> None:
        self.children_.append(item)
        child_separator = QtWidgets.QFrame(self)
        self.children_separators.append(child_separator)
        child_separator.setFrameShape(QtWidgets.QFrame.HLine)
        self.main_layout.addWidget(child_separator)
        self.main_layout.addWidget(item)

    def remove_child(self, item) -> None:
        self.main_layout.removeWidget(item)
        item.deleteLater()
        self.children_.remove(item)


class AnnotationWindow(QtWidgets.QMainWindow):

    # Signal() -- Emitted when the user activates edit mode.
    splitter_moved = Signal(int, int)

    def __init__(self, incoming_update, monitor_path, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.incoming_update = incoming_update
        self.main_dictionary = {}
        self.monitor_path = monitor_path
        self.splitter_list: List[QtWidgets.QSplitter] = []
        self.splitter_pos = None
        self.current_splitter_pos = 10

        self.central_widget_dummy = QtWidgets.QWidget()
        self.main_layout = QtWidgets.QVBoxLayout()
        self.central_widget_dummy.setLayout(self.main_layout)

        self.search_bar_layout = QtWidgets.QHBoxLayout()

        self.filter_line_edit = QtWidgets.QLineEdit()
        self.filter_line_edit.setPlaceholderText('Filter Items')

        self.star_button = QtWidgets.QPushButton('Star')
        self.trash_button = QtWidgets.QPushButton('Hide Trash')

        self.star_button.setCheckable(True)
        self.trash_button.setCheckable(True)

        self.search_bar_layout.addWidget(self.filter_line_edit)
        self.search_bar_layout.addWidget(self.star_button)
        self.search_bar_layout.addWidget(self.trash_button)
        self.main_layout.addLayout(self.search_bar_layout)

        self.comments_scroll_area = VerticalScrollArea()
        self.scroll_area_dummy_widget = QtWidgets.QWidget()
        self.scroll_area_layout = QtWidgets.QVBoxLayout()
        self.scroll_area_dummy_widget.setLayout(self.scroll_area_layout)
        self.comments_scroll_area.setWidget(self.scroll_area_dummy_widget)

        for i, (keys, items) in enumerate(self.incoming_update.items()):
            self.sort_and_add_item(keys, items)

        self.main_layout.addWidget(self.comments_scroll_area)
        # self.connect_splitter_slots()

        self.splitter_list[0].splitterMoved.connect(self.on_moved_splitter)
        # self.splitter_list[0].splitterMoved.connect(self.splitter_list[1].moveSplitter)
        # self.splitter_list[1].splitterMoved.connect(self.splitter_list[0].moveSplitter)
        self.star_button.clicked.connect(self.on_star_toggle)

        # self.set_position_for_all_splitters()
        self.setCentralWidget(self.central_widget_dummy)

    def sort_and_add_item(self, path, files) -> None:
        if path.parent == self.monitor_path:
            parent_item, parent_path = None, None
        elif path.parent in self.main_dictionary:
            parent_item, parent_path = self.main_dictionary[path.parent], path.parent
        else:
            self.sort_and_add_item(path.parent, None)
            parent_item, parent_path = self.main_dictionary[path.parent], path.parent

        if files is None:
            item = GenericParent(path, parent_item, parent_path)
            if parent_item is None:
                self.scroll_area_layout.addWidget(item)

        else:
            item = SingleFolderItem(folder_path=path, items_dictionary=files, parent=parent_item)
            self.splitter_list.append(item)

        if parent_item is not None:
            parent_item.add_child(item)

        self.main_dictionary[path] = item

    def connect_splitter_slots(self) -> None:
        for splitter in self.splitter_list:
            # splitter.splitterMoved.connect(self.on_moved_splitter)
            self.splitter_moved.connect(splitter.splitterMoved)

    @Slot(int, int)
    def on_moved_splitter(self, pos: int, index: int) -> None:
        # self.splitter_moved.emit(pos, index)
        pass

    def set_position_for_all_splitters(self) -> None:
        for splitter in self.splitter_list:
            splitter.moveSplitter(self.current_splitter_pos, 1)

    @Slot()
    def on_star_toggle(self):
        self.splitter_list[1].setSizes(self.splitter_list[0].sizes())



# TODO: look over logger and start utilizing in a similar way like instrument server is being used right now.
# TODO: Test deletion of nested folder situations for large data files to see if this is fast enough.
class Monitr(QtWidgets.QMainWindow):
    def __init__(self, monitorPath: str = '.',
                 parent: Optional[QtWidgets.QMainWindow] = None):

        super().__init__(parent=parent)

        # Instantiate variables.
        self.main_dictionary: Dict[Path, Dict[Path, ContentType]] = {}
        self.collapsed_state_dictionary: Dict[Path, Dict[str, bool]] = {}
        self.monitor_path = Path(monitorPath)
        self.currently_selected_folder = None

        # Create GUI elements.

        # layout
        self.main_partition_layout = QtWidgets.QHBoxLayout()
        self.main_partition_splitter = QtWidgets.QSplitter()
        self.file_tree_layout = QtWidgets.QVBoxLayout()
        self.file_tree_dummy_widget_holder = QtWidgets.QWidget()
        self.bottom_buttons_layout = QtWidgets.QHBoxLayout()
        self.dummy_widget = QtWidgets.QWidget()
        self.annotation_window = None

        # Left side of the main window

        # Buttons
        self.expand_all_button = QtWidgets.QPushButton('Expand all')
        self.collapse_all_button = QtWidgets.QPushButton('Collapse all')
        self.refresh_button = QtWidgets.QPushButton('Refresh')
        self.annotation_window_button = QtWidgets.QPushButton('Annotation window')
        self.annotation_window_button.setCheckable(True)

        # Adding buttons to layout
        self.bottom_buttons_layout.addWidget(self.refresh_button)
        self.bottom_buttons_layout.addWidget(self.expand_all_button)
        self.bottom_buttons_layout.addWidget(self.collapse_all_button)
        self.bottom_buttons_layout.addWidget(self.annotation_window_button)

        self.file_explorer = FileExplorer(self.main_dictionary, self.monitor_path, parent=self.dummy_widget)
        self.tree = self.file_explorer.file_tree
        self.file_tree_layout.addWidget(self.file_explorer)

        self.file_tree_layout.addLayout(self.bottom_buttons_layout)

        self.file_tree_dummy_widget_holder.setLayout(self.file_tree_layout)

        # Setting a stretch policy so the extra space goes to the right side of the screen and not the file explorer.
        file_tree_dummy_widget_holder_size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                                                          QtWidgets.QSizePolicy.Preferred)
        file_tree_dummy_widget_holder_size_policy.setHorizontalStretch(1)
        file_tree_dummy_widget_holder_size_policy.setVerticalStretch(0)
        self.file_tree_dummy_widget_holder.setSizePolicy(file_tree_dummy_widget_holder_size_policy)

        self.main_partition_splitter.addWidget(self.file_tree_dummy_widget_holder)

        # Setting up the right part of the window.

        # Setting internal variables for right side layout.
        self.data_window = None
        self.text_input = None
        self.file_windows: List[Collapsible] = []
        self.scroll_area = None
        self.file_windows_splitter = None
        self.tag_label = None
        self.tags_creator = None
        self.right_side_layout_dummy_holder = QtWidgets.QWidget()
        self.invalid_data_label = None

        self.right_side_layout = QtWidgets.QVBoxLayout()
        self.right_side_layout_dummy_holder.setLayout(self.right_side_layout)
        self.setCentralWidget(self.main_partition_splitter)

        # debug items
        # self.debug_layout = QtWidgets.QHBoxLayout()
        # self.main_dict_button = QtWidgets.QPushButton(f'Print main dictionary')
        # self.tree_main_dict_button = QtWidgets.QPushButton(f'print tree main dictionary')
        # self.debug_layout.addWidget(self.main_dict_button)
        # self.debug_layout.addWidget(self.tree_main_dict_button)
        # self.main_dict_button.clicked.connect(self.print_main_dictionary)
        # self.tree_main_dict_button.clicked.connect(self.print_tree_main_dictionary)
        # self.file_tree_layout.addLayout(self.debug_layout)
        # self.text_edit_item = None

        self.refresh_files()

        # Set the watcher.
        self.watcher_thread = QtCore.QThread(parent=self)
        self.watcher = WatcherClient(self.monitor_path)
        self.watcher.moveToThread(self.watcher_thread)
        self.watcher_thread.started.connect(self.watcher.run)

        self.expand_all_button.clicked.connect(self.tree.expandAll)
        self.collapse_all_button.clicked.connect(self.tree.collapseAll)
        self.refresh_button.clicked.connect(self.refresh_files)
        self.annotation_window_button.clicked.connect(self.on_comments_window_toggle)

        self.tree.plot_requested.connect(self.on_plot_data)
        self.tree.item_selected.connect(self.on_new_folder_selected)
        self.tree.item_starred.connect(self.on_new_item_starred)
        self.tree.item_trashed.connect(self.on_new_item_trashed)
        self.file_explorer.filter_line_edit.textChanged.connect(self.on_filter_line_edit_text_change)

        # Connect the Signals.
        self.watcher.moved.connect(self.on_file_moved)
        self.watcher.created.connect(self.on_file_created)
        self.watcher.deleted.connect(self.on_file_deleted)
        self.watcher.modified.connect(self.on_file_modified)
        self.watcher.closed.connect(self.on_file_closed)

        self.watcher_thread.start()

    def refresh_files(self) -> None:
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

        self.tree.refresh_tree(self.main_dictionary)

        # Filters what folders should be starred.
        starred_folders = [Path(walk_entry[0]) for walk_entry in walk_results if '__star__.tag' in walk_entry[2] and
                           Path(walk_entry[0]) in self.main_dictionary]

        # Filters what folders should be trashed.
        trash_folders = [Path(walk_entry[0]) for walk_entry in walk_results if '__trash__.tag' in walk_entry[2] and
                         Path(walk_entry[0]) in self.main_dictionary]

        # Check that there aren't any folder with both tags in it
        matching_items = set(starred_folders) & set(trash_folders)

        # Delete every double tag from the lists and actual files.
        for match in matching_items:
            starred_folders.remove(match)
            trash_folders.remove(match)

            star_path = match.joinpath('__star__.tag')
            trash_path = match.joinpath('__trash__.tag')
            star_path.unlink()
            trash_path.unlink()

        # Warn the user that repeated tags have been found and deleted.
        if len(matching_items) > 0:
            logger().error(f'Both star and trash tag have been found and deleted from the following folders:'
                           f' {matching_items} ')

        for folder in starred_folders:
            self.tree.star_item(folder)
        for folder in trash_folders:
            self.tree.trash_item(folder)

        final_timer = time.time_ns() - start_timer
        logger().info(f'refreshing files took: {final_timer * 10 ** -9}s')

    @Slot(FileSystemEvent)
    def on_file_created(self, event: FileSystemEvent) -> None:
        """
        Triggered every time a file or directory is created. Identifies if the new created file is relevant and adds it
        to the main dictionary.
        """
        # logger().info(f'file created: {event}')
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
                        self._check_special_tag_creation(path)

                        if path.suffix == '.tag':
                            self.tree.new_tag_created(path)

            # If a file is created in the currently displaying folder update the right side.
            if path.parent == self.currently_selected_folder:
                self.generate_right_side_window(self.currently_selected_folder)

    @Slot(FileSystemEvent)
    def on_file_deleted(self, event: FileSystemEvent) -> None:
        """
        Triggered every time a file or directory is deleted. Identifies if the deleted file is relevant and deletes it
        and any other non-relevant files.
        """
        # logger().info(f'file deleted: {event}')
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
                        if path.name == '__star__.tag':
                            self.tree.star_item(path.parent)
                        elif path.name == '__trash__.tag':
                            self.tree.trash_item(path.parent)

                        if path.suffix == '.tag':
                            self.tree.tag_deleted(path)

                        del self.main_dictionary[path.parent][path]
                        self.tree.delete_item(path)

            # If a file gets deleted from the currently selected folder, update the right side.
            if path.parent == self.currently_selected_folder:
                self.generate_right_side_window(self.currently_selected_folder)

    @Slot(FileSystemEvent)
    def on_file_moved(self, event: FileSystemEvent) -> None:
        """
        Triggered every time a file or folder is moved, this includes a file or folder changing names.
        Updates both the `main_dictionary` and the file tree.
        """
        # logger().info(f'File moved: {event}')
        # File moved gets triggered with None and '', for the event paths. From what I can tell, they are not useful,
        # so we ignore them.
        if event.src_path is not None and event.src_path != ''\
                and event.dest_path is not None and event.dest_path != '':
            src_path = Path(event.src_path)
            dest_path = Path(event.dest_path)
            if event.is_directory:
                if src_path in self.main_dictionary:
                    self.main_dictionary[dest_path] = self.main_dictionary.pop(src_path)

                # The change might be to a parent folder which is not being kept track of in the main_dictionary,
                # but still needs updating in the GUI.
                self.tree.update_item(src_path, dest_path)

            # If a file becomes a ddh5, create a new ddh5 and delete the old entry.
            elif src_path.suffix != '.ddh5' and dest_path.suffix == '.ddh5':
                # Checks if the new ddh5 is in an already kept track folder. If so delete the out of data info.
                if src_path.parent in self.main_dictionary:
                    del self.main_dictionary[src_path.parent][src_path]
                    self.tree.delete_item(src_path)
                elif dest_path.parent in self.main_dictionary:
                    del self.main_dictionary[dest_path.parent][src_path]
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
                    # TODO: get here and particularly test this case.
                    self._update_change_of_file(src_path, dest_path)

            # The change might be to a parent folder which is not being kept track of in the main_dictionary, but still
            # needs updating in the GUI.
            else:
                self._update_change_of_file(src_path, dest_path)
                self.tree.update_item(src_path, dest_path)

    @Slot(FileSystemEvent)
    def on_file_modified(self, event: FileSystemEvent) -> None:
        """
        Gets called every time a file or folder gets modified.
        If the file gets modified in the currently selected folder updates the right side of the screen.
        """
        # logger().info(f'file modified: {event}')
        # path = Path(event.src_path)
        # print(f'after the logging of modified.')
        # if path.parent == self.currently_selected_folder:
        #     self.new_folder_selected(path.parent)
        pass

    @Slot(FileSystemEvent)
    def on_file_closed(self, event: FileSystemEvent) -> None:
        """
        Gets called every time a file is closed
        """
        # logger().info(f'file closed: {event}')
        pass

    def _update_change_of_file(self, src_path: Path, dest_path: Path) -> None:
        """
        Helper function that updates a file that has changed its file type.

        :param src_path: The path of the file before the modification.
        :param dest_path: The path of the file after the modification.
        """
        # Checks that the difference is not a star or trash tag.
        if src_path.name == '__star__.tag' and dest_path.name != '__star__.tag':
            self.tree.star_item(src_path.parent)
        elif src_path.name == '__trash__.tag' and dest_path.name != '__trash__.tag':
            self.tree.trash_item(src_path.parent)

        if src_path.name != dest_path.name:
            self._check_special_tag_creation(dest_path)

        if src_path.parent in self.main_dictionary:
            del self.main_dictionary[src_path.parent][src_path]
            self.main_dictionary[src_path.parent][dest_path] = ContentType.sort(dest_path)
            self.tree.update_item(src_path, dest_path)
        elif dest_path.parent in self.main_dictionary:
            del self.main_dictionary[dest_path.parent][src_path]
            self.main_dictionary[dest_path.parent][dest_path] = ContentType.sort(dest_path)
            self.tree.update_item(src_path, dest_path)

    def _check_special_tag_creation(self, path: Path) -> None:
        """
        Checks that there is only 1 special tag file in the folder. Creates a message if it already finds a special tag
        file and deletes it.

        :param path: The path of the new file.
        """
        if path.name == '__star__.tag':
            trash_file = path.parent.joinpath('__trash__.tag')
            # If there is a trash file in a folder that is being starred delete the star file and raise
            # a warning.
            if trash_file.is_file():
                path.unlink()
                error_msg = QtWidgets.QMessageBox()
                error_msg.setText(f'Folder is already star. Please do not star a trash folder '
                                  f' \n {path} was deleted ')
                error_msg.setWindowTitle(f'Deleting __star__.tag')
                error_msg.exec_()
            else:
                self.tree.star_item(path.parent)
        elif path.name == '__trash__.tag':
            star_path = path.parent.joinpath('__star__.tag')
            # If there is a star file in a folder that is being trash delete the star file and raise
            # a warning.
            if star_path.is_file():
                path.unlink()
                error_msg = QtWidgets.QMessageBox()
                error_msg.setText(f'Folder is already trash. Please do not trash a star folder '
                                  f' \n {path} was deleted ')
                error_msg.setWindowTitle(f'Deleting __star__.tag')
                error_msg.exec_()
            else:
                self.tree.trash_item(path.parent)

    def _add_new_ddh5_file(self, path: Path) -> None:
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
        else:
            # Gets all the files in the folder containing the new ddh5 file.
            new_entry = {
                path.parent: {file: ContentType.sort(file) for file in path.parent.iterdir() if str(file.suffix) != ''}}
            self.main_dictionary.update(new_entry)
            self.tree.sort_and_add_tree_widget_item(path.parent)

    def _delete_parent_folder(self, path: Path) -> None:
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

    @Slot(Path)
    def on_plot_data(self, path: Path) -> None:
        """
        Starts an autoplot window in a different process for the ddh5 in the path

        :param path: The Path item directing to the ddh5 file that should be plotted.
         """
        plot_app = 'plottr.apps.autoplot.autoplotDDH5'
        process = launchApp(plot_app, str(path), 'data')

    # Debug function
    @Slot()
    def print_main_dictionary(self) -> None:
        """Debug function. Prints main dictionary"""
        pprint.pprint(self.main_dictionary)

    # Debug function
    @Slot()
    def print_tree_main_dictionary(self) -> None:
        """Debug function. Prints the tree main dictionary"""
        # size_dict = {}
        # for item in self.file_windows:
        #     if isinstance(item.widget, ImageViewer):
        #         print(f'I found an ImageViewer with title: {item.plainTitle}')
        #         width = item.widget.frameGeometry().width()
        #         height = item.widget.frameGeometry().height()
        #         size_dict[item.plainTitle] = {'actual size': (width, height),
        #                                       'item_sizeHint': item.sizeHint(),
        #                                       'widget_sizeHint': item.widget.sizeHint(),
        #                                       'pixmap_size:': item.widget.pixmap.size(),
        #                                       'minimum_height': item.widget.minimumHeight(),
        #                                       'minimum_width': item.widget.minimumWidth()}
        #
        # print(f'here comes the dictionary. remember: WIDTH, HEIGHT')

        file_tree = self.file_explorer.file_tree.main_items_dictionary
        # print_dict = {file_name: dict(star=file.star, trash=file.trash) for file_name, file in file_tree.items()}
        # pprint.pprint(print_dict)
        pprint.pprint(file_tree)

    # TODO: Make this more efficient by having some kind of memory, so you don't have to make every search
    #   every time a single character gets changed, but instead a new item gets added.
    @Slot(str)
    def on_filter_line_edit_text_change(self, filter_str: str) -> None:
        """
        Gets triggered everytime the text of the filter line text edit changes. It identifies what kind of query and
        matches it with the main dictionary. Queries are separated by commas (','). Empty queries or composed of only
        a single whitespace are ignored. It also ignores the first character of a query if this is a whitespace.

        It accepts 5 kinds of queries:
            * tags: queries starting with, 'tag:', 't:', or 'T:'.
            * Markdown files: queries starting with, 'md:', 'm:', or 'M:'.
            * Images: queries starting with, 'image:', 'i:', or 'I:'.
            * Json files: queries starting with, 'json:', 'j:', or 'J:'.
            * Folder names: any other query.

        :param filter_str: The str that is currently in the filter line text edit
        """

        raw_queries = filter_str.split(',')
        queries_with_empty_spaces = [item[1:] if len(item) >= 1 and item[0] == " " else item for item in raw_queries]
        queries = [item for item in queries_with_empty_spaces if item != '' and item != ' ']

        tag_queries = []
        md_queries = []
        image_queries = []
        json_queries = []
        name_queries = []
        for query in queries:
            if query[:6] == 'tag:':
                tag_queries.append(query[6:])
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

        matches_dict = {}
        if len(name_queries) > 0:
            name_matches = self._match_items(name_queries)
            matches_dict.update(name_matches)
        if len(tag_queries) > 0:
            tag_matches = self._match_items(tag_queries, ContentType.tag)
            matches_dict.update(tag_matches)
        if len(md_queries) > 0:
            md_matches = self._match_items(md_queries, ContentType.md)
            matches_dict.update(md_matches)
        if len(image_queries) > 0:
            image_matches = self._match_items(image_queries, ContentType.image)
            matches_dict.update(image_matches)
        if len(json_queries):
            json_matches = self._match_items(json_queries, ContentType.json)
            matches_dict.update(json_matches)

        # Verified matches are matches that match every query requested and not only one.
        verified_matches = []

        # verifies all the matches.
        for key, values in matches_dict.items():
            for value in values:
                if value in verified_matches:
                    continue
                found = True
                for second_values in matches_dict.values():
                    if value not in second_values:
                        found = False
                if found:
                    verified_matches.append(value)

        if len(verified_matches) == 0 and len(queries) == 0:
            self.tree.update_filter_matches(fil=None)
        else:
            self.tree.update_filter_matches(fil=verified_matches)

    def _match_items(self, queries: List[str], content_type: Optional[ContentType] = None) -> Dict[str, List[Path]]:
        """
        Helper function that matches the queries asked with items in the main dictionary.

        :param queries: List of the queries that should be used to match against the main dictionary.
        :param content_type: Optional ContentType indicating what kind of file the query should be matched against.
            If none, it will look for folder names (main_dictionary keys) instead of specific file kinds.

        :return: A dictionary with each query as a key and a list of matching Path as a value.
        """
        matches = {}
        if content_type is None:
            for query in queries:
                match_pattern = re.compile(query, flags=re.IGNORECASE)
                query_matches = [key for key in self.main_dictionary.keys() if match_pattern.search(str(key))]
                matches[query] = query_matches
        else:
            for query in queries:
                match_pattern = re.compile(query, flags=re.IGNORECASE)
                query_matches = [key for key, values in self.main_dictionary.items()
                                 for file_name, file_type in values.items()
                                 if (match_pattern.search(str(file_name.name)) and file_type == content_type)]
                matches[query] = query_matches

        return matches

    @Slot(Path)
    def on_new_folder_selected(self, path: Path) -> None:
        """
        Gets called when the user selects a folder in the main file tree. Calls the function that generates the right
        side of the screen.

        :param path: The path of the folder being selected
        """
        self.generate_right_side_window(path)

    def generate_right_side_window(self, path: Path) -> None:
        """
        Generates the right side of the screen.

        :param path: The path of the folder where the files to create the right side are being created/
        """
        # Check that it is a folder that has a ddh5 inside
        if path in self.main_dictionary:

            # If it's the first time, create the right side scroll area and add it to the splitter.
            if self.scroll_area is None:
                self.scroll_area = VerticalScrollArea()
                self.scroll_area.setWidget(self.right_side_layout_dummy_holder)
                self.main_partition_splitter.addWidget(self.scroll_area)

            # Check if this is the first time we are selecting a folder.
            # If it isn't update the collapsed state dictionary
            if self.currently_selected_folder is not None:
                self.collapsed_state_dictionary[self.currently_selected_folder] = \
                    {window.plainTitle: window.btn.isChecked() for window in self.file_windows}
            collapsed_settings = {}
            if path in self.collapsed_state_dictionary:
                collapsed_settings = self.collapsed_state_dictionary[path]

            self.currently_selected_folder = path
            self.clear_right_layout()
            self.add_tag_label(path)
            try:
                self.add_data_window(path)
            except Exception as e:
                self.invalid_data_label = QtWidgets.QLabel(f'Could not load  data: {type(e)}: {e}')
                self.right_side_layout.addWidget(self.invalid_data_label)
            self.add_text_input(path)
            self.add_all_files(path, collapsed_settings)

        self.main_partition_splitter.setStretchFactor(0, 0)
        self.main_partition_splitter.setStretchFactor(1, 255)

    def add_data_window(self, path: Path) -> None:
        """
        Create the widget to display the data.

        :param path: The path of the folder being selected
        """
        data_files = [file for file, file_type in self.main_dictionary[path].items()
                      if file_type == ContentType.data]

        self.data_window = Collapsible(DataTreeWidget(data_files), 'Data Display')

        assert isinstance(self.data_window.widget, DataTreeWidget)
        self.data_window.widget.plot_requested.connect(self.on_plot_data)

        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.data_window.setSizePolicy(size_policy)

        self.right_side_layout.addWidget(self.data_window)

    def add_tag_label(self, path: Path) -> None:
        """
        Add the tags present in the folder selected.

        :param path: The path of the folder being selected
        """
        tags = [str(label.stem) for label, file_type in self.main_dictionary[path].items()
                if file_type == ContentType.tag]

        self.tag_label = TagLabel(tags)
        self.tags_creator = TagCreator(path)
        self.right_side_layout.addWidget(self.tag_label)
        self.right_side_layout.addWidget(self.tags_creator)

    def add_text_input(self, path:Path) -> None:
        """
        Adds the widget to add a comment in the selected folder.

        :param path: The path of the folder being selected
        """
        self.text_input = Collapsible(TextInput(path), title='Add Comment:')
        self.right_side_layout.addWidget(self.text_input)

    # TODO: Modify the complex number showing, so it shows real units instead of 0s and 1s.
    # TODO: add expand all to the json viewer.
    # TODO: make the json viewer editable.
    def add_all_files(self, path: Path, collapsed_settings: Dict[str, bool] = {}) -> None:
        """
        Adds all other md, json or images files on the right side of the screen.

        :param path: The path of the folder being selected.
        :param collapsed_settings: Contains previous state (if exists) of each widget so that the function can generate
            them expanded or collapsed appropriately.
        """
        # Generate a sorted list of the files I need to display a window
        files = [(file, file_type) for file, file_type in self.main_dictionary[path].items()
                 if file_type == ContentType.json or
                 file_type == ContentType.md or
                 file_type == ContentType.image]

        # Adding extra check if multiple files get deleted at once to update with files that do exists
        files = [file for file in files if file[0].is_file()]

        files = sorted(files, key=lambda x: str.lower(x[0].name), reverse=True)
        for file, file_type in files:
            if file_type == ContentType.json:

                collapsed_option = False
                # Check if there are collapsed settings for this file and apply them.
                if file.name in collapsed_settings:
                    collapsed_option = collapsed_settings[file.name]
                json_view = Collapsible(widget=QtWidgets.QTreeView(), title=file.name, expanding=collapsed_option)
                json_view.widget.setVisible(collapsed_option)
                json_view.btn.setChecked(collapsed_option)
                if collapsed_option:
                    json_view.btn.setText(json_view.expandedTitle)
                else:
                    json_view.btn.setText(json_view.collapsedTitle)

                assert isinstance(json_view.widget, QtWidgets.QTreeView)
                json_model = JsonModel(json_view)

                json_view.widget.setModel(json_model)

                with open(file) as json_file:
                    json_model.load(json.load(json_file))

                for i in range(len(json_model._headers)):
                    json_view.widget.resizeColumnToContents(i)

                self.file_windows.append(json_view)
                self.right_side_layout.addWidget(json_view)

            elif file_type == ContentType.md:

                collapsed_option = True
                # Check if there are collapsed settings for this file and apply them.
                if file.name in collapsed_settings:
                    collapsed_option = collapsed_settings[file.name]
                plain_text_edit = Collapsible(widget=TextEditWidget(path=file),
                                              title=file.name, expanding=collapsed_option)
                plain_text_edit.widget.setVisible(collapsed_option)
                plain_text_edit.btn.setChecked(collapsed_option)
                if collapsed_option:
                    plain_text_edit.btn.setText(plain_text_edit.expandedTitle)
                else:
                    plain_text_edit.btn.setText(plain_text_edit.collapsedTitle)

                self.file_windows.append(plain_text_edit)
                self.right_side_layout.addWidget(plain_text_edit)

            elif file_type == ContentType.image:

                collapsed_option = False
                # Check if there are collapsed settings for this file and apply them.
                if file.name in collapsed_settings:
                    collapsed_option = collapsed_settings[file.name]

                label = Collapsible(ImageViewer(file, parent=self.right_side_layout_dummy_holder),
                                    title=file.name, expanding=collapsed_option)
                label.widget.setVisible(collapsed_option)
                label.btn.setChecked(collapsed_option)
                if collapsed_option:
                    label.btn.setText(label.expandedTitle)
                else:
                    label.btn.setText(label.collapsedTitle)

                self.file_windows.append(label)
                self.right_side_layout.addWidget(label)

    def clear_right_layout(self) -> None:
        """
        Clears every item on the right side of the screen.
        """

        if self.data_window is not None:
            self.right_side_layout.removeWidget(self.data_window)
            self.data_window.deleteLater()
            self.data_window = None

        if self.invalid_data_label is not None:
            self.right_side_layout.removeWidget(self.invalid_data_label)
            self.invalid_data_label.deleteLater()
            self.invalid_data_label = None

        if self.tag_label is not None:
            self.right_side_layout.removeWidget(self.tag_label)
            self.tag_label.deleteLater()
            self.tag_label = None

        if self.tags_creator is not None:
            self.right_side_layout.removeWidget(self.tags_creator)
            self.tags_creator.deleteLater()
            self.tags_creator = None

        if self.text_input is not None:
            self.right_side_layout.removeWidget(self.text_input)
            self.text_input.deleteLater()
            self.text_input = None

        if len(self.file_windows) >= 1:
            for window in self.file_windows:
                self.right_side_layout.removeWidget(window)
                window.deleteLater()
            self.file_windows = []

    @Slot(Path)
    def on_new_item_starred(self, path: Path) -> None:
        """
        Gets called every time the user decides to star an item. Checks whether the item is a folder of interest or a
        parent of one and stars or un-stars depending on whether a star tag already exists.

        :param path: The path of the folder being starred.
        """
        if path in self.main_dictionary:
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
        else:
            children_folders = [folder for folder in self.main_dictionary.keys() if folder.is_relative_to(path)]
            n_star_tags = 0
            for child in children_folders:
                star_path = child.joinpath('__star__.tag')
                if star_path.is_file():
                    n_star_tags += 1

            # If there are more children folders than star tags, we are starring the parent folder.
            if len(children_folders) > n_star_tags:
                # Same process as individually staring a folder, but for every child folder.
                for child in children_folders:
                    star_path = child.joinpath('__star__.tag')
                    trash_path = child.joinpath('__trash__.tag')
                    if trash_path.is_file():
                        trash_path.unlink()
                    if not star_path.is_file():
                        with open(star_path, 'w') as file:
                            file.write('')
            else:
                # All the child folders are starred, we need to un-star every child.
                for child in children_folders:
                    star_path = child.joinpath('__star__.tag')
                    if star_path.is_file():
                        star_path.unlink()

    @Slot(Path)
    def on_new_item_trashed(self, path: Path) -> None:
        """
        Gets called every time the user decides to trash an item. Checks whether the item is a folder of interest or a
        parent of one and trashes or un-trashes depending on whether a trash tag already exists.

        :param path: The path of the folder being starred.
        """
        if path in self.main_dictionary:
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
        else:
            children_folders = [folder for folder in self.main_dictionary.keys() if folder.is_relative_to(path)]
            n_trash_tags = 0
            for child in children_folders:
                trash_path = child.joinpath('__trash__.tag')
                if trash_path.is_file():
                    n_trash_tags += 1

            # If there are more children folders than trash tags, we are trashing the parent folder.
            if len(children_folders) > n_trash_tags:
                # Same process as individually trashing a folder, but for every child folder.
                for child in children_folders:
                    star_path = child.joinpath('__star__.tag')
                    trash_path = child.joinpath('__trash__.tag')
                    if star_path.is_file():
                        star_path.unlink()
                    if not trash_path.is_file():
                        with open(trash_path, 'w') as file:
                            file.write('')
            else:
                # All the child folders are trashed, we need to un-trash every child.
                for child in children_folders:
                    trash_path = child.joinpath('__trash__.tag')
                    if trash_path.is_file():
                        trash_path.unlink()

    @Slot()
    def on_comments_window_toggle(self):
        if self.annotation_window_button.isChecked():
            if self.annotation_window is None:
                self.annotation_window = AnnotationWindow(self.main_dictionary, self.monitor_path)
            self.annotation_window.show()
        else:
            self.annotation_window.hide()



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
