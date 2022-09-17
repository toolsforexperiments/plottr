from typing import Tuple, Any, Optional, Union, Dict, List

import numpy as np
import lmfit

from plottr.analyzer.fitters.fitter_base import Fit, FitResult


class Cosine(Fit):
    @staticmethod
    def model(coordinates: np.ndarray,
              A: float, f: float, phi: float, of: float) -> np.ndarray:
        """$A \cos(2 \pi f x + \phi) + of$"""
        return A * np.cos(2 * np.pi * coordinates * f + phi) + of

    @staticmethod
    def guess(coordinates: Union[Tuple[np.ndarray, ...], np.ndarray],
                 data: np.ndarray) -> Dict[str, float]:
        of = np.mean(data)
        A = (np.max(data) - np.min(data)) / 2.

        # Making sure that coordinates is ndarray.
        # Changing the type in the signature will create a different mypy error.
        assert isinstance(coordinates, np.ndarray)
        fft_val = np.fft.rfft(data)[1:]
        fft_frq = np.fft.rfftfreq(data.size,
                                  np.mean(coordinates[1:] - coordinates[:-1]))[1:]
        idx = np.argmax(np.abs(fft_val))
        f = fft_frq[idx]
        phi = np.angle(fft_val[idx])

        return dict(A=A, of=of, f=f, phi=phi)


class Exponential(Fit):
    @staticmethod
    def model(coordinates: np.ndarray, a: float, b: float) -> np.ndarray:
        """ a * b ** x"""
        return a * b ** coordinates

    @staticmethod
    def guess(coordinates: Union[Tuple[np.ndarray, ...], np.ndarray],
                 data: np.ndarray) -> Dict[str, float]:
        return dict(a=1, b=2)
