"""
plottr.data.qcodes_db_overview — Fast database overview queries.

This module exposes :func:`get_db_overview` (and :class:`RunOverviewDict`),
which provide a fast, lightweight listing of the runs in a QCoDeS database
without loading full ``DataSet`` objects.

The implementation has been contributed to QCoDeS. When a QCoDeS version that
exposes ``qcodes.dataset.get_db_overview`` is installed, that implementation is
used; otherwise the vendored copy in :mod:`plottr.data._qcodes_db_overview`
(an exact copy of the upstream implementation) is used as a fallback.
"""

try:
    from qcodes.dataset import RunOverviewDict, get_db_overview
except ImportError:
    from ._qcodes_db_overview import RunOverviewDict, get_db_overview

__all__ = ["RunOverviewDict", "get_db_overview"]
