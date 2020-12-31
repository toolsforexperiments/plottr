from typing import Tuple, Any, Optional, Union, Dict, List

import numpy as np
import lmfit

from ..base import Analysis, AnalysisResult


class Fit(Analysis):

    @staticmethod
    def model(*arg, **kwarg) -> np.ndarray:
        raise NotImplementedError

    def analyze(self, coordinates, data, dry=False, params={}, **fit_kwargs):
        model = lmfit.model.Model(self.model)

        _params = lmfit.Parameters()
        for pn, pv in self.guess(coordinates, data).items():
            _params.add(pn, value=pv)
        for pn, pv in params.items():
            _params[pn] = pv

        if dry:
            lmfit_result = lmfit.model.ModelResult(model, params=_params,
                                                   data=data,
                                                   coordinates=coordinates)
        else:
            lmfit_result = model.fit(data, params=_params,
                                     coordinates=coordinates, **fit_kwargs)

        return FitResult(lmfit_result)

    @staticmethod
    def guess(coordinates, data) -> Dict[str, Any]:
        raise NotImplementedError


class FitResult(AnalysisResult):

    def __init__(self, lmfit_result: lmfit.model.ModelResult):
        self.lmfit_result = lmfit_result
        self.params = lmfit_result.params

    def eval(self, *args: Any, **kwargs: Any):
        return self.lmfit_result.eval(*args, **kwargs)