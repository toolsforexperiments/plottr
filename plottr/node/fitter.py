import sys
import os
import pkgutil
import importlib
from importlib import reload, import_module
import warnings
from typing import Dict, Optional, Type, Callable, Tuple, Any, List, Union
import inspect
from dataclasses import dataclass
import numbers
from types import ModuleType

import lmfit
from lmfit import Parameter as lmParameter, Parameters as lmParameters

from plottr import QtGui, QtCore, Slot, Signal, QtWidgets
from plottr.analyzer import fitters
from plottr.analyzer.fitters.fitter_base import Fit, FitResult

from ..data.datadict import DataDictBase
from .node import Node, NodeWidget, updateOption, updateGuiFromNode

__author__ = 'Chao Zhou'
__license__ = 'MIT'


def reload_module_get_model(module: ModuleType) -> Tuple[ModuleType, Dict[str, type]]:
    '''Gather the model classes in the the fitting module file
    :return : a dictionary that contains all the model classed in the module
    '''
    def is_Fit_subclass(cls: Type[Fit]) -> bool:
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
    return module, model_dict

def get_modules_in_pkg(pkg: ModuleType) -> Dict[str, ModuleType]:
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

DEBUG = 1



@dataclass
class FittingOptions:
    model: Type[Fit]
    parameters: lmParameters
    dry_run: bool = False


