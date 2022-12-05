"""
First version of filtering testing suite. For now the rules of filtering are:

    * If an item regex matchwith the filter parameter it will be shown.
    * All children items of the matching item will be shown too: If a parent has a tag favorite and the user is
        searching t:favorite, the child items will be shown.
    * Parents of the matching item will also be shown. This only happen for parents and not siblings of the item.
        This is because if the parent item is not shown, the child will not be shown either.
    * Trash items will ALWAYS be hidden (when hide trash is activated). This means that all the children of a trash item
        will be hidden, no matter if the match with anything else that is being filtered at the moment.
"""
import os
import sys
import time
import shutil
import datetime
import numpy as np

from pathlib import Path
from pprint import pprint
from typing import Tuple, List

from plottr.data.datadict import DataDict
from plottr.apps.monitr import FilterWorker, FileModel
from plottr.data.datadict_storage import datadict_to_hdf5


FOLDER_PATH = Path(r'C:\Users\Msmt\Documents\Python Scripts\watchdog_testing_data\automatic_file_creation')


def generate_data(file_size, file_path=None, ret=False) -> DataDict:
    """
    Creates a ddh5 file with fake data of the specified file size. If a file path is specified, the file will be saved
    in that directory. The ddh5 will be saved in the working directory otherwise. If ret is True, the function will
    return the created DataDict

    :param file_size: The approximated size that the function will create.
    :param file_path: The location of the created file.
        If the file_path is just a directory without the name of the file with the extension,
         the created file will be named 'data.ddh5'. If None, the file will be saved in the working directory with name
         'data.ddh5'.
    :param ret: If true, the function returns the datadict used to create the ddh5 file.
    :return: None if ret is False. If ret is True, returns the DataDict used to create the ddh5 file.
    """

    npoints = np.sqrt(file_size*10**6/24)
    x = np.arange(-npoints/2, npoints/2)

    xv, yv = np.meshgrid(x, x)

    z = np.sqrt(xv**2 + yv**2)

    datadict = DataDict()
    datadict['x'] = dict(axes=[])
    datadict['y'] = dict(axes=[])
    datadict['z'] = dict(axes=['x', 'y'])

    datadict.add_data(x=xv, y=yv, z=z)

    datadict.validate()
    if file_path is None:
        datadict_to_hdf5(datadict=datadict, path=os.path.join(os.path.abspath(os.getcwd()), 'data.ddh5'))
        return datadict
    else:
        root, ext = os.path.splitext(file_path)
        if ext == '':
            file_path = os.path.join(file_path, 'data.ddh5')
        datadict_to_hdf5(datadict=datadict, path=file_path)
        if ret:
            return datadict


def generate_file_structure(folder_path=None) -> Tuple[List[Path], List[Path], FileModel]:
    if folder_path.is_dir():
        shutil.rmtree(folder_path)
        folder_path.mkdir()

    folder_path = folder_path.joinpath('data')
    folder_path.mkdir()

    n_days = 5
    days_paths = [folder_path.joinpath(f'day_{i}') for i in range(n_days)]
    folder_paths = []
    for day_path in days_paths:
        day_path.mkdir()
        for i in range(3):
            folder=day_path.joinpath(f'data_folder_{i}')
            folder.mkdir()
            generate_data(0.001, folder)
            folder_paths.append(folder)

    return folder_path, days_paths, folder_paths


def test_only_ddh5_files(tmp_path, qtbot):
    folder_path, days_paths, folder_paths = generate_file_structure(tmp_path)

    model = FileModel(str(folder_path), 0, 2, watcher_on=False)
    filter_worker = FilterWorker()
    queries = []
    allowed_list, queries_dict = filter_worker.filter_items(model, False, False, '', queries)

    paths = [item for item in allowed_list]
    assert sorted(folder_paths + days_paths) == sorted(paths)


def test_same_tag_in_2_datasets(tmp_path, qtbot):
    folder_path, days_paths, folder_paths = generate_file_structure(tmp_path)

    tag_containing_folders = [folder_paths[0],folder_paths[3]]
    allowed_folders= days_paths[0:2] + [folder_paths[0], folder_paths[3]]

    tag_str = 'favorite.tag'
    for tag_folder in tag_containing_folders:
        tag_path = tag_folder.joinpath(tag_str)
        with open(tag_path, 'w') as f:
            f.write('this is a fav')

    model = FileModel(str(folder_path), 0, 2, watcher_on=False)
    filter_worker = FilterWorker()
    queries = 't:favorite'
    tag_queries = []
    star_status, trash_status = False, False
    filtered_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)

    paths = [item for item in filtered_list]
    assert sorted(allowed_folders) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in allowed_folders:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)


