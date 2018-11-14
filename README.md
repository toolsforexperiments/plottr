# plottr: modular plotting and processing

A framework for inspecting data, based on flowcharts from *pyqtgraph*. 
*plottr*'s main aim is to allow the user to define custom data processing flows and plotting.
A particular use case is data filtering and plotting.

## Interactive usage: 

For now, check out the Notebook *Interactive data inspection* under `/doc/`.

# inspectr: QCoDeS dataset inspection

You can use the inspectr tool to get a simple overview over QCoDeS database 
files, and plot datasets contained in the database.

## Usage:

* from within the plottr-directory, run `python apps/inspectr.py --dbpath <path to your `

# Installation

Note: this package is not compatible with the original plottr tool, and this new version does not (yet!) support live plotting of qcodes data. If you want to keep using the old plottr for that, you probably want to create a new environment for this version.
(But rest assured, live plotting is all the way up on the priority list ;))

## Requirements:
* python >= 3.6 (f-strings...)
* the usual: numpy, mpl, ...
* pandas >= 0.22
* xarray
* pyqtgraph >= 0.10.0

## python package

clone the repo, and install using `pip -e plottr/`. 


