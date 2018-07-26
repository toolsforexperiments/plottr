"""
Module for importing pycqed2 hdf5 files.
"""

import os
import h5py
from plottr.data.datadict import DataDict

def split_name_unit(val):
    """
    tool function for splitting data name from unit.
    Expects a string of format "name (unit)".
    Returns name, unit
    """
    if '(' not in val or ')' not in val:
        return val, ''
    
    unit = val[::-1][val[::-1].find(')')+1:val[::-1].find('(')][::-1]
    name = '('.join(val.split('(')[:-1]).strip()
    return name, unit

def load_pycqed_hdf5(path):
    """
    Loads the hdf5 file from path. path contains only the base, i.e.,
    if path = '/my/path/to/data/123456_Measurement', it'll try to open
    the file '/my/path/to/data/123456_Measurement/123456_Measurement.hdf5'.
    
    Returns a dictionary with the data column name as keys, and the column
    data as values.
    """
    fn = os.path.split(path)[-1] + '.hdf5'
    with h5py.File(os.path.join(path, fn), 'r') as f:
        data = f['Experimental Data']['Data'][:]
        cols = [ str(c.decode('utf-8')) for c in f['Experimental Data']['Data'].attrs['column_names'] ]
        
    ret = {}
    for i, c in enumerate(cols):
        ret[c] = data[:, i]
    
    print("Loaded data with {} points. Columns:".format(data.shape[0]))
    for c in cols:
        print("\t* {}".format(c))
    return ret

def pycqed_to_datadict(data, axes, grid=True):
    """
    Converts output from load_pycqed_hdf5 to DataDict.
    axes need to be given (without units part) to determine
    dependent/independent parameters.
    
    Returns DataDict if grid is False, GridDataDict otherwise.
    """
    cols = [c for c in data.keys()]
    ret = DataDict()
    for c in cols:
        name, unit = split_name_unit(c)
        ret[name] = dict(values=data[c], unit=unit)
        if name not in axes:
            ret[name]['axes'] = axes
    
    ret.validate()
    if grid:
        ret = ret.get_grid()
        
    return ret
