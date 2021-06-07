import sys
import os
import argparse
import importlib
import inspect

from plottr import QtWidgets, plottrPath


def run(func, **kw):
    app = QtWidgets.QApplication([])
    _ = func(**kw)
    return app.exec_()


def get_functions():
    testdir = os.path.join(plottrPath, '..', 'test')
    testsdir = os.path.join(testdir, 'gui')
    sys.path.append(testdir)
    mods = []
    functions = {}

    for fn in os.listdir(testsdir):
        try:
            path = f"gui.{os.path.splitext(fn)[0]}"
            if '__' not in path:
                mod = importlib.import_module(path)
                mods.append(mod)
        except:
            pass

    for mod in mods:
        for name, fun in inspect.getmembers(mod):
            if inspect.isfunction(fun) and 'test_' in name:
                functions[f"{mod.__name__}.{name}"] = \
                    dict(func=fun, signature=inspect.signature(fun))

    return functions


if __name__ == '__main__':
    funcs = get_functions()
    names_help = "available test functions: "
    for f, desc in funcs.items():
        names_help += f"\n - {f} {desc['signature']}"

    parser = argparse.ArgumentParser(description='Testing data display widgets',
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('name', help=names_help, default=None, metavar='NAME',
                        choices=list(funcs.keys()))
    parser.add_argument("--kwargs", help="keyword arguments for the function",
                        default={})

    args = parser.parse_args()

    print(f'Running {args.name} with options: {args.kwargs}. \n')
    kwargs = {}
    if args.kwargs != {}:
        kwargs = eval(args.kwargs)
    run(funcs[args.name]['func'], **kwargs)
