from typing import TYPE_CHECKING, List, Tuple, Dict, Any, Optional
from importlib.abc import Loader
from importlib.util import spec_from_file_location, module_from_spec
import logging
import os
import sys
import signal

if TYPE_CHECKING:
    from PyQt5 import QtCore, QtGui, QtWidgets
    Signal = QtCore.pyqtSignal
    Slot = QtCore.pyqtSlot
else:
    from qtpy import QtCore, QtGui, QtWidgets
    Signal = QtCore.Signal
    Slot = QtCore.Slot

from pyqtgraph.flowchart import Flowchart as pgFlowchart, Node as pgNode
Flowchart = pgFlowchart
NodeBase = pgNode

from ._version import __version__

logger = logging.getLogger(__name__)
logger.info(f"Imported plottr version: {__version__}")


plottrPath = os.path.split(os.path.abspath(__file__))[0]


def qtsleep(delay_sec: float) -> None:
    """sleep function that allows QT event processing in the background."""
    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(int(delay_sec * 1000), loop.quit)
    loop.exec_()


def qtapp() -> QtWidgets.QApplication:
    """make a QT application that can be interrupted by Ctrl+C in the terminal."""
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QtWidgets.QApplication(sys.argv)
    return app


def configPaths() -> Tuple[str, str, str]:
    """Get the folders where plottr looks for config files.

    :return: List of absolute paths, in order of priority:
        (1) current working directory
        (2) ~/.plottr
        (3) config directory in the package.
    """
    builtIn = os.path.join(plottrPath, 'config')
    user = os.path.join(os.path.expanduser("~"), '.plottr')
    cwd = os.getcwd()
    return cwd, user, builtIn


def configFiles(fileName: str) -> List[str]:
    """Get available config files with the given file name.

    :param fileName: file name, without path
    :return: List of found config files with the provided name, in order
        or priority.
    """
    ret = []
    for path in configPaths():
        fp = os.path.join(path, fileName)
        if os.path.exists(fp):
            ret.append(fp)
    return ret


def config(names: Optional[List[str]] = None) -> \
        Dict[str, Any]:
    """Return the plottr configuration as a dictionary.

    Each config file found is expected to contain a dictionary with name
    ``config``. The returned configuration is of the form
    ``
    {
        cfg_1: {...},
        cfg_2: {...},
    }
    ``
    The keys in the returned dictionary are the names given, and the contents
    of each entry the dictionary found in the corresponding files.

    Values returned are determined in hierarchical order:
    If configs are found on package and user levels, we first look at the
    package-provided config, and then update with user-provided ones (see doc
    of :func:`.configPaths`). I.e., user-provided config has the highest
    priority and overrides package-provided config.

    Note: currently, exceptions raised when trying to import config objects are
    not caught. Erroneous config files may thus crash the program.

    :param names: List of files. For given ``name`` will look
        for ``plottrcfg_<name>.py`` in the config directories.
        if ``None``, will look only for ``plottrcfg_main.py``
    :param forceReload: If True, will not use a cached config file if present.
        will thus get the most recent config from file, without need to restart
        the program.
    """
    if names is None:
        names = ['main']

    config = {}
    for name in names:
        modn = f"plottrcfg_{name}"
        filen = f"{modn}.py"
        this_cfg: Dict[str, Any] = {}
        for filep in configFiles(filen)[::-1]:
            spec = spec_from_file_location(modn, filep)
            if spec is None:
                raise FileNotFoundError(f"Could not locate spec for {modn}, {filep}")
            mod = module_from_spec(spec)
            sys.modules[modn] = mod
            assert isinstance(spec.loader, Loader)
            spec.loader.exec_module(mod)
            this_cfg.update(getattr(mod, 'config', {}))

        config[name] = this_cfg
    return config


def config_entry(*path: str, default: Optional[Any] = None,
                 names: Optional[List[str]] = None) -> Any:
    """Get a specific config value.

    ..Example: If the config is:: python

        config = {
            'foo' : {
                'bar' : 'spam',
            },
        }

    .. then we can get an entry like this:: python

        >>> config_entry('foo', 'bar', default=None)
        'spam'
        >>> config_entry('foo', 'bacon')
        None
        >>> config_entry('foo', 'bar', 'bacon')
        None

    :param path: strings denoting the nested keys to the desired value
    :param names: see :func:`.config`.
    :param default: what to return when key isn't found in the config.
    :returns: desired value
    """

    cfg: Any = config(names)
    for k in path:
        if isinstance(cfg, dict) and k in cfg:
            cfg = cfg.get(k)
        else:
            return default
    return cfg