class FittingGui(NodeWidget):
    """ Gui for controlling the fitting function and the initial guess of
    fitting parameters.
    """
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, node: Optional[Node] = None):

        super().__init__(parent)
        self.input_options: Optional[FittingOptions] = None # fitting option in dataIn
        self.live_update = False
        self.dry_run = False
        self.param_signals: List[QtCore.pyqtBoundSignal] = []
        self.fitting_modules = INITIAL_MODULES
        self.my_layout = QtWidgets.QGridLayout()
        self.setLayout(self.my_layout)

        # fitting module widgets
        module_sel_widget = QtWidgets.QWidget()
        module_sel_grid = QtWidgets.QGridLayout()
        # model function selection widget
        self.module_combo = self.addModuleComboBox()
        self.module_combo.currentTextChanged.connect(self.moduleUpdate)
        self.module_combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                        QtWidgets.QSizePolicy.Fixed)
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
        self.my_layout.addWidget(module_sel_widget, 0, 0)


        # model list widget
        self.model_list = QtWidgets.QListWidget()
        self.moduleUpdate(self.module_combo.currentText())
        self.model_list.currentItemChanged.connect(self.modelChanged)

        # function description window
        self.model_doc_box = QtWidgets.QLineEdit("")
        self.model_doc_box.setReadOnly(True)

        # splitter1
        splitter1 = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        splitter1.addWidget(self.model_list)
        splitter1.addWidget(self.model_doc_box)

        # parameter table
        self.param_table = QtWidgets.QTableWidget(0, 4)
        self.param_table.setHorizontalHeaderLabels([
            'fix', 'initial guess', 'lower bound', 'upper bound'])
        self.param_table.horizontalHeader(). \
            setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.param_table.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                        QtWidgets.QSizePolicy.Expanding)

        # splitter2
        splitter2 = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        splitter2.addWidget(splitter1)
        splitter2.addWidget(self.param_table)
        self.my_layout.addWidget(splitter2, 1, 0)

        # fitting update options
        self.update_option_widget = self.addUpdateOptions()
        self.my_layout.addWidget(self.update_option_widget, 2, 0)


        # getter and setter
        self.optGetters['fitting_options'] = self.fittingOptionGetter
        self.optSetters['fitting_options'] = self.fittingOptionSetter

    def addModuleComboBox(self) -> QtWidgets.QComboBox:
        """ Set up the model function drop down manual widget.
        """
        combo = QtWidgets.QComboBox()
        combo.setEditable(False)
        for module_name in self.fitting_modules:
            combo.addItem(module_name)
        return combo

    @Slot(str)
    def moduleUpdate(self, current_module_name: str) -> None:
        if DEBUG:
            print ("GUI...: ", "moduleUpdate called. Updating",current_module_name)
        self.model_list.clear()
        current_module = self.fitting_modules[current_module_name]
        # update the module in console and get models in new module
        new_module, new_models = reload_module_get_model(current_module)
        for model_name in new_models:
            self.model_list.addItem(model_name)
        self.fitting_modules[current_module_name] = new_module
        # debug-------------------------------------------
        '''
        # fitters.generic_functions.Cosine.pp(1)
        try:
            test = self.fitting_modules[current_module_name].Exponential2
            print("Exponential2 is here!!!!!")
        except :
            print("No Exponential2 :( ")
        '''
        #-------------------------------------------------

    @Slot()
    def moduleRefreshClicked(self) -> None:
        self.moduleUpdate(self.module_combo.currentText())

    def add_user_module(self) -> None:
        mod_file = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Open file',fitters.__path__[0], "Python files (""*.py)")[0]
        if (mod_file is None) or mod_file[-3:] !=".py":
            return
        mod_name = mod_file.split('/')[-1][:-3]
        mod_dir = '\\'.join(mod_file.split('/')[:-1])
        # load the selected module
        sys.path.append(mod_dir)
        user_module = import_module(mod_name, mod_dir)

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
                     previous: QtWidgets.QListWidgetItem) -> None:
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
        self.updateParamTable(model_cls)
        self.model_doc_box.setText(model_cls.model.__doc__)

    def updateParamTable(self, model_cls: Type[Fit]) -> None:
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
            fixParamCheck.setStyleSheet("margin-left:15%; margin-right:5%;")
            initialGuessBox = OptionSpinbox(1.0, self)
            lowerBoundBox = NumberInput(None, self)
            upperBoundBox = NumberInput(None, self)
            lowerBoundBox.newTextEntered.connect(initialGuessBox.setMinimum)
            upperBoundBox.newTextEntered.connect(initialGuessBox.setMaximum)

            # gather the param change signals for enabling live update
            self.param_signals.extend([fixParamCheck.stateChanged,
                                       initialGuessBox.valueChanged,
                                       lowerBoundBox.newTextEntered,
                                       upperBoundBox.newTextEntered])
            # put param options into table
            self.param_table.setCellWidget(idx, 0, fixParamCheck)
            self.param_table.setCellWidget(idx, 1, initialGuessBox)
            self.param_table.setCellWidget(idx, 2, lowerBoundBox)
            self.param_table.setCellWidget(idx, 3, upperBoundBox)

        self.changeParamLiveUpdate(self.live_update)

    def _paramFixCheck(self, default_value: bool = False) -> QtWidgets.QCheckBox:
        """generate a push checkbox for the parameter fix option.
        :param default_value : param is fixed by default or not
        :returns: a checkbox widget
        """
        widget = QtWidgets.QCheckBox('')
        widget.setChecked(default_value)
        widget.setToolTip("when fixed, the parameter will be fixed to the "
                          "initial guess value during fitting")
        return widget

    def addUpdateOptions(self) -> QtWidgets.QWidget:
        ''' Add check box & buttons that control the fitting update policy.
        '''
        update_option_widget = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout()
        # when checked, fitting will update after each change of fitting model
        # or parameter option
        liveUpdateCheck = QtWidgets.QCheckBox('Live Update')
        grid.addWidget(liveUpdateCheck, 0, 0)
        # update fitting on-demand
        updateFitButton = QtWidgets.QPushButton("Fit")
        grid.addWidget(updateFitButton, 0, 1)
        # guess fitting parameters and show the dry run result
        guessParamButton = QtWidgets.QPushButton("Guess Parameters")
        grid.addWidget(guessParamButton, 0, 2)
        # reload the fitting options that come from the data
        reloadInputOptButton = QtWidgets.QPushButton("Reload Input Option")
        grid.addWidget(reloadInputOptButton, 0, 3)

        @Slot(QtCore.Qt.CheckState)
        def setLiveUpdate(live: QtCore.Qt.CheckState) -> None:
            ''' connect/disconnects the changing signal of each fitting
            option to signalAllOptions slot
            '''
            if live == QtCore.Qt.Checked:
                self.model_list.currentItemChanged.connect(
                    self._signalAllOptions)
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
        def reloadInputOption() -> None:
            if DEBUG:
                print("GUI...: ", "reload input option")
            self.fittingOptionSetter(self.input_options)

        @Slot()
        def setGuessParam() -> None:
            if DEBUG:
                print("GUI...: ", "setGuessParam called, setting fitting parameter to guess")
            if self.model_list.currentItem() is None:
                return
            self.dry_run = True
            self.signalAllOptions()

        liveUpdateCheck.stateChanged.connect(setLiveUpdate)
        updateFitButton.pressed.connect(self.signalAllOptions)
        guessParamButton.pressed.connect(setGuessParam)
        reloadInputOptButton.pressed.connect(reloadInputOption)
        reloadInputOptButton.setToolTip('reload the fitting options stored '
                                        'in the input data')

        update_option_widget.setLayout(grid)
        return update_option_widget

    def changeParamLiveUpdate(self, enable: bool) -> None:
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

    def getCurrentModel(self) -> Optional[Type[Fit]]:
        """
        get the current model selected
        """
        current_module = self.fitting_modules[self.module_combo.currentText()]
        model_selected = self.model_list.currentItem()
        if model_selected is None:
            return None
        model = getattr(current_module, model_selected.text())
        return model


    def fittingOptionGetter(self) -> Optional[FittingOptions]:
        """ get all the fitting options and put them into a dictionary
        """
        if DEBUG:
            print("GUI...: ", 'getter in gui called')
        # get the current model selected
        model = self.getCurrentModel()
        if model is None:
            return None
        # get the parameters for current model
        parameters = lmParameters()
        for i in range(self.param_table.rowCount()):
            table_item = self.param_table.verticalHeaderItem(i)
            assert isinstance(table_item, QtWidgets.QTableWidgetItem)
            param_name = table_item.text()
            param = lmParameter(param_name)
            item0 = self.param_table.cellWidget(i, 0)
            item1 = self.param_table.cellWidget(i, 1)
            item2 = self.param_table.cellWidget(i, 2)
            item3 = self.param_table.cellWidget(i, 3)
            assert isinstance(item0, QtWidgets.QCheckBox)
            assert isinstance(item1, OptionSpinbox)
            assert isinstance(item2, NumberInput)
            assert isinstance(item3, NumberInput)
            param.vary = not item0.isChecked()
            param.value = item1.value()
            param.min = item2.value()
            param.max = item3.value()
            parameters[param_name] = param

        fitting_options = FittingOptions(model, parameters, self.dry_run)
        if DEBUG:
            print("GUI...: ", 'getter in gui got', fitting_options)
        return fitting_options

    def fittingOptionSetter(self, fitting_options: Optional[FittingOptions]) -> None:
        """ Set all the fitting options
        """
        if DEBUG:
            print("GUI...: ", 'setter in gui called')
        if fitting_options is None:
            return
        # set the model in gui
        model = fitting_options.model
        if DEBUG:
            print("GUI...: ", f"setter trying to set model to {model}")
        # try to find the module that contains the model first
        module_exist = False
        for mdu_name, mdu in self.fitting_modules.items():
            if mdu.__file__ == inspect.getsourcefile(model):
                self.module_combo.setCurrentText(mdu_name)
                if DEBUG:
                    print("GUI...: ", f"setter set module to {mdu_name}")
                module_exist = True
                break
        # set the model in model list
        if module_exist:
            model_cls_name = model.__qualname__
            find_mdls = self.model_list.findItems(model_cls_name,
                                                  QtCore.Qt.MatchExactly)
            if len(find_mdls) == 1:
                self.model_list.setCurrentItem(find_mdls[0])
            else:
                if DEBUG:
                    print("GUI...: ", "unexpected Error when trying to find the module")
                    print(model_cls_name)
                else:
                    raise NameError("GUI...: ", "unexpected Error when trying to find the module")
        else:
            #TODO: fix this, add the new model to gui
            raise NotImplementedError("auto add new model to gui")

        # set the parameter table in gui
        for i in range(self.param_table.rowCount()):
            table_item = self.param_table.verticalHeaderItem(i)
            assert isinstance(table_item, QtWidgets.QTableWidgetItem)
            param_name = table_item.text()
            param_options = fitting_options.parameters[param_name]

            item0 = self.param_table.cellWidget(i, 0)
            item1 = self.param_table.cellWidget(i, 1)
            item2 = self.param_table.cellWidget(i, 2)
            item3 = self.param_table.cellWidget(i, 3)
            assert isinstance(item0, QtWidgets.QCheckBox)
            assert isinstance(item1, OptionSpinbox)
            assert isinstance(item2, NumberInput)
            assert isinstance(item3, NumberInput)

            item0.setChecked(not param_options.vary)
            item1.setValue(param_options.value)
            item2.setValue(param_options.min)
            item3.setValue(param_options.max)
        self.dry_run = fitting_options.dry_run

    def _signalAllOptions(self, *args: Any) -> None:
        # to make the signalAllOptions accept signals w/ multi args
        if DEBUG:
            print("GUI...: ", "signal all option change")
        if self.model_list.currentItem() is not None:
            self.signalAllOptions()

    @updateGuiFromNode
    def setDefaultFit(self, fitting_options: FittingOptions) -> None:
        ''' set the gui to the fitting options in the input data
        '''
        if DEBUG:
            print("GUI...: ", f'updateGuiFromNode setDefault got {fitting_options}')
        if self.fittingOptionGetter() is None:
            self.fittingOptionSetter(fitting_options)
        self.input_options = fitting_options

    @updateGuiFromNode
    def setGuessParam(self, fitting_options: FittingOptions) -> None:
        """ set the parameter to the guess parameter from guess function
        """
        if DEBUG:
            print("GUI...: ", f'updateGuiFromNode setGuessParam got {fitting_options}')
        self.fittingOptionSetter(fitting_options)