def test_2_different_children_tags(tmp_path, qtbot):
    folder_path, days_paths, folder_paths = generate_file_structure(tmp_path)

    tag_favorite_folder = [folder_paths[0], folder_paths[6]]
    tag_invalid_folder = [folder_paths[3], folder_paths[6]]

    favorite_results = [days_paths[0], days_paths[2], folder_paths[0], folder_paths[6]]
    invalid_results = [days_paths[1], days_paths[2], folder_paths[3], folder_paths[6]]

    both_tags = [days_paths[2], folder_paths[6]]

    combined_results = list(set(favorite_results + invalid_results))

    for tag_folder in tag_favorite_folder:
        fav_path = tag_folder.joinpath('favorite.tag')
        with open(fav_path, 'w') as f:
            f.write('this is a fav')

    for tag_folder in tag_invalid_folder:
        invalid_path = tag_folder.joinpath('invalid.tag')
        with open(invalid_path, 'w') as f:
            f.write('this is invalid')

    model = FileModel(str(folder_path), 0, 2, watcher_on=False)
    filter_worker = FilterWorker()

    queries = 't:'
    tag_queries = []
    star_status, trash_status = False, False
    invalid_allowed_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in invalid_allowed_list]
    assert sorted(combined_results) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in combined_results:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)

    queries = 't:favorite'
    favorite_allowed_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in favorite_allowed_list]
    assert sorted(favorite_results) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in favorite_results:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)

    queries = 't:invalid'
    invalid_allowed_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in invalid_allowed_list]
    assert sorted(invalid_results) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in invalid_results:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)

    queries = 't:favorite, t:invalid'
    invalid_allowed_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in invalid_allowed_list]
    assert sorted(both_tags) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in both_tags:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)

    queries = 't:other tag'
    invalid_allowed_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in invalid_allowed_list]
    assert [] == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)


def test_parent_folder_with_tags(qtbot, tmp_path):
    folder_path, days_paths, folder_paths = generate_file_structure(tmp_path)

    allowed_folders = [days_paths[0]] + folder_paths[0:3]

    fav_path = days_paths[0].joinpath('favorite.tag')
    with open(fav_path, 'w') as f:
        f.write(f'this is a fav')

    model = FileModel(str(folder_path), 0, 2, watcher_on=False)
    filter_worker = FilterWorker()

    queries = 't:favorite'
    tag_queries = []
    star_status, trash_status = False, False
    filtered_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(allowed_folders) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in allowed_folders:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)


def test_2_different_parent_tags(tmp_path, qtbot):
    folder_path, days_paths, folder_paths = generate_file_structure(tmp_path)

    tag_favorite_folder = [days_paths[0], days_paths[2]]
    tag_invalid_folder = [days_paths[1], days_paths[2]]

    favorite_results = [days_paths[0], days_paths[2]] + folder_paths[:3] + folder_paths[6:9]
    invalid_results = [days_paths[1], days_paths[2]] + folder_paths[3:6] + folder_paths[6:9]

    both_tags = [days_paths[2]] + folder_paths[6:9]

    combined_results = list(set(favorite_results + invalid_results))

    for tag_folder in tag_favorite_folder:
        fav_path = tag_folder.joinpath('favorite.tag')
        with open(fav_path, 'w') as f:
            f.write('this is a fav')

    for tag_folder in tag_invalid_folder:
        invalid_path = tag_folder.joinpath('invalid.tag')
        with open(invalid_path, 'w') as f:
            f.write('this is invalid')

    model = FileModel(str(folder_path), 0, 2, watcher_on=False)
    filter_worker = FilterWorker()

    queries = 't:'
    tag_queries = []
    star_status, trash_status = False, False
    invalid_allowed_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in invalid_allowed_list]
    assert sorted(combined_results) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in combined_results:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)

    queries = 't:favorite'
    favorite_allowed_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in favorite_allowed_list]
    assert sorted(favorite_results) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in favorite_results:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)

    queries = 't:invalid'
    invalid_allowed_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in invalid_allowed_list]
    assert sorted(invalid_results) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in invalid_results:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)

    queries = 't:favorite, t:invalid'
    invalid_allowed_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in invalid_allowed_list]
    assert sorted(both_tags) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in both_tags:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)


    queries = 't:other tag'
    invalid_allowed_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in invalid_allowed_list]
    assert [] == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)


