# Plottr Performance & UX Improvements

This document summarizes the changes in this PR, the profiling that motivated them,
and suggestions for future work.

---

## Part 1: Implemented — Pipeline Performance (datadict, nodes, gridding)

### Problem

Plottr's data pipeline copied data excessively as it flowed through nodes. Each node
defensively deep-copied all data, and internal methods (`structure()`, `validate()`,
`copy()`) added further redundant copies. For a 100x100x100 MeshgridDataDict (~38 MB),
a single `copy()` took 92 ms and `validate()` took 43 ms.

### What Changed

**`plottr/data/datadict.py`** (core data container):
- New `_copy_field()` helper with per-key copy semantics: numpy `.copy()` for arrays,
  `list()` for axes, `deepcopy` only for mutable metadata
- Rewrote `copy(deep=True/False)` — no longer chains through `structure()` → `validate()`
  → `deepcopy`. New `deep=False` shares arrays (xarray-style API, backward compatible)
- `_build_structure()` private helper that skips redundant validation
- `MeshgridDataDict.validate()` monotonicity check: replaced `np.unique(np.sign(np.diff(...)))`
  with direct min/max checks — same coverage, no sort/allocate
- `mask_invalid()` fast-path: skips masking entirely when data has no invalid entries
- `shapes()` uses `np.shape()` instead of `np.array(...).shape`
- `datasets_are_equal()` shape short-circuit + set-based comparison
- `remove_invalid_entries()` fixed O(n²) `np.append` pattern + fixed crash on inhomogeneous arrays
- `meshgrid_to_datadict()` / `datadict_to_dataframe()`: `ravel()` instead of `flatten()`

**`plottr/utils/num.py`** (numerical utilities):
- `largest_numtype()`: dtype check instead of iterating every element as Python object (~15,000× faster)
- `is_invalid()`: skip zero-array allocation for non-float types
- `guess_grid_from_sweep_direction()`: convert with `np.asarray()` once instead of 4×
- `_find_switches()`: compute `is_invalid()` once (was 3×), single `np.percentile([lo,hi])` call
  (was 2 separate sorts), vectorized boolean filter, `np.nanmean` for NaN-safe sweep direction

**`plottr/node/node.py`**: Defer `structure()` call to only when structure actually changes (50× faster steady-state)

**`plottr/node/dim_reducer.py`**: Removed redundant `copy()` in `XYSelector.process()`

**`plottr/node/grid.py`**: Pass `copy=False` to `datadict_to_meshgrid()` since gridder already copies input

**`plottr/plot/base.py`**: `dataclasses.replace` instead of `deepcopy` for complex plot splitting

### Bugs Fixed
- `copy()` now properly deep-copies global mutable metadata (was sharing references)
- `remove_invalid_entries()` no longer crashes when dependents have different numbers of invalid entries

### Benchmark Results

**Micro-benchmarks (key functions):**

| Function | Before | After | Speedup |
|---|---|---|---|
| `largest_numtype` (500K float) | 29.8 ms | 0.002 ms | ~15,000× |
| `mesh_500k_copy()` | 42.2 ms | 2.9 ms | 14.8× |
| `node_process` (500K mesh, steady state) | 7.4 ms | 0.15 ms | 50× |
| `_find_switches` (640K pts) | 80 ms | 31 ms | 2.6× |
| `datadict_to_meshgrid` (640K pts) | 175 ms | 71 ms | 2.5× |
| `mesh_500k_validate()` | 20.5 ms | 14.1 ms | 1.5× |

**Real experimental data (P1386BB_00BE_datasets.db, steady-state refresh):**

| Dataset | Data Size | Before | After | Speedup |
|---|---|---|---|---|
| QDstability (14400×251, 16 deps) | 223 MB | 555 ms | 189 ms | 2.93× |
| TopogapStage2 (41×33×5×81, 21 deps) | 152 MB | 439 ms | 161 ms | 2.73× |
| QDtuning (7440×121, 16 deps) | 14 MB | 31 ms | 11 ms | 2.73× |

**Interactive actions (simulated user operations on large datasets):**

| Action | Before | After | Speedup |
|---|---|---|---|
| Toggle subtract average (15 MB 2D) | 293 ms | 29 ms | 10.2× |
| Swap XY axes (18 MB 2D) | 790 ms | 241 ms | 3.3× |
| Switch dependent (61 MB 1D) | 2,287 ms | 977 ms | 2.3× |
| Data refresh (15 MB 2D) | 697 ms | 199 ms | 3.5× |