class OptionSpinbox(QtWidgets.QDoubleSpinBox):
    """A spinBox widget for parameter options
    :param default_value : default value of the option
    """

    # TODO: Support easier input for large numbers
    def __init__(self, default_value: float = 1.0, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setRange(-1 * MAX_FLOAT, MAX_FLOAT)
        self.setValue(default_value)

    def setMaximum(self, maximum: str) -> None:  # type: ignore[override]
        try:
            value = eval(maximum)
        except:
            value = MAX_FLOAT
        if isinstance(value, float):
            super().setMaximum(value)
        else:
            super().setMaximum(MAX_FLOAT)

    def setMinimum(self, minimum: str) -> None:  # type: ignore[override]
        try:
            value = eval(minimum)
        except:
            value = -1 * MAX_FLOAT
        if isinstance(value, float):
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

    def __init__(self, default_value: Union[numbers.Number, None], parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setValue(default_value)
        self.editingFinished.connect(self.emitNewText)

    def value(self) -> Optional[numbers.Number]:
        try:
            value = eval(self.text())
        except:
            return None
        if isinstance(value, numbers.Number):
            return value
        else:
            return None

    def setValue(self, value: Union[numbers.Number, None]) -> None:
        self.setText(str(value))

    def emitNewText(self) -> None:
        self.newTextEntered.emit(self.text())


# ================= Node ==============================
class FittingNode(Node):
    uiClass = FittingGui
    nodeName = "Fitter"
    default_fitting_options = Signal(object)
    guess_fitting_options = Signal(object)

    def __init__(self, name: str):
        super().__init__(name)
        self._fitting_options: Optional[FittingOptions] = None

    def process(self, dataIn: Optional[DataDictBase] = None) -> Optional[Dict[str, Optional[DataDictBase]]]:
        return self.fitting_process(dataIn)

    @property
    def fitting_options(self) -> Optional[FittingOptions]:
        return self._fitting_options

    @fitting_options.setter
    @updateOption('fitting_options')
    def fitting_options(self, opt: Optional[FittingOptions]) -> None:
        if isinstance(opt, FittingOptions) or opt is None:
            self._fitting_options = opt
        else:
            raise TypeError('Wrong fitting options')

    def fitting_process(self, dataIn: Optional[DataDictBase] = None) -> Optional[Dict[str, Optional[DataDictBase]]]:
        if dataIn is None:
            return None

        if len(dataIn.axes()) > 1 or len(dataIn.dependents()) > 1:
            return dict(dataOut=dataIn)

        dataIn_opt = dataIn.get('__fitting_options__')
        dataOut = dataIn.copy()

        # no fitting option selected in gui
        if self.fitting_options is None:
            if dataIn_opt is not None:
                self._fitting_options = dataIn_opt
            else:
                return dict(dataOut=dataOut)

        if dataIn_opt is not None:
            if DEBUG:
                print("NODE>>>: ", "Emit initial option from node!", dataIn_opt)
            self.default_fitting_options.emit(dataIn_opt)

        # fitting
        if DEBUG:
            print("NODE>>>: ", f"node got fitting option {self.fitting_options}")

        axname = dataIn.axes()[0]
        x = dataIn.data_vals(axname)
        y = dataIn.data_vals(dataIn.dependents()[0])

        assert isinstance(self.fitting_options, FittingOptions)
        fit = self.fitting_options.model(x, y)
        if self.fitting_options.dry_run:
            guess_params = lmParameters()
            for pn, pv in fit.guess(x, y).items():
                guess_params.add(pn, value=pv)
            guess_opts = FittingOptions(self.fitting_options.model,
                                        guess_params, False)
            self.guess_fitting_options.emit(guess_opts)
            if DEBUG:
                print("NODE>>>: ", f"guess param in node. Emit guess_opts: {guess_opts}")
            # show dry run result
            fit_result = fit.run(dry=True)
            result_y = fit_result.eval(coordinates=x)
            dataOut['guess'] = dict(values=result_y, axes=[axname, ])
        else:
            fit_result = fit.run(params=self.fitting_options.parameters)
            assert isinstance(fit_result, FitResult)
            lm_result = fit_result.lmfit_result
            if lm_result.success:
                dataOut['fit'] = dict(values=lm_result.best_fit, axes=[axname,])
                dataOut.add_meta('info', lm_result.fit_report())

        return dict(dataOut=dataOut)

    def setupUi(self) -> None:
        super().setupUi()
        assert isinstance(self.ui, FittingGui)
        self.default_fitting_options.connect(self.ui.setDefaultFit)
        self.guess_fitting_options.connect(self.ui.setGuessParam)