def test_staring_child_items(qtbot, tmp_path):
    folder_path, days_paths, folder_paths = generate_file_structure(tmp_path)

    starred_folders = folder_paths[4:7]
    allowed_folders = days_paths[1:3] + starred_folders

    for path in starred_folders:
        with open(path.joinpath('__star__.tag'), 'w') as f:
            f.write(f'this is a star')

    model = FileModel(str(folder_path), 0, 2, watcher_on=False)
    filter_worker = FilterWorker()

    queries = ''
    tag_queries = []
    star_status, trash_status = True, False
    filtered_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(allowed_folders) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in allowed_folders:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)

def test_2_starred_children_1_tagged(qtbot, tmp_path):
    folder_path, days_paths, folder_paths = generate_file_structure(tmp_path)

    starred_folders = [folder_paths[4], folder_paths[5]]
    allowed_folders = [days_paths[1], folder_paths[4]]

    for path in starred_folders:
        with open(path.joinpath('__star__.tag'), 'w') as f:
            f.write(f'this is a star')

    with open(folder_paths[4].joinpath('favorite.tag'), 'w') as f:
        f.write(f'this is a fav')

    model = FileModel(str(folder_path), 0, 2, watcher_on=False)
    filter_worker = FilterWorker()

    queries = ''
    tag_queries = []
    star_status, trash_status = True, False
    filtered_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(allowed_folders + [folder_paths[5]]) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in allowed_folders + [folder_paths[5]]:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)

    queries = 't:favorite'
    tag_queries = []
    star_status, trash_status = True, False
    filtered_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(allowed_folders) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in allowed_folders:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)


def test_starring_parent_items(qtbot, tmp_path):
    folder_path, days_paths, folder_paths = generate_file_structure(tmp_path)

    starred_folders = days_paths[1:3]
    allowed_folders = starred_folders + folder_paths[3:9]

    for path in starred_folders:
        with open(path.joinpath('__star__.tag'), 'w') as f:
            f.write(f'this is a star')

    model = FileModel(str(folder_path), 0, 2, watcher_on=False)
    filter_worker = FilterWorker()

    queries = ''
    tag_queries = []
    star_status, trash_status = True, False
    filtered_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(allowed_folders) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in allowed_folders:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)

    # Testing star filter through tags:
    queries = 't:__star__'
    tag_queries = []
    star_status, trash_status = False, False
    filtered_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(allowed_folders) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in allowed_folders:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)


def test_parent_starring_and_child_tags(qtbot, tmp_path):
    folder_path, days_paths, folder_paths = generate_file_structure(tmp_path)

    starred_folders = days_paths[1:3]
    tagged_folder = folder_paths[7]
    allowed_folders = [folder_paths[7], days_paths[2]]

    for path in starred_folders:
        with open(path.joinpath('__star__.tag'), 'w') as f:
            f.write(f'this is a star')

    with open(tagged_folder.joinpath('favorite.tag'), 'w') as f:
        f.write(f'this is a fav')

    model = FileModel(str(folder_path), 0, 2, watcher_on=False)
    filter_worker = FilterWorker()
    print(f'the folder path is: {folder_path}')

    queries = ''
    tag_queries = ['favorite']
    star_status, trash_status = True, False
    filtered_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert [] == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)

    with open(tagged_folder.joinpath('__star__.tag'), 'w') as f:
        f.write(f'this is a fav')

    model = FileModel(str(folder_path), 0, 2, watcher_on=False)
    filtered_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(allowed_folders) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in allowed_folders:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)

def test_2_starred_parent_one_tagged(qtbot, tmp_path):
    folder_path, days_paths, folder_paths = generate_file_structure(tmp_path)

    starred_folders = days_paths[:2]
    allowed_folders = [days_paths[0]] + folder_paths[:3]

    for path in starred_folders:
        with open(path.joinpath('__star__.tag'), 'w') as f:
            f.write(f'this is a star')

    with open(days_paths[0].joinpath('favorite.tag'), 'w') as f:
        f.write(f'this is a fav')

    model = FileModel(str(folder_path), 0, 2, watcher_on=False)
    filter_worker = FilterWorker()

    queries = 't:favorite'
    tag_queries = []
    star_status, trash_status = True, False
    filtered_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(allowed_folders) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in allowed_folders:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)

    queries = ''
    tag_queries = ['favorite']
    filtered_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(allowed_folders) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in allowed_folders:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)

