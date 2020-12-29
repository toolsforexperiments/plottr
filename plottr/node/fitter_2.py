import sys
import pkgutil
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
    '''Gather the model classes in the the fitting module
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
    model_classes = inspect.getmembers(module, is_Fit_subclass)
    model_dict = {}
    for mc in model_classes:
        model_dict[mc[0]] = mc[1]
    return model_dict

def get_modules_in_pkg(pkg):
    modules = []
    for importer, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
        if modname != "fitter_base":
            modules.append(modname)
    return modules

def get_all_models_in_pkg(pkg):
    model_dict = {}
    modules = get_modules_in_pkg(pkg)
    for m in modules:
        model_dict[m] = get_models_in_module(getattr(pkg, m))
    return model_dict

MODELS = get_all_models_in_pkg(fitters)
#TODO: this requires putting the modules in the init of fitters, there should
# be a better way to do this.




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

        self.layout = QtWidgets.QFormLayout()
        self.setLayout(self.layout)

        # set up model function selection widget
        self.module_combo = self.addModuleComboBox()
        self.module_combo.currentTextChanged.connect(self.moduleChanged)

        self.model_list = QtWidgets.QListWidget()
        self.layout.addWidget(self.model_list)
        self.moduleChanged(self.module_combo.currentText())
        self.model_list.currentItemChanged.connect(self.modelChanged)


    def addModuleComboBox(self):
        """ Set up the model function drop down manual widget.
        """
        combo = QtWidgets.QComboBox()
        for module_name in MODELS:
            combo.addItem(module_name)
        self.layout.addWidget(combo)
        return combo

    @Slot(str)
    def moduleChanged(self, current_module):
        self.model_list.clear()
        for model_name in MODELS[current_module]:
            self.model_list.addItem(model_name)


    @Slot(QtWidgets.QListWidgetItem, QtWidgets.QListWidgetItem)
    def modelChanged(self,
                     current: QtWidgets.QListWidgetItem,
                     previous: QtWidgets.QListWidgetItem):
        """ Process a change in fit model selection.
        Will update the parameter table based on the new selection.
        """
        if current is not None:
            print (current.text())
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