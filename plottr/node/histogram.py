from .node import Node, NodeWidget, updateOption


class Histogrammer(Node):
    """A node that replaces the data with a histogram of the data.

    User can select the number of bins that we will use for the histogram.
    Histrogramming will make the dependent dimension that is histogrammed
    an independent, and the new dependent is occurrence.

    If the data is on a grid, then some or all of the previous independents may
    be kept, all others or removed. If the data is not on a grid, all other
    independents are removed.
    """

    useUi = False

    def __init__(self, name: str) -> None:
        super().__init__(name)

        self._nbins: int = 21


    @property
    def nbins(self) -> int:
        return self._nbins

    @nbins.setter
    @updateOption('nbins')
    def nbins(self, value: int) -> None:
        self._nbins = value

