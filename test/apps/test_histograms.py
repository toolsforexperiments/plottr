#%% magics to configure mainloop

from IPython import get_ipython
ipy = get_ipython()
ipy.magic("load_ext autoreload")
ipy.magic("autoreload 2")
ipy.magic("gui qt")
ipy.magic("matplotlib qt")


#%% importing stuff and defining methods
from typing import Tuple

import numpy as np
from matplotlib import pyplot as plt
from xhistogram.core import histogram

from plottr.data.datadict import datadict_to_meshgrid
from plottr.node.tools import linearFlowchart
from plottr import Flowchart, QtCore
from plottr.data import DataDict
from plottr.apps.autoplot import AutoPlotMainWindow
from plottr.node.data_selector import DataSelector
from plottr.node.grid import DataGridder
from plottr.node.dim_reducer import XYSelector
from plottr.node.histogram import Histogrammer
from plottr.plot import makeFlowchartWithPlot


def testdata(n_reps=100, n_extra_axes=1):
    reps = np.arange(n_reps)
    axes = ['sample'] + [f'ax_{i}' for i in range(n_extra_axes)]
    extra_axes_vals = [np.linspace(-1., 1., 10+i) for i in range(n_extra_axes)]
    axes_vals = [reps] + extra_axes_vals
    axes_vals_mesh = np.meshgrid(*axes_vals, indexing='ij')

    outcomes_mesh = np.random.normal(
        loc=0, scale=1, size=axes_vals_mesh[0].shape,
    )

    for axvals in axes_vals_mesh[1:]:
        outcomes_mesh = np.add(outcomes_mesh, axvals)

    dataset = DataDict(
        result=dict(values=outcomes_mesh.flatten(),
                    axes=axes),
    )
    for ax, axvals in zip(axes, axes_vals_mesh):
        dataset[ax] = dict(values=axvals.flatten())

    return dataset


def complex_testdata(n_samples=100, n_amps=21):
    samples = np.arange(n_samples)
    amps = np.arange(n_amps)
    ss, aa = np.meshgrid(samples, amps, indexing='ij')
    locs = aa * np.exp(-1j * 0.1 * np.pi)
    values_real = np.random.normal(loc=locs.real, scale=0.5, size=ss.shape)
    values_imag = np.random.normal(loc=locs.imag, scale=0.5, size=ss.shape)
    vv = values_real + 1j*values_imag

    dataset = DataDict(
        sample=dict(values=ss.flatten()),
        amp=dict(values=aa.flatten()),
        result=dict(values=vv.flatten(),
                    axes=['sample', 'amp'])
    )

    if dataset.validate():
        return dataset


def complex_testdata_many_independents(n_samples=100, n_amps=4, n_phases=8, n_widths=3):
    samples = np.arange(n_samples)
    amps = np.arange(n_amps)+1.
    phases = np.linspace(0, 2*np.pi*(1.-1./n_phases), n_phases)
    widths = (np.arange(n_widths)+1.)/5.

    ss, aa, pp, ww = np.meshgrid(samples, amps, phases, widths, indexing='ij')
    locs = aa * np.exp(-1j*pp)
    values_real = np.random.normal(loc=locs.real, scale=widths, size=ss.shape)
    values_imag = np.random.normal(loc=locs.imag, scale=widths, size=ss.shape)
    vv = values_real + 1j*values_imag

    dataset = DataDict(
        sample=dict(values=ss.flatten()),
        amp=dict(values=aa.flatten()),
        phase=dict(values=pp.flatten()),
        width=dict(values=ww.flatten()),
        result=dict(values=vv.flatten(),
                    axes=['sample', 'amp', 'phase', 'width'])
    )

    if dataset.validate():
        return dataset


def plot() -> Tuple[Flowchart, AutoPlotMainWindow]:

    nodes = [
        ('Data selection', DataSelector),
        ('Grid', DataGridder),
        ('Histogram', Histogrammer),
        ('Dimension assignment', XYSelector),
    ]
    fc = makeFlowchartWithPlot(nodes)

    widgetOptions = {
        "Data selection": dict(visible=True,
                               dockArea=QtCore.Qt.TopDockWidgetArea),
        "Dimension assignment": dict(visible=True,
                                     dockArea=QtCore.Qt.TopDockWidgetArea),
    }
    win = AutoPlotMainWindow(fc,
                             loaderName=None,
                             widgetOptions=widgetOptions,
                             monitor=False)
    win.show()
    return fc, win


#%% verify testdata
# dataset = testdata()
# dataset_gridded = datadict_to_meshgrid(dataset)
#
# fig = plt.figure(constrained_layout=True)
# ax = fig.add_subplot(1, 2, 1)
# ax.imshow(dataset_gridded.data_vals('output'), aspect='auto')
#
# h, e = histogram(dataset_gridded.data_vals('output'),
#                  axis=0, bins=10)
# ax = fig.add_subplot(1,2,2)
# ax.imshow(h, aspect='auto')

#%% testing the node stand-alone
# dataset = testdata()
# dataset_gridded = datadict_to_meshgrid(dataset)
#
# fc = linearFlowchart(('hist', Histogrammer))
# fc.setInput(dataIn=dataset_gridded)
#
# hnode: Histogrammer = fc.nodes()['hist']
# hnode.histogramAxis = 'repetition'
# hnode.nbins = 9
#
# dataset_out = fc.outputValues()['dataOut']
#
# fig = plt.figure(constrained_layout=True)
# ax = fig.add_subplot(1, 2, 1)
# ax.imshow(dataset_gridded.data_vals('output'), aspect='auto')
#
# ax = fig.add_subplot(1,2,2)
# ax.imshow(dataset_out.data_vals('output_count'), aspect='auto')


#%% launching an app and setting testdata
fc, win = plot()
win.show()

hnode: Histogrammer = fc.nodes()['Histogram']
dselnode: DataSelector = fc.nodes()['Data selection']
dimnode: XYSelector = fc.nodes()['Dimension assignment']

# dataset = testdata(n_extra_axes=2)
dataset = complex_testdata(n_samples=100, n_amps=21)

fc.setInput(dataIn=dataset)
dselnode.selectedData = ['result']
