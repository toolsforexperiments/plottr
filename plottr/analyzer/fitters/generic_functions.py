from typing import Tuple, Any, Optional, Union, Dict, List

import numpy as np
import lmfit

from plottr.analyzer.fitters.fitter_base import Fit, FitResult


class Cosine(Fit):
    @staticmethod
    def model(coordinates, A, f, phi, of) -> np.ndarray:
        """$A \cos(2 \pi f x + \phi) + of$"""
        return A * np.cos(2 * np.pi * coordinates * f + phi) + of

    @staticmethod
    def guess(coordinates, data):
        of = np.mean(data)
        A = (np.max(data) - np.min(data)) / 2.

        fft_val = np.fft.rfft(data)[1:]
        fft_frq = np.fft.rfftfreq(data.size,
                                  np.mean(coordinates[1:] - coordinates[:-1]))[1:]
        idx = np.argmax(np.abs(fft_val))
        f = fft_frq[idx]
        phi = np.angle(fft_val[idx])

        return dict(A=A, of=of, f=f, phi=phi)

class Exponential(Fit):
    @staticmethod
    def model(coordinates, a, b) -> np.ndarray:
        """ a * b ** x"""
        return a * b ** coordinates

    @staticmethod
    def guess(coordinates, data):
        return dict(a=1, b=2)
