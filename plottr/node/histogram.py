"""A node for histogramming data.

This module contains the following classes:

* :class:`.Histogrammer` -- a node that converts data into a histogram of the
  data. User can select over which data axis to perform the histogramming, as
  well as how many bins to use.
* :class:`.HistogrammerWidget` -- node widget that allows GUI specification
  of the user options for the node.
"""

from typing import Union, Optional, Dict, List, Type

import numpy as np
from xhistogram.core import histogram

from plottr import QtWidgets
from ..gui.widgets import FormLayoutWrapper, DimensionCombo
from ..data.datadict import DataDictBase, MeshgridDataDict
from .node import Node, NodeWidget, updateOption


class _HistogramOptionsWidget(FormLayoutWrapper):
    """Form widget providing a combo box for histogramming axis selection and an
    integer spin box for number of bins."""
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(
            parent=parent,
            elements=[('Hist. axis', DimensionCombo(dimensionType='axes')),
                      ('# of bins', QtWidgets.QSpinBox())],
        )
        self.combo = self.elements['Hist. axis']
        self.nbins = self.elements['# of bins']
        self.nbins.setRange(3, 10000)


class HistogrammerWidget(NodeWidget):
    """Node widget for the :class:`.Histogrammer` node."""

    def __init__(self, node: "Histogrammer"):
        super().__init__(embedWidgetClass=_HistogramOptionsWidget, node=node)

        self.widget: _HistogramOptionsWidget
        assert self.widget is not None
        self.widget.combo.connectNode(self.node)

        self.widget.nbins.setValue(node.nbins)
        self.setAxis(node.histogramAxis)

        self.optSetters = {
            'histogramAxis': self.setAxis,
            'nbins': self.widget.nbins.setValue,
        }
        self.optGetters = {
            'histogramAxis': self.getAxis,
            'nbins': self.widget.nbins.value,
        }

        self.widget.combo.dimensionSelected.connect(
            lambda x: self.signalOption('histogramAxis'))
        self.widget.nbins.editingFinished.connect(
            lambda: self.signalOption('nbins'))


    def getAxis(self) -> Optional[str]:
        t = self.widget.combo.currentText()
        if t == 'None':
            t = None
        return t

    def setAxis(self, value: Optional[str]) -> None:
        if value is None:
            value = 'None'
        self.widget.combo.setCurrentText(value)


class Histogrammer(Node):
    """A node that replaces the data with a histogram of the data.

    User can select the number of bins that we will use for the histogram, as
    well as the histogramming axes.
    Histrogramming will make the dependent dimension an independent, and the
    new dependent is occurrence. If the dependent data is complex, histogramming
    adds two new independents, one for the real and one for the imaginary
    part.

    Properties are:

    :nbins: ``int``
        number of bins.
    :histogramAxis: ``str``
        name of the axis over which to perform the histogramming.
    """

    useUi = True
    uiClass: Type["NodeWidget"] = HistogrammerWidget

    def __init__(self, name: str) -> None:
        self._nbins: int = 51
        self._histogramAxis: Optional[str] = None

        super().__init__(name)

    @property
    def nbins(self) -> int:
        return self._nbins

    @nbins.setter  # type: ignore[misc]
    @updateOption('nbins')
    def nbins(self, value: int) -> None:
        self._nbins = value

    @property
    def histogramAxis(self) -> Optional[str]:
        return self._histogramAxis

    @histogramAxis.setter  # type: ignore[misc]
    @updateOption('histogramAxis')
    def histogramAxis(self, value: Optional[str]) -> None:
        self._histogramAxis = value

    def validateOptions(self, data: DataDictBase) -> bool:
        if not super().validateOptions(data):
            return False
        if self.histogramAxis is None:
            return True
        elif self.histogramAxis not in data.axes():
            self.logger().error(f"'{self.histogramAxis}' is not a valid axis.")
            return False
        return True

    def process(self, dataIn: Optional[DataDictBase]=None) \
            -> Optional[Dict[str, Optional[DataDictBase]]]:
        data = super().process(dataIn=dataIn)
        if data is None:
            return None
        data = data['dataOut']
        assert data is not None
        data = data.mask_invalid()

        if self.histogramAxis is None:
            return dict(dataOut=data)

        newData = MeshgridDataDict()
        if isinstance(data, MeshgridDataDict):
            dataIsOnGrid = True
        else:
            dataIsOnGrid = False

        hAxisIdx: Optional[int] = None
        for depName in data.dependents():
            if dataIsOnGrid:
                axes = data.axes(depName)
                hAxisIdx = axes.index(self.histogramAxis)
                del axes[hAxisIdx]
            else:
                axes = []

            dvals = data.data_vals(depName)
            bins: Union[np.ndarray, List[np.ndarray]]
            if not np.iscomplexobj(dvals):
                d = [dvals]
                dataIsComplex = False
                bins = np.linspace(dvals.min(), dvals.max(), self.nbins+1)
            else:
                d = [dvals.imag, dvals.real]
                dataIsComplex = True
                bins = [
                    np.linspace(dvals.imag.min(), dvals.imag.max(), self.nbins+1),
                    np.linspace(dvals.real.min(), dvals.real.max(), self.nbins+1),
                ]
            hist, edges = histogram(*d, axis=hAxisIdx, bins=bins)

            newDepName = depName+'_count'
            if dataIsComplex:
                newAxNames = [f'Im[{depName}]', f'Re[{depName}]']
                newAxUnits = 2*[data[depName]['unit']]
                realAxVals = np.outer(np.ones_like(edges[0][:-1]),
                                      edges[1][:-1] + (edges[1][1:] - edges[1][:-1])).flatten()
                imagAxVals = np.outer(edges[0][:-1] + (edges[0][1:] - edges[0][:-1]),
                                      np.ones_like(edges[1][:-1])).flatten()
                axVals = [imagAxVals, realAxVals]
            else:
                newAxNames = [depName]
                newAxUnits = [data[depName]['unit']]
                axVals = [edges[0][:-1] + (edges[0][1:] - edges[0][:-1])]

            newData[newDepName] = dict(
                values=hist,
                axes=axes+newAxNames
            )

            # expand onto grid and add to dataset
            for an, au, av in zip(newAxNames, newAxUnits, axVals):
                newData[an] = dict(
                    values=np.outer(
                        np.ones(int(hist.size//av.size)),
                        av
                    ).reshape(*hist.shape),
                    unit=au,
                )

            for ax in axes:
                if ax in newData:
                    continue
                # fill up to match the added histogram dimensions
                oldAxData = data.data_vals(ax).mean(axis=hAxisIdx)
                axData = np.outer(
                    oldAxData, np.ones(hist.size//oldAxData.size)
                ).reshape(*hist.shape)
                newData[ax] = data[ax]
                newData[ax]['values'] = axData

        if newData.validate():
            return dict(dataOut=newData)

        return None

