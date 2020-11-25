# from .CosineFit import CosineFit



# This is to make each fitting model class be accessible directly from analyzer.fitter
# instead of analyzer.fitter.module_name.class_name
EXCLUDE_MODULES = ['__init__.py', 'fitter_base.py']
import os
for module in os.listdir(os.path.dirname(__file__)):
    if module in EXCLUDE_MODULES  or module[-3:] != '.py':
        continue
    module_name = module[:-3]
    exec("from ." + module_name + " import " + module_name)
    # I'm not sure if this is a good way to implement this...
del module