def test_trash_child_items(qtbot, tmp_path):
    folder_path, days_paths, folder_paths = generate_file_structure(tmp_path)

    trashed_folders = folder_paths[12:]
    allowed_folders = days_paths + folder_paths[:12]

    for path in trashed_folders:
        with open(path.joinpath('__trash__.tag'), 'w') as f:
            f.write(f'this is a trash')

    model = FileModel(str(folder_path), 0, 2, watcher_on=False)
    filter_worker = FilterWorker()

    queries = ''
    tag_queries = []
    star_status, trash_status = False, True
    filtered_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(allowed_folders) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in allowed_folders:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)


def test_trash_parent_items(qtbot, tmp_path):
    folder_path, days_paths, folder_paths = generate_file_structure(tmp_path)

    trashed_folders = days_paths[3:]
    allowed_folders = days_paths[:3] + folder_paths[:9]

    for path in trashed_folders:
        with open(path.joinpath('__trash__.tag'), 'w') as f:
            f.write(f'this is a trash')

    model = FileModel(str(folder_path), 0, 2, watcher_on=False)
    filter_worker = FilterWorker()

    queries = ''
    tag_queries = []
    star_status, trash_status = False, True
    filtered_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(allowed_folders) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in allowed_folders:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)

def test_trash_parent_with_star_children(qtbot, tmp_path):
    folder_path, days_paths, folder_paths = generate_file_structure(tmp_path)

    starred_folder = folder_paths[1]
    trashed_folder = days_paths[0]

    allowed_folders = []

    with open(trashed_folder.joinpath('__trash__.tag'), 'w') as f:
        f.write(f'this is a trash')

    with open(starred_folder.joinpath('__star__.tag'), 'w') as f:
        f.write(f'this is a star')

    model = FileModel(str(folder_path), 0, 2, watcher_on=False)
    filter_worker = FilterWorker()

    queries = ''
    tag_queries = []
    star_status, trash_status = True, True
    filtered_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(allowed_folders) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in allowed_folders:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)

    queries = 't:__star__'
    star_status, trash_status = False, True
    filtered_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(allowed_folders) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in allowed_folders:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)


def test_star_parent_with_trash_child(qtbot, tmp_path):
    folder_path, days_paths, folder_paths = generate_file_structure(tmp_path)

    starred_folder = days_paths[0]
    trashed_folder = folder_paths[1]

    allowed_folders = [days_paths[0], folder_paths[0], folder_paths[2]]

    with open(trashed_folder.joinpath('__trash__.tag'), 'w') as f:
            f.write(f'this is a trash')

    with open(starred_folder.joinpath('__star__.tag'), 'w') as f:
            f.write(f'this is a star')

    model = FileModel(str(folder_path), 0, 2, watcher_on=False)
    filter_worker = FilterWorker()

    queries = ''
    tag_queries = []
    star_status, trash_status = True, True
    filtered_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(allowed_folders) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in allowed_folders:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)


    queries = 't:__star__'
    star_status, trash_status = False, True
    filtered_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(allowed_folders) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in allowed_folders:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)


def test_2_children_with_tags_1_is_trashed(qtbot, tmp_path):
    folder_path, days_paths, folder_paths = generate_file_structure(tmp_path)

    tagged_folders = folder_paths[0:2]
    trashed_folder = folder_paths[1]

    allowed_folders = [days_paths[0], folder_paths[0]]

    for path in tagged_folders:
        with open(path.joinpath('favorite.tag'), 'w') as f:
            f.write(f'this is a fave')

    with open(trashed_folder.joinpath('__trash__.tag'), 'w') as f:
        f.write(f'this is a star')

    model = FileModel(str(folder_path), 0, 2, watcher_on=False)
    filter_worker = FilterWorker()

    queries = 't:favorite'
    tag_queries = []
    star_status, trash_status = False, True
    filtered_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(allowed_folders) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in allowed_folders:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)

    queries = ''
    tag_queries = ['favorite']
    filtered_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(allowed_folders) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in allowed_folders:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)

