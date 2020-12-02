"""
data_selector.py

A node and widget for subselecting from a dataset.
"""
from typing import List, Tuple, Dict, Any, Sequence, Optional

import numpy as np

from .node import Node, NodeWidget, updateOption
from ..data.datadict import DataDictBase, DataDict
from ..gui.data_display import DataSelectionWidget
from plottr.icons import get_dataColumnsIcon
from ..utils import num

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


class DataDisplayWidget(NodeWidget):
    """
    Simple Tree widget to show data and their dependencies in the node data.
    """

    def __init__(self, node: Optional[Node] = None):
        self.icon = get_dataColumnsIcon()
        super().__init__(embedWidgetClass=DataSelectionWidget)
        assert self.widget is not None
        self.optSetters = {
            'selectedData': self.setSelected,
        }
        self.optGetters = {
            'selectedData': self.getSelected,
        }

        self.widget.dataSelectionMade.connect(
            lambda x: self.signalOption('selectedData'))

    def setSelected(self, vals: Sequence[str]) -> None:
        assert self.widget is not None
        self.widget.setSelectedData(vals)
        self._updateOptions(vals)

    def getSelected(self) -> List[str]:
        assert self.widget is not None
        return self.widget.getSelectedData()

    def setData(self, structure: DataDictBase,
                shapes: Dict[str, Tuple[int, ...]], _: Any) -> None:
        assert self.widget is not None
        self.widget.setData(structure, shapes)

    def setShape(self, shapes: Dict[str, Tuple[int, ...]]) -> None:
        assert self.widget is not None
        self.widget.setShape(shapes)

    def _updateOptions(self, selected: Sequence[str]) -> None:
        assert self.widget is not None
        ds = self.widget._dataStructure
        for n, w in self.widget.dataItems.items():
            if selected != [] and ds[n]['axes'] != ds[selected[0]]['axes']:
                self.widget.setItemEnabled(n, False)
            else:
                self.widget.setItemEnabled(n, True)


class DataSelector(Node):
    """
    This node allows extracting data from datasets. The fields specified by
    ``selectedData`` and their axes are kept, the rest is discarded.
    All selected data fields must be compatible in the sense that they have the
    same axes (also in the same order).
    The utility of this node is that afterwards data can safely be processed
    together, as the structure of all remaining fields is shared.

    Properties of this node:
    :selectedData: list of strings with compatible dependents.
    """

    # TODO: allow the user to control dtypes.

    nodeName = "DataSelector"
    uiClass = DataDisplayWidget

    force_numerical_data = True

    def __init__(self, name: str):
        super().__init__(name)

        self._dataStructure = None
        self.selectedData = []  # type: ignore[misc]

    # Properties

    @property
    def selectedData(self) -> List[str]:
        return self._selectedData

    @selectedData.setter  # type: ignore[misc]
    @updateOption('selectedData')
    def selectedData(self, val: List[str]) -> None:
        if isinstance(val, str):
            val = [val]
        self._selectedData = val

    # Data processing

    def validateOptions(self, data: DataDictBase) -> bool:
        """
        Validations performed:
        * only compatible data fields can be selected.
        """
        if data is None:
            return True

        for elt in self.selectedData:
            if elt not in data:
                self.logger().warning(
                    f'Did not find selected data {elt} in data. '
                    f'Clearing the selection.'
                )
                self._selectedData = []

        if len(self.selectedData) > 0:
            allowed_axes = data.axes(self.selectedData[0])
            for d in self.selectedData:
                if data.axes(d) != allowed_axes:
                    self.logger().error(
                        f'Datasets {self.selectedData[0]} '
                        f'(with axes {allowed_axes}) '
                        f'and {d}(with axes {data.axes(d)}) are not compatible '
                        f'and cannot be selected simultaneously.'
                        )
                    return False
        return True

    def _reduceData(self, data: Optional[DataDictBase]) -> Optional[DataDictBase]:
        if data is None:
            return None
        if isinstance(self.selectedData, str):
            dnames = [self.selectedData]
        else:
            dnames = self.selectedData
        if len(self.selectedData) == 0:
            return None

        ret = data.extract(dnames)
        if self.force_numerical_data:
            for d, _ in ret.data_items():
                d_data_vals = ret.data_vals(d)
                dt = num.largest_numtype(d_data_vals,
                                         include_integers=False)
                if dt is not None:
                    ret[d]['values'] = ret[d]['values'].astype(dt)
                else:
                    return None

        return ret

    def process(self, dataIn: Optional[DataDictBase] = None) -> Optional[Dict[str, Any]]:
        data = super().process(dataIn=dataIn)
        if data is None:
            return None
        data = data['dataOut']

        # this is the actual operation of the node
        data = self._reduceData(data)
        if data is None:
            return None

        # it is possible at this stage that we have data in DataDictBase format
        # which we cannot process further down the line.
        # But after extraction of compatible date we can now convert.
        if isinstance(data, DataDictBase):
            data = DataDict(**data)
            if not data.validate():
                return None

        return dict(dataOut=data)

    # Methods for GUI interaction

    def setupUi(self) -> None:
        super().setupUi()
        assert self.ui is not None
        self.newDataStructure.connect(self.ui.setData)
        self.dataShapesChanged.connect(self.ui.setShape)

