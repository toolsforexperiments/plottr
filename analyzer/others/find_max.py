import numpy as np

from ..base import Analysis, AnalysisResult

class FindMax(Analysis):
    """A simple example class to illustrate the concept."""

    def analyze(self, xvals, yvals):
        i = np.argmax(yvals)

        return AnalysisResult(
            dict(
                max_val=yvals[i],
                max_pos=xvals[i]
            )
        )