### Tests Added

221 new tests across 4 test files:
- `test_datadict_copy_semantics.py` — copy isolation, edge cases, pipeline integrity
- `test_pipeline_coverage.py` — per-node tests, hypothesis property-based, various dtypes
- `test_round2_optimizations.py` — is_invalid, largest_numtype, remove_invalid_entries
- `test_gridder_comprehensive.py` — all GridOption paths, shapes, edge cases

---

## Part 2: Implemented — Inspectr Loading & UX

### Problem

Opening a large QCoDeS database (1496 runs) in inspectr took 15+ minutes because the
`experiments()` + `data_sets()` enumeration in QCoDeS is O(N²). Clicking any dataset
froze the UI for ~1 second while the snapshot (up to 6 MB of JSON) was parsed into
thousands of tree widget items.

### What Changed

**Fast database overview** (`plottr/data/qcodes_db_overview.py`, new module):
- Single SQL JOIN query fetching run metadata directly from runs + experiments tables
- Skips snapshot and run_description blobs entirely
- Reads `inspectr_tag` directly as a column from the runs table
- Intended for eventual contribution to QCoDeS

**Lazy snapshot loading** (`plottr/apps/inspectr.py`):
- Snapshot tree built only when user expands the "QCoDeS Snapshot" section
- Info pane sections collapsed by default
- Smooth pixel-based scrolling for tall rows (e.g., exception tracebacks)

**Incremental refresh**:
- `refreshDB()` only loads runs newer than the last known run_id
- Merges incremental results into existing dataframe

**Loading UX**:
- Live progress indicator: "Loading database... (142/1496 datasets)"
- Contextual messages: "Select a date...", "No datasets found...", "No datasets match filter..."
- Wider default window (960×640)

**Fallback chain**: SQL direct → `load_by_id` loop → original `experiments()` API

### Benchmark

| Approach | 23 runs | 1496 runs (projected) |
|---|---|---|
| Old (experiments + data_sets) | 103 ms | 15+ minutes |
| load_by_id loop | 90 ms | ~5 seconds |
| **SQL direct** (new) | **14 ms** | **~10 ms** |
| Incremental (3 new runs) | - | **~4 ms** |

Snapshot click: 951 ms → 0.3 ms (3,554× faster)

---

## Part 3: Implemented — Plot UI Improvements

### What Changed

**Grid layout for pyqtgraph subplots** (`plottr/plot/pyqtgraph/autoplot.py`):
- Replaced single-column `QSplitter` with `QGridLayout` using near-square grid
  (same formula as matplotlib: `nrows = int(n^0.5 + 0.5)`)
- Many subplots now arrange as 2×2, 2×3, 4×4 etc. instead of stacking vertically

**Scrollable plot area** (both backends):
- "Scrollable" checkbox + min-height spinbox in the plot toolbar
- Off by default; when enabled, plot area expands and becomes scrollable
- Min height per row configurable (40–2000 px, default 75 px pyqtgraph / 100 px mpl)

**Plot backend selector** (`plottr/apps/inspectr.py`):
- Combo box in inspectr toolbar to switch between matplotlib and pyqtgraph
- Default: matplotlib. Applies to newly opened plot windows.

---

## Part 4: Not Implemented — Future Suggestions

These were identified during analysis but not implemented in this PR.

### HDF5 Data Loading (datadict_storage.py)
- Lines 274 and 305 read the **entire HDF5 dataset into memory** just to get its shape
- Fix: `ds.shape` instead of `ds[:].shape` — would reduce load time by 50–80%

### Signal Emission Overhead (node.py)
- Up to 7 Qt signals emitted per node per data update
- `dataFieldsChanged` is redundant (axes + deps)
- Could consolidate to 1–2 batched signals

### Fitter / Histogrammer / ScaleUnits Memoization
- These nodes recompute results on every update even when inputs haven't changed
- Could cache results keyed on data hash + parameters

### Pipeline Change Detection
- No concept of "what changed" — every update re-processes all data through all nodes
- For append-only monitoring, nodes could process only new data

### QCoDeS API Suggestion
The ideal API for inspectr would be a single function returning lightweight run metadata
for all or a range of runs without creating full DataSet objects:
```python
get_run_overview(conn, start_id=None, end_id=None)
# Returns: [{run_id, exp_name, sample_name, name, timestamps, guid, result_counter, metadata_keys}]
```
This would be a single SQL query completing in <1 ms for any database size.