def test_name_of_child(qtbot, tmp_path):
    folder_path, days_paths, folder_paths = generate_file_structure(tmp_path)

    unique_named_path = days_paths[0].joinpath('pretty_folder')
    allowed_folders = [unique_named_path, days_paths[0]]

    unique_named_path.mkdir()
    generate_data(0.001, unique_named_path)

    model = FileModel(str(folder_path), 0, 2, watcher_on=False)
    filter_worker = FilterWorker()

    queries = 'pretty'
    tag_queries = []
    star_status, trash_status = False, False
    filtered_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(allowed_folders) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in allowed_folders:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)


def test_name_of_parent_and_name_of_nested_child(qtbot, tmp_path):
    folder_path, days_paths, folder_paths = generate_file_structure(tmp_path)

    unique_named_path = days_paths[0].joinpath('pretty_folder')
    child_inside = unique_named_path.joinpath('a_lonely_child')

    allowed_folders = [unique_named_path, child_inside, days_paths[0]]

    unique_named_path.mkdir()
    child_inside.mkdir()
    generate_data(0.001, child_inside)

    model = FileModel(str(folder_path), 0, 2, watcher_on=False)
    filter_worker = FilterWorker()

    queries = 'pretty'
    tag_queries = []
    star_status, trash_status = False, False
    filtered_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(allowed_folders) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in allowed_folders:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)

    queries = 'lonely'
    tag_queries = []
    star_status, trash_status = False, False
    filtered_list, queries_dict = filter_worker.filter_items(model, star_status, trash_status, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(allowed_folders) == sorted(paths)

    # Individual filtering part of the test.
    for path, item in model.main_dictionary.items():
        if path in allowed_folders:
            assert FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)
        else:
            assert not FilterWorker.is_item_shown(item, queries, tag_queries, star_status, trash_status)


