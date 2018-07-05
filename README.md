# plottr: (live) plotting

A simple GUI tool for plotting measurement data (e.g., for live plotting). It runs as a standalone server, and data can be sent to it via a network socket, which makes it fairly independent of the tools used to measure. 

There's little documentation at this point, but there is a list of examples in the notebooks in the doc/ folder.

## Usage: 
* run the standalone program plottr.py (e.g. through the .bat file)
* In your working process (i.e., ipython session, jupyter notebook, ...) use one of the client tools to package the data correctly (or do it yourself) and send it (see examples!). 
* If you're using qcodes with the dataset v2, there's also a subscriber that 
you can use with the dataset (see examples!)

# inspectr: QCoDeS dataset inspection

You can use the inspectr tool to get a simple overview over QCoDeS database 
files.

## Usage:

* start the standalone program inspectr.py
* drag and drop a .db file into the main window after launching
* if plottr is running, a double click on a row in the dataset table in the 
inspectr window will send the data to plottr where it is visualized.

# Requirements:
* python >= 3.6 (f-strings...)
* the usual: numpy, mpl, ...
* pandas >= 0.22
* xarray
