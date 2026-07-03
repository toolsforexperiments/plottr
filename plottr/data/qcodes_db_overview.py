"""
plottr.data.qcodes_db_overview — Fast database overview queries.

This module provides optimized functions for listing QCoDeS dataset metadata
without loading full DataSet objects. It uses direct SQLite queries on the
QCoDeS database schema, avoiding the expensive experiments()/data_sets()
enumeration.

The implementation has been contributed to QCoDeS: when a QCoDeS version that
exposes ``qcodes.dataset.get_db_overview`` is installed, that implementation is
used. For older QCoDeS versions the equivalent local implementation below is
used as a fallback. The queries rely on the stable QCoDeS database schema
(runs + experiments tables) which has not changed across many QCoDeS versions.
"""
import datetime
import json
import logging
from contextlib import closing, nullcontext
from typing import Dict, Optional, Sequence, Tuple

from typing_extensions import TypedDict

from qcodes.dataset.sqlite.database import conn_from_dbpath_or_conn
from qcodes.dataset.sqlite.query_helpers import is_column_in_table

logger = logging.getLogger(__name__)


class RunOverviewDict(TypedDict):
    """Lightweight run overview — no snapshot, no data, no full DataSet.

    Extra ad-hoc metadata columns requested via the ``extra_columns`` argument
    of :func:`get_db_overview` are added under their column name in addition to
    the keys documented here (e.g. ``inspectr_tag``).
    """
    run_id: int
    experiment: str
    sample: str
    name: str
    started_date: str
    started_time: str
    completed_date: str
    completed_time: str
    records: int
    guid: str


def _format_timestamp(ts: Optional[float]) -> Tuple[str, str]:
    """Convert a unix timestamp float to (date, time) strings in local time."""
    if ts is None or ts == 0:
        return '', ''
    try:
        dt = datetime.datetime.fromtimestamp(ts)
    except (OSError, ValueError, OverflowError):
        return '', ''
    return dt.strftime('%Y-%m-%d'), dt.strftime('%H:%M:%S')


def _records_from_run_description(run_description_json: Optional[str]) -> int:
    """Extract record count from run_description shapes field.

    QCoDeS run_description may contain a ``shapes`` dict mapping dependent
    parameter names to their shape tuples.  The total data-point count is the
    product of shape dimensions summed across all parameter trees.
    """
    if not run_description_json:
        return 0
    try:
        desc = json.loads(run_description_json)
    except (json.JSONDecodeError, TypeError):
        return 0
    shapes = desc.get('shapes') if isinstance(desc, dict) else None
    if not shapes:
        return 0
    total = 0
    for shape in shapes.values():
        if isinstance(shape, (list, tuple)) and len(shape) > 0:
            n = 1
            for dim in shape:
                n *= dim
            total += n
    return total


def get_db_overview(path_to_db: Optional[str] = None,
                    conn: Optional[object] = None,
                    start_run_id: int = 0,
                    extra_columns: Optional[Sequence[str]] = None,
                    ) -> Dict[int, RunOverviewDict]:
    """Get a lightweight overview of all runs in a QCoDeS database.

    Uses a single SQL JOIN query to fetch run metadata from the ``runs`` and
    ``experiments`` tables, avoiding the expensive ``experiments()`` +
    ``data_sets()`` enumeration that QCoDeS uses internally.

    For a database with 1500 runs, this completes in ~10ms vs 15+ minutes
    with the standard QCoDeS API.

    :param path_to_db: path to the .db file. Opened read-only if given.
    :param conn: an existing connection to use instead of ``path_to_db``. It is
        left open by this function.
    :param start_run_id: only return runs with run_id > start_run_id.
        Use 0 to get all runs. Pass the last known run_id for incremental
        refresh.
    :param extra_columns: names of additional ``runs``-table columns to include
        in each overview dict (e.g. ad-hoc metadata columns such as
        ``inspectr_tag``). Columns not present in the ``runs`` table are
        silently skipped.
    :returns: dict mapping run_id to RunOverviewDict.
    """
    overview: Dict[int, RunOverviewDict] = {}

    created_conn = conn is None
    connection = conn_from_dbpath_or_conn(
        conn=conn, path_to_db=path_to_db, read_only=True  # type: ignore[arg-type]
    )
    manager = closing(connection) if created_conn else nullcontext(connection)

    with manager as c:
        valid_extra_columns = [
            col for col in (extra_columns or [])
            if is_column_in_table(c, 'runs', col)
        ]
        extra_select = ''.join(f", r.{col}" for col in valid_extra_columns)

        # Includes run_description to extract shape info for record count.
        # Deliberately excludes snapshot (large blob).
        query = f"""
            SELECT r.run_id, e.name, e.sample_name, r.name,
                   r.run_timestamp, r.completed_timestamp,
                   r.result_counter, r.guid, r.result_table_name,
                   r.run_description{extra_select}
            FROM runs r
            JOIN experiments e ON r.exp_id = e.exp_id
            WHERE r.run_id > ?
            ORDER BY r.run_id
        """

        try:
            rows = c.execute(query, (start_run_id,)).fetchall()
        except Exception as e:
            logger.warning(f"Could not query database overview: {e}")
            return overview

        # result_counter in the runs table counts INSERT calls, not data points.
        # For array paramtype one INSERT can contain thousands of data points,
        # so query the real row count of each results table separately.
        result_tables = {row[8] for row in rows if row[8]}
        row_counts: Dict[str, int] = {}
        for table in result_tables:
            try:
                count = c.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
            except Exception:
                continue  # results table may not exist yet
            row_counts[table] = count[0] if count else 0

        n_fixed = 10  # number of columns selected before extra_columns
        for row in rows:
            run_id = row[0]
            started_date, started_time = _format_timestamp(row[4])
            completed_date, completed_time = _format_timestamp(row[5])
            result_table = row[8] or ''
            is_completed = row[5] is not None and row[5] != 0

            # For completed datasets: prefer shape metadata (authoritative
            # final count) over results table rows. For active datasets: prefer
            # results table rows (live count that grows as data is added).
            # Fall back to result_counter if nothing else is available.
            if is_completed:
                records = _records_from_run_description(row[9])
                if records == 0:
                    records = row_counts.get(result_table, 0)
            else:
                records = row_counts.get(result_table, 0)
                if records == 0:
                    records = _records_from_run_description(row[9])
            if records == 0:
                records = row[6] or 0

            entry: RunOverviewDict = {
                'run_id': run_id,
                'experiment': row[1] or '',
                'sample': row[2] or '',
                'name': row[3] or '',
                'started_date': started_date,
                'started_time': started_time,
                'completed_date': completed_date,
                'completed_time': completed_time,
                'records': records,
                'guid': row[7] or '',
            }
            if valid_extra_columns:
                extra = {col: row[n_fixed + i]
                         for i, col in enumerate(valid_extra_columns)}
                entry.update(extra)  # type: ignore[typeddict-item]

            overview[run_id] = entry

    return overview


try:
    # Prefer the upstream QCoDeS implementation when it is available; it is
    # exported on ``qcodes.dataset`` from the QCoDeS version that upstreamed
    # this function. Fall back to the local implementation above otherwise.
    from qcodes.dataset import get_db_overview  # type: ignore[no-redef]  # noqa: F811
except ImportError:
    pass
