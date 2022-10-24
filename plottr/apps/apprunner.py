"""
Script through which new Apps are opened by the :class:plottr.apps.appmanager.AppManager.
All the arguments in the script are the arguments for :class:plottr.apps.appmanager.App
"""

import sys
import importlib
import argparse

from plottr import qtapp
from plottr.apps.appmanager import App


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Script to open apps"
    )
    parser.add_argument('port', help='The port this process should communicate through', default="12345")
    parser.add_argument('module', default="plottr.apps.autoplot")
    parser.add_argument('function', default='autoplotDDH5App')
    parser.add_argument('app_arguments', nargs='*', default=["/home/msmt/Documents/code_playground/Slider playground/data/manual_data/simple_data.ddh5", 'data'])

    args = parser.parse_args()
    port = int(args.port)
    full_module = args.module
    func_name = args.function
    extra_arguments = tuple(args.app_arguments)

    application = qtapp()
    module = importlib.import_module(full_module)
    func = getattr(module, func_name)
    app = App(func, port, None, extra_arguments)
    sys.exit(application.exec_())

