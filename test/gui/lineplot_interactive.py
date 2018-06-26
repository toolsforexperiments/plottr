# -*- coding: utf-8 -*-
import numpy as np
from pprint import pprint
from plottr.data.datadict import DataDict
from lineplot import Node, DataDictSourceNode, DataSelector


def testdata1(nx, ny):
    x = np.linspace(0, 10, nx)
    y = np.linspace(-5, 5, ny)
    xx, yy = np.meshgrid(x, y, indexing='ij')
    zz = np.cos(xx) * np.sin(yy)
    zz2 = np.sin(xx) * np.cos(yy)
    d = DataDict(
        x = dict(values=xx.reshape(-1)),
        y = dict(values=yy.reshape(-1)),
        z = dict(values=zz.reshape(-1), axes=['x', 'y']),
        z2 = dict(values=zz2.reshape(-1), axes=['x', 'y']),
    )
    return d


data1 = testdata1(3, 5)

datasrc = DataDictSourceNode()
datasrc.setData(data1)

datasel = DataSelector()
datasel.setSource(datasrc)
datasel.dataName = 'z'
datasel.slices = dict(y=np.s_[0:1:])
