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

# OPEN_MODULE_ICON = QtGui.QIcon(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_DirOpenIcon))
# REFRESH_MODULE_ICON = QtGui.QIcon(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))


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
        # refresh_button = QtWidgets.QPushButton(REFRESH_MODULE_ICON, "")
        refresh_button = QtWidgets.QPushButton("↻")
        refresh_button.clicked.connect(self.moduleRefreshClicked)
        refresh_button.setSizePolicy(QtWidgets.QSizePolicy.Fixed,
                                     QtWidgets.QSizePolicy.Fixed)
        module_sel_grid.addWidget(refresh_button, 0, 1)
        # add module button
        # open_button = QtWidgets.QPushButton(OPEN_MODULE_ICON,"")
        open_button = QtWidgets.QPushButton("+")
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


        # parameter table
        self.param_table = QtWidgets.QTableWidget(0, 4)
        self.param_table.setHorizontalHeaderLabels([
            'fix', 'initial guess', 'lower bound', 'upper bound'])
        self.param_table.horizontalHeader(). \
            setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.layout.addWidget(self.param_table)

        # fitting update options
        self.addUpdateOptions()

        # getter and setter
        # self.optGetters['fitting_model'] = self.fittingOptionGetter
        # self.optSetters['fitting_model'] = self.fittingOptionSetter
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
            self.param_table.setRowCount(0)
            return
        current_module = self.fitting_modules[self.module_combo.currentText()]
        model_cls = getattr(current_module, current.text())
        print(model_cls.model.__code__)
        self.updateParamTable(model_cls)
        self.model_doc_box.setText(model_cls.model.__doc__)

    def updateParamTable(self, model_cls: Type[Fit]):
        """ Update the parameter table based on the current model selection.
        :param model_cls: the current selected fitting model class
        """
        # flush param table
        self.param_table.setRowCount(0)
        # rebuild param table based on the selected model function
        func = model_cls.model
        # assume the first variable is the independent variable
        params = list(inspect.signature(func).parameters)[1:]
        self.param_table.setRowCount(len(params))
        self.param_table.setVerticalHeaderLabels(params)
        # generate fix, initial guess, lower/upper bound option GUIs for each
        # parameter
        self.param_signals = []
        for idx, name in enumerate(params):
            fixParamCheck = self._paramFixCheck()
            fixParamCheck.setStyleSheet("margin-left:10%; margin-right:10%;")
            initialGuessBox = OptionSpinbox(1.0, self)
            lowerBoundBox = NumberInput(None, self)
            upperBoundBox = NumberInput(None, self)
            lowerBoundBox.newTextEntered.connect(initialGuessBox.setMinimum)
            upperBoundBox.newTextEntered.connect(initialGuessBox.setMaximum)

            # gather the param change signals for enabling live update
            self.param_signals.extend((fixParamCheck.stateChanged,
                                       initialGuessBox.valueChanged,
                                       lowerBoundBox.newTextEntered,
                                       upperBoundBox.newTextEntered))
            # put param options into table
            self.param_table.setCellWidget(idx, 0, fixParamCheck)
            self.param_table.setCellWidget(idx, 1, initialGuessBox)
            self.param_table.setCellWidget(idx, 2, lowerBoundBox)
            self.param_table.setCellWidget(idx, 3, upperBoundBox)

        self.changeParamLiveUpdate(self.live_update)

    def _paramFixCheck(self, default_value: bool = False):
        """generate a push checkbox for the parameter fix option.
        :param default_value : param is fixed by default or not
        :returns: a checkbox widget
        """
        widget = QtWidgets.QCheckBox('')
        widget.setChecked(default_value)
        widget.setToolTip("when fixed, the parameter will be fixed to the "
                          "initial guess value during fitting")
        return widget

    def addUpdateOptions(self):
        ''' Add check box & buttons that control the fitting update policy.
        '''
        widget = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout()
        # when checked, fitting will update after each change of fitting model
        # or parameter option
        liveUpdateCheck = QtWidgets.QCheckBox('Live Update')
        grid.addWidget(liveUpdateCheck, 0, 0)
        # update fitting on-demand
        updateButton = QtWidgets.QPushButton("Update")
        grid.addWidget(updateButton, 0, 1)
        # reload the fitting options that come from the data
        reloadInputOptButton = QtWidgets.QPushButton("Reload Input Option")
        grid.addWidget(reloadInputOptButton, 0, 2)

        @Slot(QtCore.Qt.CheckState)
        def setLiveUpdate(live: QtCore.Qt.CheckState):
            ''' connect/disconnects the changing signal of each fitting
            option to signalAllOptions slot
            '''
            if live == QtCore.Qt.Checked:
                self.model_list.currentItemChanged.connect(self._signalAllOptions)
                self.changeParamLiveUpdate(True)
                self.live_update = True
            else:
                try:
                    self.model_list.currentItemChanged.disconnect(
                        self._signalAllOptions)
                except TypeError:
                    pass
                self.changeParamLiveUpdate(False)
                self.live_update = False

        @Slot()
        def reloadInputOption():
            print("reload input option")
            # self.fittingOptionSetter(self.input_options)

        liveUpdateCheck.stateChanged.connect(setLiveUpdate)
        updateButton.pressed.connect(self.signalAllOptions)
        reloadInputOptButton.pressed.connect(reloadInputOption)
        reloadInputOptButton.setToolTip('reload the fitting options stored '
                                        'in the input data')

        widget.setLayout(grid)
        self.layout.addWidget(widget)

    def changeParamLiveUpdate(self, enable: bool):
        ''' connect/disconnects the changing signal of each fitting param
        option to signalAllOptions slot
        :param enable: connect/disconnect when enable is True/False.
        '''
        if enable:
            for psig in self.param_signals:
                psig.connect(self._signalAllOptions)
        else:
            for psig in self.param_signals:
                try:
                    psig.disconnect(self._signalAllOptions)
                except TypeError:
                    pass



    def _signalAllOptions(self, *args):
        # to make the signalAllOptions accept signals w/ multi args
        print("signal option change")
        self.signalAllOptions()

class OptionSpinbox(QtWidgets.QDoubleSpinBox):
    """A spinBox widget for parameter options
    :param default_value : default value of the option
    """

    # TODO: Support easier input for large numbers
    def __init__(self, default_value=1.0, parent=None):
        super().__init__(parent)
        self.setRange(-1 * MAX_FLOAT, MAX_FLOAT)
        self.setValue(default_value)

    def setMaximum(self, maximum):
        try:
            value = eval(maximum)
        except:
            value = MAX_FLOAT
        if isinstance(value, numbers.Number):
            super().setMaximum(value)
        else:
            super().setMaximum(MAX_FLOAT)

    def setMinimum(self, minimum):
        try:
            value = eval(minimum)
        except:
            value = -1 * MAX_FLOAT
        if isinstance(value, numbers.Number):
            super().setMinimum(value)
        else:
            super().setMinimum(-1 * MAX_FLOAT)


class NumberInput(QtWidgets.QLineEdit):
    """A text edit widget that checks whether its input can be read as a
    number.
    This is copied form the parameter GUI that Wolfgang wrote for the
    parameter manager gui.
    """
    newTextEntered = Signal(str)

    def __init__(self, default_value, parent=None):
        super().__init__(parent)
        self.setValue(default_value)
        self.editingFinished.connect(self.emitNewText)

    def value(self):
        try:
            value = eval(self.text())
        except:
            return None
        if isinstance(value, numbers.Number):
            return value
        else:
            return None

    def setValue(self, value):
        self.setText(str(value))

    def emitNewText(self):
        self.newTextEntered.emit(self.text())


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