import sys
import os
import pkgutil
import importlib
from importlib import reload, import_module
import warnings
from typing import Dict, Optional, Type
import inspect
from dataclasses import dataclass
import numbers

import lmfit

from plottr import QtGui, QtCore, Slot, Signal, QtWidgets
from plottr.analyzer import fitters
from plottr.analyzer.fitters.fitter_base import Fit

from ..data.datadict import DataDictBase
from .node import Node, NodeWidget, updateOption, updateGuiFromNode

__author__ = 'Chao Zhou'
__license__ = 'MIT'

def get_models_in_module(module):
    '''Gather the model classes in the the fitting module file
    :return : a dictionary that contains all the model classed in the module
    '''
    def is_Fit_subclass(cls: Type[Fit]):
        """ check if a class is the subclass of analyzer.fitters.fitter_base.Fit
        """
        try:
            if issubclass(cls, Fit) and (cls is not Fit):
                return True
            else:
                return False
        except TypeError:
            return False
    # reload the module (this will clear the class cache)
    try:
        del sys.modules[module.__name__]
    except:
        pass
    module = import_module(module.__name__)

    model_classes = inspect.getmembers(module, is_Fit_subclass)
    model_dict = {}
    for mc in model_classes:
        model_dict[mc[0]] = mc[1]
    return model_dict

def get_modules_in_pkg(pkg):
    '''Gather the fitting modules in a package
    '''
    modules = {}
    for importer, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
        if modname != "fitter_base":
            module_ = import_module('.'+modname, pkg.__name__)
            try:
                del sys.modules[module_.__name__]
            except:
                pass
            module_ = import_module('.'+modname, pkg.__name__)
            modules[modname] = module_
    return modules


INITIAL_MODULES = get_modules_in_pkg(fitters)
#TODO: this requires putting the modules in the init of fitters, there should
# be a better way to do this.

OPEN_MODULE_ICON = QtGui.QIcon(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_DirOpenIcon))
REFRESH_MODULE_ICON = QtGui.QIcon(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))


MAX_FLOAT = sys.float_info.max
@dataclass  # TODO : add other options for parameters, e.g. constrains
class ParamOptions:  # Maybe just use the lmfit.Parameter object instead?
    fixed: bool = False
    initialGuess: float = 0
    lowerBound: float = None
    upperBound: float = None


@dataclass
class FittingOptions:
    model: str
    parameters: Dict[str, ParamOptions]


