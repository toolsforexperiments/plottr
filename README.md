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

# Quickstart

## Installation

Plottr is installable from pypi with `pip install plottr`

Plottr requires either the PyQt5 or Pyside2 gui framework.
To install with PyQt5 or Pyside2 backend you can do
``pip install plottr[PyQt5]`` or ``pip install plottr[Pyside2]`` 

Note that if  you have installed ``pyqt`` from ``(Ana)Conda`` you should not use any of these
targets but do ``pip install plottr`` or install Plottr from conda forge:

```
conda config --add channels conda-forge
conda config --set channel_priority strict
conda install plottr
```

To install from source: clone the repo, and install using `pip install -e .`

## inspectr: QCoDeS dataset inspection and (live) plotting

You can use the `inspectr` tool to get a simple overview over QCoDeS database
files, and plot datasets contained in the database.

To use: run `plottr-inspectr [--dbpath <path to your .db file>]` 
 
As an alternative from the root of the cloned plottr repository, run `python apps/inspectr.py [--dbpath <path to your .db file>]`

For basic instructions, check out the Notebook *Live plotting qcodes data* under `/doc/examples`.

## Some notes on installing

Note: this package is not compatible with the original `plottr` tool.
You might want to install freshly if you still use the old version.

## Requirements:
* python >= 3.7 (f-strings...)
* the usual: numpy, mpl, ...
* pandas >= 0.22
* xarray
* pyqtgraph >= 0.10.0

# Recent changes:

## v0.8.1 2021-11-30

### Added

- Test with python 3.10 and mark as supported (#238)

### Fixed

- add missing init file to config dir (#236)
- Use a regular install in tests (#237)

## v0.8.0 2021-11-11

### Added

- Inspectr: tag a run with a star (⭐) or cross (❌) icon, filter by those,
  also show dataset metadata next to parameters and snapshot (#229)
- Improvements to monitr: more stability in adding data to ddh5, better
  performance by making data loading multithreaded and running reach plot
  window in a separate process (#219)
- Added pyqtgraph backend for plotting that can be used instead of matplotlib
  (Example for how to select can be found in test/apps/autoplot_app.py) (#215, #218)

### Fixed

- Fix/invaliddata: small fixes when data contains a lot of invalid entries (#226)
- Fix in shape recognition when adding data (#220)

### Behind the scenes

- Add minimal versions to dependencies (#201)
- Make the .gitignore proper (#73)
- add dependabot (#208)
- Fix typechecking with mypy 0.9xx (#207)
- clarify install instructions wrt qt and mention conda forge (#202)

## 2021-06-08

### Added

- refactoring the plotting system (#166)
- Add version log message to main ``__init__`` (#175)

### Fixed

- Fix crop if less than one row is not nan (#198)
- Fix rgba error (#199)
- Allow empty dataset if datadict is none (#195)

### Behind the scenes

- Modernize setup files (#194)
- packaging cleanups (#177)
- upgrade versioneer to 0.19 (#176)

## 2021-02-16

### Added

- Add copy content features to inspectr and autoplot windows, specifically
  - a new Copy pop up menu for copying content of cells in inspectr
  - a new Copy metadata button in plot window for copying info about the dataset to clipboard

### Fixed

- remove redundant information between the optional "info" box on the plot and the plot title

## 2021-02-08

- Drop support for Python 3.6 and support type-checking with qcodes 0.21.0
- Fix type-checking with numpy 1.20

### Fixed
- Fixed y-axis to not show axis-label if more than one plot is selected in 1D single-plot show.

## 2020-08-21

- Workaround for bug with pyqt installed via conda that would result in blank icons.
- Add experimental support for using Pyside2 as an alternative to PyQt5

## 2020-08-06

### Added

- Entry points for inspectr (plottr-inspectr) and autoplot (plottr-autoplot-ddh5) 
- LICENSE file has been added (no change to license of the code)
- setup.py has been tweeked to ensure that sdist and bdist_wheel packages are generated correctly

## 2020-06-05

### Added

- Usable version of hdf5 file support. can use the apps/monitr.py script to launch a tool that allows easy (live) plotting.

## 2020-04-24

### Fixed

- there were several issues/annoyances that caused (minor) issues with grid handling and plotting in rare-ish circumstances. Most of them should be fixed now.

### Added

- A few docs and examples, mostly about grid usage.

## 2020-04-17

### Changed

- the main repo has now moved to to a different organization: https://github.com/toolsforexperiments/plottr 
  the old repo (https://github.com/data-plottr/plottr) will be kept in sync for a while, but deleted eventually.
