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

---

## Part 5: Profiling with Real Data (963×1001 complex RF measurement)

Profiled using dataset `d2712e0a-0c00-0012-0000-019dc443d6e4` (downloaded via `qdwsdk`):
a 963×1001 complex128 2D gate-gate sweep (Vrf_6 vs plunger and depletion gate voltages).
Device: L1033AA_00BE_Mv22v3, ~12.5 MB on disk, ~15 MB in memory as complex128.

### Timing Summary

| Operation | Time (ms) | Notes |
|---|---|---|
| `ds_to_datadict` (first call) | 2,588 | 1,500 ms is xarray/cf_xarray import (one-time) |
| `ds_to_datadict` (steady state) | 999 | qcodes SQLite → numpy deserialization |
| `datadict_to_meshgrid` | 122 | `guess_grid_from_sweep_direction` dominates |
| Pipeline steady state (sel+grid) | 51 | Per re-trigger with same data |
| Switch dependent variable | 172 | selector + gridding + pyqtgraph `eq()` |
| Complex: real only | 8.5 | `copy()` + `.real.copy()` |
| Complex: real+imag | 11.6 | `copy()` + `.real` + `.imag` |
| Complex: mag+phase | 30.8 | `copy()` + `np.abs()` + `np.angle()` |
| `copy()` deep | 5.1 | Already fast after our optimization |
| `copy()` shallow | 0.1 | Zero-copy array sharing |
| `validate()` | 0.2 | Already fast |
| `structure()` | 0.4 | Already fast |
| `is_invalid()` on 963k complex | 44.6 | **`a == None` comparison is 44× slower than `np.isnan`** |
| `np.isnan()` on 963k complex | 1.0 | What `is_invalid` should use for numeric dtypes |

### Bottleneck Analysis

#### 1. `is_invalid()` — 44× slower than needed (LOW-HANGING FRUIT)

The current implementation does `a == None` for all arrays, which triggers Python object
comparison on every element. For numeric arrays (float/complex), this is always `False`
and is pure waste. Replacing with `np.isnan()` directly for numeric dtypes would cut
`is_invalid` from 44.6 ms → ~1 ms.

This cascades through `_find_switches()` (which calls `is_invalid` on each 963k-element
axis), making `datadict_to_meshgrid` ~90 ms faster.

**Fix**: In `is_invalid()`, check dtype first — if it's a numeric type, skip the `== None`
check entirely and return just `np.isnan(a)`.

#### 2. `ds_to_datadict()` — 999 ms steady state (MEDIUM EFFORT)

The qcodes `DataSetCacheDeferred` loads data via xarray round-trip. The actual SQLite
read + numpy deserialization (`_convert_array` → `numpy.read_array` → `ast.literal_eval`
for headers) takes ~1 second for 963k × 3 parameters.

This is largely inside qcodes, so fixes would be upstream. However, plottr could:
- Cache the loaded DataDict and skip reload when the dataset hasn't changed
- Use `load_by_id(...).cache.data()` directly instead of going through `ds_to_datadict`
  which re-wraps the data
- For completed datasets (known from metadata), cache the DataDict permanently

#### 3. `datadict_to_meshgrid` with `guessShape` — 122 ms (AVOIDABLE)

When shape metadata exists in the QCodes `RunDescriber` (this dataset has
`shapes={'rf_wrapper_ch6_Vrf_6': (1001, 1001)}`), the gridder should use
`GridOption.metadataShape` and skip the expensive `guess_grid_from_sweep_direction`.

The autoplot code already does this (`autoplot.py:298`), but the grid widget default
is `noGrid`, so if the user starts from the widget rather than autoplot, they get
`guessShape` which runs the full sweep-direction analysis on every re-trigger.

**Fix**: Default the grid widget to `metadataShape` when shape metadata is available.

#### 4. `np.abs()` + `np.angle()` for complex mag+phase — 30.8 ms (INHERENT)

This is inherent computational cost for computing magnitude and phase of 963k complex128
values. Not much to optimize here, but could be deferred (only compute when the plot
backend actually needs to render).

#### 5. pyqtgraph `Terminal.setValue` → `eq()` — 12 ms per node (MEDIUM)

pyqtgraph's flowchart compares old and new terminal values using a recursive `eq()`
function. For large DataDicts this recurses into all arrays and does element-wise
comparison. This adds ~24 ms per pipeline trigger (12 ms per node, 2 nodes).

**Fix**: Override `eq()` on DataDictBase to do a cheap identity or shape check
instead of element-wise comparison, or set terminal values without comparison.

### Suggested Priority (remaining)

Items 1, 2, and 6 have been implemented. Remaining potential improvements:

1. ~~**Fix `is_invalid()`**~~ ✅ Done — 44x faster (44.6ms → 1.0ms)
2. ~~**Default to `metadataShape`**~~ ✅ Done — avoids 122ms gridding when shape metadata exists
3. **Cache loaded DataDict** for completed datasets — avoids 999 ms reload on each refresh
4. **Override pyqtgraph `eq()`** for DataDictBase — saves ~24 ms per pipeline trigger
5. **Lazy complex splitting** — compute mag/phase only when needed by the plot backend
6. ~~**Fix mpl double-replot**~~ ✅ Done — ~20% faster mpl steady-state (919ms → 754ms)
7. **Matplotlib artist-level updates** — Instead of `fig.clear()` + full recreation on every
   `setData()`, reuse existing Line2D/QuadMesh/colorbar artists and update their data.
   The pyqtgraph backend already does this via `clearWidget=False`; bringing the same
   pattern to mpl could reduce steady-state replot from ~750ms to ~200ms.

### Backend Comparison After Optimizations (963×1001 complex128)

| Operation | matplotlib | pyqtgraph |
|---|---|---|
| First plot | 1,428 ms | 175 ms |
| Steady replot | 754 ms | 80 ms |
| Complex real | 394 ms | 118 ms |
| Complex realAndImag | 687 ms | 114 ms |
| Complex magAndPhase | 730 ms | 108 ms |

The pyqtgraph backend is ~10x faster for steady-state replots because it reuses
plot widget objects when only data changes. The matplotlib backend's remaining
cost is dominated by `fig.clear()` + subplot/artist recreation + agg rendering.
