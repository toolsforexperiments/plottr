# plottr: modular data plotting and processing

A framework for inspecting data, based on flowcharts from *pyqtgraph*.
*plottr*'s main aim is to allow the user to define custom data processing flows and plotting.
A particular use case is data filtering and plotting.

## Documentation: 
https://plottr.readthedocs.io (work in progress...)

## Recent changes:

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

In brief: clone the repo, and install using `pip install -e`

## inspectr: QCoDeS dataset inspection and (live) plotting

You can use the `inspectr` tool to get a simple overview over QCoDeS database
files, and plot datasets contained in the database.

To use: from the root of the cloned plottr repository, run `python apps/inspectr.py [--dbpath <path to your .db file>]`

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

## python package

clone the repo, and install using `pip install -e plottr/`.
