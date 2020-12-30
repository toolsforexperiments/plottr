import sys
import pkgutil
from importlib import reload, import_module
import warnings
from typing import Dict, Optional, Type
import inspect
from dataclasses import dataclass
import numbers

import lmfit
import numpy as np

from plottr import QtGui, QtCore, Slot, Signal, QtWidgets
from plottr.analyzer import fitters
from plottr.analyzer.fitters import generic_functions
from plottr.analyzer.fitters.fitter_base import Fit


# __author__ = 'Chao Zhou'
# __license__ = 'MIT'
#
# def get_models_in_module(module):
#     '''Gather the model classes in the the fitting module
#     '''
#     def is_Fit_subclass(cls: Type[Fit]):
#         """ check if a class is the subclass of analyzer.fitters.fitter_base.Fit
#         """
#         try:
#             if issubclass(cls, Fit) and (cls is not Fit):
#                 return True
#             else:
#                 return False
#         except TypeError:
#             return False
#     model_classes = inspect.getmembers(module, is_Fit_subclass)
#     model_dict = {}
#     for mc in model_classes:
#         model_dict[mc[0]] = mc[1]
#     return model_dict
#
# def get_modules_in_pkg(pkg):
#     modules = []
#     for importer, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
#         if modname != "fitter_base":
#             module_ = import_module('.'+modname, pkg.__name__)
#             reload(module_)
#             modules.append(modname)
#     return modules
#
# def get_all_models_in_pkg(pkg):
#     model_dict = {}
#     modules = get_modules_in_pkg(pkg)
#     for m in modules:
#         model_dict[m] = get_models_in_module(getattr(pkg, m))
#     return model_dict
#
# MODELS = get_all_models_in_pkg(fitters)
#
# # MODELS = get_all_models_in_pkg(fitters)
# # MODELS = get_models_in_module(generic_functions)
# im = list(pkgutil.iter_modules(fitters.__path__))



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
    modules = {}
    for importer, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
        if modname != "fitter_base":
            module_ = import_module('.'+modname, pkg.__name__)
            try:
                del sys.modules[module_.__name__]
            except:
                pass
            module_ = import_module('.'+modname, pkg.__name__)
            # reload(module_)
            modules[modname] = module_
    return modules

# def get_all_models_in_pkg(pkg):
#     model_dict = {}
#     modules = get_modules_in_pkg(pkg)
#     for m in modules:
#         model_dict[m] = get_models_in_module(getattr(pkg, m))
#     return model_dict

INITIAL_MODULES = get_modules_in_pkg(fitters)