def test_combination_of_star_trash_tags(qtbot, tmp_path):

    folder_path, days_paths, folder_paths = generate_file_structure(tmp_path)

    unique_named_path = days_paths[0].joinpath('pretty_folder')
    lonely_child = unique_named_path.joinpath('a_lonely_child')

    trashed_folders = [days_paths[1], folder_paths[6], folder_paths[-1]]
    starred_folders = [days_paths[4], folder_paths[10], lonely_child]

    favorite_tag = [lonely_child]
    coffee_tag = [days_paths[4], folder_paths[7], lonely_child]

    unique_named_path.mkdir()
    lonely_child.mkdir()
    generate_data(0.001, lonely_child)

    for path in trashed_folders:
        with open(path.joinpath('__trash__.tag'), 'w') as f:
            f.write(f'this is a trash')

    for path in starred_folders:
        with open(path.joinpath('__star__.tag'), 'w') as f:
            f.write(f'this is a star')

    for path in favorite_tag:
        with open(path.joinpath('favorite.tag'), 'w') as f:
            f.write(f'this is a fave')

    for path in coffee_tag:
        with open(path.joinpath('coffee.tag'), 'w') as f:
            f.write(f'this is a cofee')

    days_paths_copy = days_paths.copy()
    days_paths_copy.pop(1)

    trash_hidden_allowed = days_paths_copy + [unique_named_path, lonely_child] + folder_paths[0:3] + folder_paths[7:14]

    model = FileModel(str(folder_path), 0, 2, watcher_on=False)
    filter_worker = FilterWorker()

    queries = ''
    tag_queries = []
    filtered_list, queries_dict = filter_worker.filter_items(model, False, True, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(trash_hidden_allowed) == sorted(paths)

    coffee_only_allowed = [days_paths[0], unique_named_path, lonely_child, days_paths[2], folder_paths[7],
                           days_paths[4]] + folder_paths[-3:]
    model.load_data()

    queries = 't:coffee'
    tag_queries = []
    filtered_list, queries_dict = filter_worker.filter_items(model, False, False, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(coffee_only_allowed) == sorted(paths)

    queries = ''
    tag_queries = ['coffee']
    filtered_list, queries_dict = filter_worker.filter_items(model, False, False, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(coffee_only_allowed) == sorted(paths)

    # When activating the trash filter the trash item inside the folder day 4 should not be shown
    coffee_only_allowed.pop(-1)

    queries = ''
    tag_queries = ['coffee']
    filtered_list, queries_dict = filter_worker.filter_items(model, False, True, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(coffee_only_allowed) == sorted(paths)

    star_only_allowed = [days_paths[0], days_paths[3], days_paths[4], lonely_child, unique_named_path,
                         folder_paths[10]] + folder_paths[12:]

    queries = ''
    tag_queries = ['']
    filtered_list, queries_dict = filter_worker.filter_items(model, True, False, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(star_only_allowed) == sorted(paths)


    coffee_and_star_allowed = [days_paths[0], unique_named_path, lonely_child, days_paths[4]] + folder_paths[12:]

    queries = 't:coffee'
    tag_queries = ['']
    filtered_list, queries_dict = filter_worker.filter_items(model, True, False, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(coffee_and_star_allowed) == sorted(paths)

    queries = ''
    tag_queries = ['coffee']
    filtered_list, queries_dict = filter_worker.filter_items(model, True, False, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(coffee_and_star_allowed) == sorted(paths)

    star_and_trash_allowed = [days_paths[0], days_paths[3], days_paths[4], lonely_child, unique_named_path,
                              folder_paths[10]] + folder_paths[12:14]

    queries = ''
    tag_queries = ['']
    filtered_list, queries_dict = filter_worker.filter_items(model, True, True, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(star_and_trash_allowed) == sorted(paths)

    star_trash_coffee_allowed = [days_paths[0], days_paths[4], lonely_child, unique_named_path,] + folder_paths[12:14]

    queries = 't:coffee'
    tag_queries = []
    filtered_list, queries_dict = filter_worker.filter_items(model, True, True, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(star_trash_coffee_allowed) == sorted(paths)

    star_trash_coffee_favorite_allowed = [days_paths[0], unique_named_path, lonely_child]

    queries = 't:coffee'
    tag_queries = ['favorite']
    filtered_list, queries_dict = filter_worker.filter_items(model, True, True, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(star_trash_coffee_favorite_allowed) == sorted(paths)

    queries = 't:favorite'
    tag_queries = ['coffee']
    filtered_list, queries_dict = filter_worker.filter_items(model, True, True, queries, tag_queries)
    paths = [item for item in filtered_list]
    assert sorted(star_trash_coffee_favorite_allowed) == sorted(paths)


def test_are_parents_trash_function(qtbot, tmp_path):
    folder_path, days_paths, folder_paths = generate_file_structure(tmp_path)

    unique_named_path = days_paths[0].joinpath('pretty_folder')
    child_inside = unique_named_path.joinpath('a_lonely_child')

    unique_named_path.mkdir()
    child_inside.mkdir()
    generate_data(0.001, child_inside)

    model = FileModel(str(folder_path), 0, 2, watcher_on=False)

    item = model.main_dictionary[child_inside]
    assert not FilterWorker._are_parents_trash(item)

    with open(days_paths[0].joinpath('__trash__.tag'), 'w') as f:
        f.write(f'this is a trash')

    model = FileModel(str(folder_path), 0, 2, watcher_on=False)
    item = model.main_dictionary[child_inside]
    assert FilterWorker._are_parents_trash(item)


def test_item_query_check(qtbot, tmp_path):
    folder_path, days_paths, folder_paths = generate_file_structure(tmp_path)

    unique_named_path = days_paths[0].joinpath('pretty_folder')
    unique_named_path.mkdir()
    generate_data(0.001, unique_named_path)

    with open(unique_named_path.joinpath('markdown_file.md'), 'w') as f:
        f.write(f'this is a markdown file')

    with open(unique_named_path.joinpath('image_file.jpg'), 'w') as f:
        f.write(f'this is an image')

    with open(unique_named_path.joinpath('json_file.json'), 'w') as f:
        f.write(f'this is a json file')

    model = FileModel(str(folder_path), 0, 2, watcher_on=False)
    item = model.main_dictionary[unique_named_path]

    filter = 'pretty_folder'
    tag_filter = []
    queries_dict = FilterWorker.parse_queries(filter, tag_filter)
    assert FilterWorker._item_check(item, False, queries_dict, )

    filter = 'pretty_folder, m:markdown'
    tag_filter = []
    queries_dict = FilterWorker.parse_queries(filter, tag_filter)
    assert FilterWorker._item_check(item, False, queries_dict, )

    filter = 'random_name_please_fail, m:markdown'
    tag_filter = []
    queries_dict = FilterWorker.parse_queries(filter, tag_filter)
    assert not FilterWorker._item_check(item, False, queries_dict, )



