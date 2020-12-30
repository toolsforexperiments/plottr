from typing import Tuple, Any, Optional, Union, Dict, List

import numpy as np
import lmfit
from plottr.analyzer.fitters.fitter_base  import Fit, FitResult


class T1_Decay(Fit):
    @staticmethod
    def model(coordinates, amp, tau):
        """ amp * exp(-1.0 * x / tau)"""
        return amp * np.exp(-1.0 * coordinates / tau)
    @staticmethod
    def guess(self, coordinates, data):
        return dict(amp=1, tau=2)


class T2_Ramsey(Fit):
    @staticmethod
    def model(coordinates, amp, tau, freq, phase):
        """ amp * exp(-1.0 * x / tau) * sin(2 * PI * freq * x + phase) """
        return amp * np.exp(-1.0 * coordinates / tau) * \
               np.sin(2 * np.pi * freq * coordinates + phase)
    @staticmethod
    def guess(self, coordinates, data):
        return dict(amp=1, tau=2, freq=3, phase=4)