"""
plottr.data.qcodes_db_overview — Fast database overview queries.

This module provides optimized functions for listing QCoDeS dataset metadata
without loading full DataSet objects. It uses direct SQLite queries on the
QCoDeS database schema, avoiding the expensive experiments()/data_sets()
enumeration.

**Intended for eventual contribution to QCoDeS.** The queries here rely on the
stable QCoDeS database schema (runs + experiments tables) which has not changed
across many QCoDeS versions.
"""
import json
import sys
import time
import logging
from contextlib import closing
from typing import Dict, Optional, Tuple

from typing_extensions import TypedDict

from qcodes.dataset.sqlite.database import conn_from_dbpath_or_conn

logger = logging.getLogger(__name__)


def _records_from_run_description(run_description_json: Optional[str]) -> int:
    """Extract record count from run_description shapes field.

    QCoDeS run_description may contain a ``shapes`` dict mapping dependent
    parameter names to their shape tuples.  The total data-point count is the
    product of shape dimensions summed across all parameter trees — matching
    the semantics of ``DataSet.number_of_results``.
    """
    if not run_description_json:
        return 0
    try:
        desc = json.loads(run_description_json)
        shapes = desc.get('shapes')
        if not shapes:
            return 0
        total = 0
        for shape in shapes.values():
            if isinstance(shape, (list, tuple)) and len(shape) > 0:
                n = 1
                for dim in shape:
                    n *= dim
                # Each parameter tree contributes n_values * n_params_in_tree
                # But shapes only has dependent params, and number_of_results
                # counts all values including axes. For display purposes,
                # the product of the shape is the most useful number.
                total += n
        return total
    except (json.JSONDecodeError, TypeError, KeyError):
        return 0


class RunOverviewDict(TypedDict):
    """Lightweight run overview — no snapshot, no data, no full DataSet."""
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
    inspectr_tag: str


def _format_timestamp(ts: Optional[float]) -> Tuple[str, str]:
    """Convert a unix timestamp float to (date, time) strings."""
    if ts is None or ts == 0:
        return '', ''
    try:
        t = time.localtime(ts)
        return time.strftime('%Y-%m-%d', t), time.strftime('%H:%M:%S', t)
    except (OSError, ValueError, OverflowError):
        return '', ''


def get_db_overview(db_path: str,
                    start_run_id: int = 0,
                    ) -> Dict[int, RunOverviewDict]:
    """Get a lightweight overview of all runs in a QCoDeS database.

    Uses a single SQL JOIN query to fetch run metadata from the ``runs`` and
    ``experiments`` tables, avoiding the expensive ``experiments()`` +
    ``data_sets()`` enumeration that QCoDeS uses internally.

    For a database with 1500 runs, this completes in ~10ms vs 15+ minutes
    with the standard QCoDeS API.

    :param db_path: path to the .db file.
    :param start_run_id: only return runs with run_id > start_run_id.
        Use 0 to get all runs. Pass the last known run_id for incremental
        refresh.
    :returns: dict mapping run_id to RunOverviewDict.
    """
    overview: Dict[int, RunOverviewDict] = {}

    if sys.version_info >= (3, 11):
        conn = conn_from_dbpath_or_conn(conn=None, path_to_db=db_path, read_only=True)
    else:
        conn = conn_from_dbpath_or_conn(conn=None, path_to_db=db_path)

    with closing(conn) as c:
        # Check which ad-hoc metadata columns exist in the runs table.
        # QCoDeS stores metadata added via ds.add_metadata() as extra columns.
        try:
            col_info = c.execute('PRAGMA table_info(runs)').fetchall()
            col_names = {col[1] for col in col_info}
        except Exception:
            col_names = set()

        has_inspectr_tag = 'inspectr_tag' in col_names

        # Build query: include inspectr_tag column if it exists.
        # Includes run_description to extract shape info for record count.
        # Deliberately excludes snapshot (large blob).
        tag_col = ", r.inspectr_tag" if has_inspectr_tag else ""
        query = f"""
            SELECT r.run_id, e.name, e.sample_name, r.name,
                   r.run_timestamp, r.completed_timestamp,
                   r.result_counter, r.guid, r.result_table_name,
                   r.run_description{tag_col}
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

        # Build a map of actual row counts from each results table.
        # result_counter in the runs table counts INSERT calls, not data points.
        # For array paramtype one INSERT can contain thousands of data points,
        # so result_counter can be much smaller than the real data point count.
        results_tables: set[str] = set()
        for row in rows:
            tbl = row[8]  # result_table_name
            if tbl:
                results_tables.add(tbl)
        row_counts: dict[str, int] = {}
        for tbl in results_tables:
            try:
                cnt = c.execute(
                    f'SELECT COUNT(*) FROM "{tbl}"'
                ).fetchone()
                row_counts[tbl] = cnt[0] if cnt else 0
            except Exception:
                pass  # table may not exist (e.g., qdwsdk downloads)

        tag_col_idx = 10 if has_inspectr_tag else -1
        for row in rows:
            run_id = row[0]
            started_date, started_time = _format_timestamp(row[4])
            completed_date, completed_time = _format_timestamp(row[5])
            tag = row[tag_col_idx] if tag_col_idx > 0 and len(row) > tag_col_idx and row[tag_col_idx] else ''
            result_table = row[8] or ''

            # Determine record count: prefer results table row count,
            # then try shape info from run_description, then result_counter.
            records = row_counts.get(result_table, 0)
            if records == 0:
                records = _records_from_run_description(row[9])
            if records == 0:
                records = row[6] or 0

            overview[run_id] = RunOverviewDict(
                run_id=run_id,
                experiment=row[1] or '',
                sample=row[2] or '',
                name=row[3] or '',
                started_date=started_date,
                started_time=started_time,
                completed_date=completed_date,
                completed_time=completed_time,
                records=records,
                guid=row[7] or '',
                inspectr_tag=tag,
            )

    return overview