class FittingGui(NodeWidget):
    """ Gui for controlling the fitting function and the initial guess of
    fitting parameters.
    """
    def __init__(self, parent=None, node=None):
        super().__init__(parent)
        self.input_options = None # fitting option in dataIn
        self.live_update = False
        self.param_signals = []
        self.fitting_modules = INITIAL_MODULES

        self.layout = QtWidgets.QFormLayout()
        self.setLayout(self.layout)

        # fitting module widgets
        module_sel_widget = QtWidgets.QWidget()
        module_sel_grid = QtWidgets.QGridLayout()
        # model function selection widget
        self.module_combo = self.addModuleComboBox()
        self.module_combo.currentTextChanged.connect(self.moduleUpdate)
        self.module_combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                        QtWidgets.QSizePolicy.Expanding)
        module_sel_grid.addWidget(self.module_combo, 0, 0)
        # refresh module button
        refresh_button = QtWidgets.QPushButton(REFRESH_MODULE_ICON, "")
        refresh_button.clicked.connect(self.moduleRefreshClicked)
        refresh_button.setSizePolicy(QtWidgets.QSizePolicy.Fixed,
                                     QtWidgets.QSizePolicy.Fixed)
        module_sel_grid.addWidget(refresh_button, 0, 1)
        # add module button
        open_button = QtWidgets.QPushButton(OPEN_MODULE_ICON,"")
        open_button.clicked.connect(self.add_user_module)
        open_button.setSizePolicy(QtWidgets.QSizePolicy.Fixed,
                                  QtWidgets.QSizePolicy.Fixed)
        module_sel_grid.addWidget(open_button, 0, 2)
        module_sel_widget.setLayout(module_sel_grid)
        self.layout.addWidget(module_sel_widget)


        # model list widget
        self.model_list = QtWidgets.QListWidget()
        self.layout.addWidget(self.model_list)
        self.moduleUpdate(self.module_combo.currentText())
        self.model_list.currentItemChanged.connect(self.modelChanged)

        # function description window
        self.model_doc_box = QtWidgets.QLineEdit("")
        self.model_doc_box.setReadOnly(True)
        self.layout.addWidget(self.model_doc_box)


    def addModuleComboBox(self):
        """ Set up the model function drop down manual widget.
        """
        combo = QtWidgets.QComboBox()
        combo.setEditable(False)
        for module_name in self.fitting_modules:
            combo.addItem(module_name)
        return combo

    @Slot(str)
    def moduleUpdate(self, current_module_name):
        print (current_module_name)
        self.model_list.clear()
        current_module = self.fitting_modules[current_module_name]
        new_models = get_models_in_module(current_module)
        for model_name in new_models:
            self.model_list.addItem(model_name)

        # debug-------------------------------------------
        """
        fitters.generic_functions.Cosine.pp(1)
        try:
            test = fitters.generic_functions.Exponential2
            print("Exponential2 is here!!!!!")
        except :
            print("No Exponential2 :( ")
        """
        #-------------------------------------------------

    @Slot()
    def moduleRefreshClicked(self):
        self.moduleUpdate(self.module_combo.currentText())

    def add_user_module(self):
        mod_file = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Open file',fitters.__path__[0], "Python files (""*.py)")[0]
        if (mod_file is None) or mod_file[-3:] !=".py":
            return
        mod_name = mod_file.split('/')[-1][:-3]
        mod_dir = '\\'.join(mod_file.split('/')[:-1])
        # load the selected module
        sys.path.append(mod_dir)
        user_module = import_module(mod_name, mod_dir)
        # debug-------------------------------------------
        """
        spec = importlib.util.spec_from_file_location(mod_name, mod_path)
        user_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(user_module)
        """
        #-------------------------------------------------
        # check if there is already a module with the same name
        if mod_name in self.fitting_modules:
            for existing_module in self.fitting_modules.values():
                if user_module.__file__ == existing_module.__file__:
                    # a module that already exists is loaded
                    print("a module that already exists is loaded")
                    self.module_combo.setCurrentText(mod_name)
                    self.moduleUpdate(mod_name)
                    return
            # a different module whose name is the same as one of the
            # existing modules is loaded
            print("a different module whose name is the same as one of "
                  "the existing modules is loaded")
            mod_name += f"({mod_dir})"

        self.fitting_modules[mod_name] = user_module
        self.module_combo.addItem(mod_name)
        self.module_combo.setCurrentText(mod_name)


    @Slot(QtWidgets.QListWidgetItem, QtWidgets.QListWidgetItem)
    def modelChanged(self,
                     current: QtWidgets.QListWidgetItem,
                     previous: QtWidgets.QListWidgetItem):
        """ Process a change in fit model selection.
        Will update the parameter table based on the new selection.
        """
        if current is None:
            print ("No model selected")
            self.model_doc_box.setText("")
            return
        current_module = self.fitting_modules[self.module_combo.currentText()]
        model_cls = getattr(current_module, current.text())
        print(model_cls.model.__doc__)

        self.model_doc_box.setText(model_cls.model.__doc__)
# ================= Node ==============================
class FittingNode(Node):
    uiClass = FittingGui
    nodeName = "Fitter"
    default_fitting_options = Signal(object)

    def __init__(self, name):
        super().__init__(name)
        self._fitting_options = None

    def process(self, dataIn: DataDictBase = None):
        return self.fitting_process(dataIn)

    @property
    def fitting_options(self):
        return self._fitting_options

    @fitting_options.setter
    @updateOption('fitting_options')
    def fitting_options(self, opt):
        if isinstance(opt, FittingOptions) or opt is None:
            self._fitting_options = opt
        else:
            raise TypeError('Wrong fitting options')

    def fitting_process(self, dataIn: DataDictBase = None):
        if dataIn is None:
            return None

        if len(dataIn.axes()) > 1 or len(dataIn.dependents()) > 1:
            return dict(dataOut=dataIn)

        print ("dummy processing")

        return dict(dataOut=dataIn)

    def setupUi(self):
        super().setupUi()
        # self.default_fitting_options.connect(self.ui.setDefaultFit)

        # debug
        # axname = dataIn.axes()[0]
        # x = dataIn.data_vals(axname)
        # model_str = self.fitting_options.model.split('.')
        # func = MODEL_FUNCS[model_str[0]][model_str[1]]
        # fit_params = self.fitting_options.parameters
        # func_args = {arg: fit_params[arg].initialGuess for arg in fit_params}
        #
        # dataOut = dataIn.copy()
        # dataOut['fit'] = dict(values=func(x,**func_args), axes=[axname, ])
        # return dict(dataOut=dataOut)