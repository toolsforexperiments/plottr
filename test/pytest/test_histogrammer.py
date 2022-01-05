import numpy as np
from xhistogram.core import histogram

from plottr.utils.num import arrays_equal
from plottr.data.datadict import DataDict, datadict_to_meshgrid
from plottr.node.tools import linearFlowchart
from plottr.node.histogram import Histogrammer
from plottr.apps.autoplot import AutoPlotMainWindow


def _make_testdata(complex: bool = False):
    x = np.linspace(-1, 1, 101)
    y = np.arange(7)
    z = np.linspace(0, 100, 16)
    xx, yy, zz = np.meshgrid(x, y, z, indexing='ij')
    rr = np.random.normal(loc=0, scale=1, size=xx.shape)
    if complex:
        ii = np.random.normal(loc=0, scale=1, size=xx.shape)
        nn = rr + 1j * ii
    else:
        nn = rr

    return datadict_to_meshgrid(DataDict(
        x=dict(values=xx),
        y=dict(values=yy),
        z=dict(values=zz),
        noise=dict(values=nn, axes=['x', 'y', 'z']),
    ))


def test_real_histogram(qtbot):
    dataset = _make_testdata()
    assert dataset.validate()
    hist, edges = histogram(dataset.data_vals('noise'), axis=0, bins=10)

    Histogrammer.useUi = False
    fc = linearFlowchart(('h', Histogrammer))
    fc.setInput(dataIn=dataset)
    assert fc.outputValues()['dataOut'] == dataset

    fc.nodes()['h'].nbins = 10
    fc.nodes()['h'].histogramAxis = 'x'
    assert fc.outputValues()['dataOut'].dependents() == ['noise_count']
    assert fc.outputValues()['dataOut'].axes('noise_count') == \
        ['y', 'z', 'noise']
    assert arrays_equal(
        fc.outputValues()['dataOut']['noise_count']['values'],
        hist
    )

def test_imag_histogram(qtbot):
    dataset = _make_testdata(complex=True)
    assert dataset.validate()
    dvals = dataset.data_vals('noise')
    hist, edges = histogram(dvals.imag, dvals.real, axis=0, bins=10)

    Histogrammer.useUi = False
    fc = linearFlowchart(('h', Histogrammer))
    fc.setInput(dataIn=dataset)
    assert fc.outputValues()['dataOut'] == dataset

    fc.nodes()['h'].nbins = 10
    fc.nodes()['h'].histogramAxis = 'x'
    assert fc.outputValues()['dataOut'].dependents() == ['noise_count']
    assert fc.outputValues()['dataOut'].axes('noise_count') == \
           ['y', 'z', 'Im[noise]', 'Re[noise]']
    assert arrays_equal(
        fc.outputValues()['dataOut']['noise_count']['values'],
        hist
    )

def test_histogram_with_ui(qtbot):
    dataset = _make_testdata()
    assert dataset.validate()
    hist, edges = histogram(dataset.data_vals('noise'), axis=1, bins=15)

    Histogrammer.useUi = True
    fc = linearFlowchart(('h', Histogrammer))
    win = AutoPlotMainWindow(fc,
                             loaderName=None,
                             monitor=False)
    win.show()
    qtbot.addWidget(win)

    fc.setInput(dataIn=dataset)
    hnode = fc.nodes()['h']

    # emit signal manually right now, since that's what's connected.
    # setting value alone won't emit the change.
    hnode.ui.widget.nbins.setValue(15)
    hnode.ui.widget.nbins.editingFinished.emit()

    hnode.ui.widget.combo.setCurrentText('y')

    assert fc.outputValues()['dataOut'].dependents() == ['noise_count']
    assert fc.outputValues()['dataOut'].axes('noise_count') == \
        ['x', 'z', 'noise']
    assert arrays_equal(
        fc.outputValues()['dataOut']['noise_count']['values'],
        hist
    )
