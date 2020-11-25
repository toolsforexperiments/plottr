# plottr: modular data plotting and processing

[![PyPi version](https://badge.fury.io/py/plottr.svg)](https://badge.fury.io/py/plottr)
[![PyPI python versions](https://img.shields.io/pypi/pyversions/plottr.svg)](https://pypi.python.org/pypi/plottr/)
[![Docs](https://img.shields.io/badge/read%20-thedocs-ff66b4.svg)](https://plottr.readthedocs.io/en/latest/)
[![Build on GitHub actions](https://github.com/toolsforexperiments/plottr/workflows/Python%20application/badge.svg?branch=master)](https://github.com/toolsforexperiments/plottr/actions)

A framework for inspecting data, based on flowcharts from *pyqtgraph*.
*plottr*'s main aim is to allow the user to define custom data processing flows and plotting.
A particular use case is data filtering and plotting.

## Documentation: 
https://plottr.readthedocs.io (work in progress...)

## Recent changes:

## 2020-08-21

- Workaround for bug with pyqt installed via conda that would result in blank icons.
- Add experimental support for using Pyside2 as an alternative to PyQt5


## 2020-08-06

#### Added
- Entry points for inspectr (plottr-inspectr) and autoplot (plottr-autoplot-ddh5) 
- LICENSE file has been added (no change to license of the code)
- setup.py has been tweeked to ensure that sdist and bdist_wheel packages are generated correctly

### 2020-06-05

#### Added
- Usable version of hdf5 file support. can use the apps/monitr.py script to launch a tool that allows easy (live) plotting.

### 2020-04-24

#### Fixed
- there were several issues/annoyances that caused (minor) issues with grid handling and plotting in rare-ish circumstances. Most of them should be fixed now.

#### Added
- A few docs and examples, mostly about grid usage.

### 2020-04-17

#### Changed
- the main repo has now moved to to a different organization: https://github.com/toolsforexperiments/plottr 
  the old repo (https://github.com/data-plottr/plottr) will be kept in sync for a while, but deleted eventually.

# Quickstart

## Installation

Plottr is installable from pypi with `pip install plottr`

To install with either PyQt5 or Pyside2 backend you can do
``pip install plottr[PyQt5]`` or ``pip install plottr[Pyside2]`` Note that if 
you have installed ``pyqt`` from ``(Ana)Conda`` you should not use any of these
targets but do ``pip install plottr`` 

To install from source: clone the repo, and install using `pip install -e .`

## inspectr: QCoDeS dataset inspection and (live) plotting

You can use the `inspectr` tool to get a simple overview over QCoDeS database
files, and plot datasets contained in the database.

To use: run `plottr-inspectr [--dbpath <path to your .db file>]` 
 
As an alternative from the root of the cloned plottr repository, run `python apps/inspectr.py [--dbpath <path to your .db file>]`

For basic instructions, check out the Notebook *Live plotting qcodes data* under `/doc/examples`.

# Some notes on installing

Note: this package is not compatible with the original `plottr` tool.
You might want to install freshly if you still use the old version.

## Requirements:
* python >= 3.6 (f-strings...)
* the usual: numpy, mpl, ...
* pandas >= 0.22
* xarray
* pyqtgraph >= 0.10.0
