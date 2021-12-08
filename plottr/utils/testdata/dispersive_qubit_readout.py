"""This modules helps generate fake data that resembles dispersive qubit readout in
circuit QED.

If you don't know what dispersive readout is, it might be helpful to review
the basics of it before using this module. See, for example:
https://arxiv.org/pdf/2005.12667.pdf (Fig 18 is a good illustration).

:func:`.angle_data` generates noisy complex fake readout data. Specifying
the qubit rotation angle will result in an appropriately weighted distribution
of |0> and |1> results. For each 0 or 1 result the output is a complex data point
sampled from a normal distribution, where the means for 0 and 1 results depend
on the readout settings.

Readout settings can be changed through module-level variables:

* :data:`.angle` is the rotation angle in the complex plane between the means
    of the ground- and excited state distributions.
* :data:`.amp` is the displacement amplitude for the readout signal.
* :data:`.noise` is the standard deviation for the noise of the complex signal.

"""

from typing import Union
import numpy as np


angle = np.pi/2
amp = 2.
noise = 0.5


def gs_probability(theta: Union[np.ndarray, float]) -> Union[np.ndarray, float]:
    """Compute ground state probability for given rotation angle."""
    return np.cos(theta/2.)**2.


def state_data(state: np.ndarray) -> np.ndarray:
    """Readout data for a set of states.

    :param state: array of states (0 or 1, typically).
    :returns: array of complex readout results."""
    mean = amp * np.exp(1j * state * angle)
    return np.random.normal(loc=mean.real, scale=noise, size=state.shape) + \
        1j * np.random.normal(loc=mean.imag, scale=noise, size=state.shape)


def angle_data(theta: float, n: int = 100) -> np.ndarray:
    """Readout data for given qubit rotation angle.

    :param theta: rotation angle (in rad)
    :param n: number of samples
    :returns: complex readout data for each sample
    """
    rng = np.random.default_rng()
    state = rng.choice(
        np.array([0, 1]),
        size=n,
        p=np.array([gs_probability(theta), 1-gs_probability(theta)]),
    )
    return state_data(state)


if __name__ == '__main__':
    from matplotlib import pyplot as plt

    data = angle_data(np.pi/2., n=1000)
    extent = np.abs(data).max()
    hist, xe, ye = np.histogram2d(data.real, data.imag,
                                  bins=np.linspace(-extent, extent, 51))
    fig, ax = plt.subplots(1, 1)
    im = ax.pcolormesh(xe, ye, hist.T)
    cb = fig.colorbar(im)
    plt.show()
