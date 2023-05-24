from typing import Tuple
import numpy as np


from plottr.apps.autoplot import autoplot
from plottr.plot.pyqtgraph.autoplot import AutoPlot
from plottr.data.datadict import DataDict, MeshgridDataDict


def oscillating_test_data(*specs: Tuple[float, float, int], amp=1, of=0):
    axes = np.meshgrid(*[np.arange(n) for _, _, n in specs], indexing='ij')
    data = amp * np.prod(np.array([np.cos(2*np.pi*(f*x+p)) 
                                   for x, (f, p, _) in zip(axes, specs)]), axis=0) \
           + np.random.normal(loc=0, scale=1, size=(axes[0].shape)) + of
    dd = MeshgridDataDict()
    for i, a in enumerate(axes):
        dd[f'axis_{i}'] = dict(values=a)
    dd['data'] = dict(
        axes=[f'axis_{i}' for i in range(len(specs))],
        values=data
    )
    dd.validate()
    return dd


data = oscillating_test_data(
    (0, 0, 10000),
    (1/10, 0, 51),
    (1/20, 0.25, 41),
    amp=5,
)

data2 = data.slice(axis_0=0)

