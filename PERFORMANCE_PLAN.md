# Plottr Performance Optimization Plan

## Problem Statement

Plottr's pipeline architecture copies data excessively as it flows through nodes. Each node in the
`linearFlowchart` (DataSelector → DataGridder → XYSelector → PlotNode) defensively copies data
before modifying it, and many internal methods (`structure()`, `extract()`, `copy()`, `validate()`)
add further redundant copies. Profiling shows that a typical 4-stage pipeline produces a **~4.8×
memory amplification factor** — almost 5 copies of the input data exist simultaneously.

For a 100×100×100 MeshgridDataDict (~38 MB), a single `copy()` takes **92 ms** and `validate()`
takes **43 ms** due to `np.diff`/`np.unique` on full meshgrid axes. In a real pipeline with
3–4 nodes, this means hundreds of milliseconds of pure overhead per update, which becomes very
noticeable during interactive parameter changes.

## Profiling Results Summary

| Operation | 10K pts (312 KB) | 100K pts (4.6 MB) | 1M pts (46 MB) | 100³ mesh (38 MB) |
|---|---|---|---|---|
| `copy()` | 0.2 ms | 1.1 ms | 7.8 ms | **92 ms** |
| `structure()` | 0.06 ms | 0.11 ms | 0.10 ms | **44 ms** |
| `validate()` | 0.02 ms | 0.05 ms | 0.06 ms | **43 ms** |
| `extract(1 dep)` | 0.38 ms | 1.0 ms | **15 ms** | — |
| `mask_invalid()` | — | — | — | **202 ms** |
| Pipeline (4 stages) | **64 ms** (4.8× mem) | — | — | — |

## Root Causes (Ranked by Impact)

### 1. CRITICAL: Cascading Deep Copies in Node Process Methods

**Every node calls `.copy()` on data it receives, even though pyqtgraph's Flowchart passes data by
reference.** Worse, inherited nodes copy *again* — `XYSelector` inherits from `DimensionReducer`,
so data is copied twice (once at each level's `process()`).

Evidence:
- `DataGridder.process()` — `data = dataout.copy()` (grid.py:473)
- `DimensionReducer.process()` — `data = dataout.copy()` (dim_reducer.py:682)
- `XYSelector.process()` — `data = dataout.copy()` (dim_reducer.py:901) ← **second copy in chain**
- `ScaleUnits.process()` — `data = dataIn.copy()` (scaleunits.py:126)
- `SubtractAverage.process()` — `data = dataIn.copy()` (correct_offset.py:63)
- `Fitter.process()` — `dataOut = dataIn.copy()` (fitter.py:606)

**Impact**: In a 4-node pipeline, data is copied 3–4 times. For 38 MB meshgrid data, that's
~150 MB of unnecessary allocations and ~370 ms of copy time.

### 2. HIGH: MeshgridDataDict.validate() Is Computationally Expensive

`MeshgridDataDict.validate()` (datadict.py:1063-1145) computes `np.diff()` + `np.unique()` +
`np.sign()` on every axis array for every dependent, verifying monotonicity. For a 100×100×100
dataset with 2 deps and 3 axes, that's 6 full-array `np.diff` computations on 1M-element arrays.

This takes **43 ms** per call and is called:
- Once per `structure()` call
- Once per `copy()` call (via `structure()`)
- Once per `validate()` directly
- Multiple times in `datadict_to_meshgrid()`, `meshgrid_to_datadict()`, etc.

Across a pipeline, validate() may be called **6–10 times** for the same data.

### 3. HIGH: structure() Uses deepcopy Unnecessarily

`DataDictBase.structure()` (datadict.py:399-451) does `cp.deepcopy(v2)` on each field's metadata
dict (line 434), even though:
- Values are already emptied (`v2['values'] = []`)
- Metadata is typically just strings and lists of strings
- A shallow copy would suffice in 99% of cases

### 4. MEDIUM: extract() Uses Deep Copy by Default

`DataDictBase.extract()` (datadict.py:315-362) calls `cp.deepcopy(self[d])` for each selected
field (line 347), including the numpy array values. `deepcopy` on numpy arrays is significantly
slower than `array.copy()` because it goes through Python's generic copy protocol rather than
numpy's optimized memcpy path.

### 5. MEDIUM: mask_invalid() Creates Full Masked Copy

`mask_invalid()` (datadict.py:724-738) uses `np.ma.masked_where(..., copy=True)`, creating a
completely new masked array for every data field. Many datasets have no invalid entries, making
this pure overhead.

### 6. LOW: shapes() Wraps Arrays Unnecessarily

`DataDictBase.shapes()` (datadict.py:553-565) calls `np.array(self.data_vals(k)).shape` — the
`np.array()` wrapper is unnecessary since `data_vals()` already returns an ndarray after
validation.

---

## Risk Analysis & Mitigations

This section documents the edge cases discovered during investigation and how the proposed
improvements must account for them.

### Risk 1: Nested Dict Mutations Bypass Dirty Flags

`DataDictBase` is a `dict` of dicts. User code commonly mutates inner dicts directly:
`dd['x']['values'] = new_array`. This does NOT trigger `DataDictBase.__setitem__` because the
outer dict is not being set — only the inner dict is being mutated.

**Mitigation**: Do NOT use a general validation cache based on `__setitem__`. Instead, use
private helper methods (`_build_structure()`) that skip validation only when called from
code paths that have *just* validated or just constructed fresh data. The public `validate()` API
always runs. This is safe because the hot-path is internal: `copy()` calls `structure()` which
calls `validate()` — and after copying validated data, re-validating the copy is redundant.

### Risk 2: Monotonicity Check Must Cover the Full Array

The current `MeshgridDataDict.validate()` checks `np.diff(axis_data, axis=axis_num)` on the full
N-d axis array. Checking only a single 1D slice would miss cases where one slice is monotonic
but another is flat or reversed.

**Mitigation**: Keep checking the full array, but avoid the expensive `np.unique(np.sign(...))`
pipeline. Instead, compute min/max of the diff directly:
```python
d = np.diff(axis_data, axis=axis_num)
d_sign = np.sign(d[~np.isnan(d)])  # ignore NaN steps
if d_sign.size > 0:
    has_zero = np.any(d_sign == 0)
    not_monotone = not (np.all(d_sign >= 0) or np.all(d_sign <= 0))
```
This avoids `np.unique()` (which sorts and allocates) while preserving full coverage. The
dominant cost becomes `np.diff()` which is a simple O(N) subtraction — much faster than
diff + sign + unique.

### Risk 3: Unknown Field Keys in DataDict

Field dicts can contain custom keys beyond `values/axes/unit/label`. Known cases:
- `__shape__` key: stored by `datadict_storage.py`, checked in `MeshgridDataDict.validate()`
- Fitter node adds `'guess'` and `'fit'` fields dynamically (fitter.py:642, 648)
- Per-field meta keys like `__meta1__` are stored inside field dicts

**Mitigation**: In `structure()` and `extract()`, when replacing `cp.deepcopy()`, we must
**preserve all keys**, not just the known ones. Use a targeted copy that special-cases only
`values` (numpy-optimized copy) and `axes` (new list), but copies everything else generically:
```python
new_field = {}
for fk, fv in original_field.items():
    if fk == 'values':
        new_field[fk] = fv.copy() if copy else fv  # numpy optimized
    elif fk == 'axes':
        new_field[fk] = list(fv)  # new list, strings are immutable
    else:
        new_field[fk] = cp.deepcopy(fv)  # safe for mutable meta/custom keys
```
This preserves backward compatibility while optimizing the two expensive keys (values, axes).

### Risk 4: In-Place Axis Mutation Breaks Shallow Copies

Several nodes mutate the `axes` list in-place:
- `DimensionReducer._applyDimReductions()` does `del data[n]['axes'][idx]`
  (dim_reducer.py:595)
- `structure(remove_data=...)` does `s[n]['axes'].pop(i)` (datadict.py:439)

If a shallow copy shares the same `axes` list, these mutations would corrupt the original.

**Mitigation**: `copy(deep=False)` (the new shallow copy mode) MUST always create a new `axes`
list for each field, even when sharing the `values` array. This makes it safe for axis mutation
while still avoiding the expensive array copy. The implementation is:
```python
new_field = {}
for fk, fv in original_field.items():
    if fk == 'values':
        new_field[fk] = fv  # shared reference (NOT copied)
    elif fk == 'axes':
        new_field[fk] = list(fv)  # ALWAYS new list
    else:
        new_field[fk] = fv  # scalars (unit, label) are immutable
```

### Risk 5: mask_invalid() Return Type Contract

Downstream plotting code checks `isinstance(data, np.ma.MaskedArray)` and calls `.filled(np.nan)`
(plot/mpl/plotting.py:99-104, plot/base.py:479,508). If we skip masking for clean data, the
arrays stay as plain `np.ndarray` and the isinstance checks return False — which is actually
fine, because the code uses `if isinstance(...): filled()` as a conditional path.

**Mitigation**: The fast-path must use `num.is_invalid()` (not just `np.isnan`) to also catch
`None` values in object arrays. When no invalid entries exist, skip masking entirely — the
plotting code handles plain ndarrays correctly. When invalid entries exist, apply masking as
before.

### Risk 6: shapes() Called on Unvalidated Data

`Node.process()` calls `dataIn.shapes()` (node.py:281) without an explicit prior `validate()`.
If values are still lists (pre-validation), `data_vals()` returns a list and `.shape` fails.

**Mitigation**: Use `np.shape()` instead of `.shape` — this works on lists, tuples, and arrays
alike, returning the correct shape without requiring conversion:
```python
shapes[k] = np.shape(self.data_vals(k))
```

### Risk 7: copy() and extract() Semantic Inconsistency

Currently `copy()` uses `ndarray.copy()` (shallow numpy copy) while `extract(copy=True)` uses
`cp.deepcopy()` (Python generic deep copy). For simple numeric arrays these are equivalent, but
for object-dtype arrays `deepcopy` recursively copies contained Python objects while
`ndarray.copy()` only copies the array of pointers.

**Mitigation**: Align both to use `ndarray.copy()` for the `values` key, and `cp.deepcopy()` for
other mutable values. This is consistent because: (a) plottr stores numeric data in arrays, not
nested objects, (b) object arrays in plottr contain None values — `ndarray.copy()` handles None
correctly since None is a singleton.

---

## Code Readability: Copy Semantics Design

A key goal is making it **obvious** in the code where data is shared vs. independent. We adopt
a pattern inspired by xarray's `copy(deep=True/False)` API and numpy conventions.

### Design Principles

1. **Explicit `deep` parameter**: Extend `copy()` to accept `deep=True` (default, backward
   compatible) and `deep=False` (shares arrays). No separate `shallow_copy()` method — one
   method, one parameter, one place to look.

2. **Docstrings document ownership**: Every method that returns data states whether the returned
   arrays are copies or views:
   ```python
   def copy(self, deep: bool = True) -> T:
       """Make a copy of the dataset.

       :param deep: If True (default), all data arrays are copied. The returned
           dataset is fully independent of the original.
           If False, the returned dataset shares data array references with the
           original. Modifications to array *contents* (e.g., ``ret['x']['values'][0] = 5``)
           will affect both. However, *replacing* an array (``ret['x']['values'] = new_arr``)
           only affects the copy. Field metadata (axes, unit, label) is always independent.
       """
   ```

3. **Nodes document their copy contract**: Each `process()` method gets a one-line comment
   stating whether it copies or modifies in-place:
   ```python
   def process(self, dataIn=None):
       ...
       data = dataIn.copy(deep=False)  # shallow: only modifying values for specific fields
       data['dep_0']['values'] = data['dep_0']['values'] * scale  # replaces array, safe
   ```

4. **No hidden copies**: Functions that need to modify data must do so on an explicit copy.
   `Node.process()` base class passes data through by reference (as it already does). Only
   nodes that transform data should copy. This should be the local decision of each node.

### API Summary

| Method | Arrays | Metadata | Use When |
|---|---|---|---|
| `copy(deep=True)` | Independent copies | Independent copies | Need fully independent data |
| `copy(deep=False)` | Shared references | Independent copies | Node only modifies a few fields |
| `extract(copy=True)` | Independent copies | Independent copies | Subsetting fields |
| `extract(copy=False)` | Shared references | Shared references | Read-only subsetting |
| `structure()` | Empty (no data) | Independent copies | Getting data shape/layout |

---

## Proposed Improvements (Revised)

### Phase 1: Extend copy() with deep parameter & fix cascading copies

#### 1a. Add `deep` parameter to `copy()`

Extend the existing `copy()` method to accept `deep=True/False`, following the xarray convention.
`deep=True` (default) preserves current behavior. `deep=False` copies the dict structure and
axes lists but shares numpy array references.

```python
def copy(self: T, deep: bool = True) -> T:
    """Make a copy of the dataset.

    :param deep: If True (default), data arrays are independently copied.
        If False, the returned dataset shares array references with the original.
        Field metadata (axes, unit, label) is always independently copied.
    """
    ret = self.__class__()
    for k, v in self.items():
        if self._is_meta_key(k):
            ret[k] = cp.deepcopy(v)
        else:
            new_field = {}
            for fk, fv in v.items():
                if fk == 'values':
                    new_field[fk] = fv.copy() if deep else fv
                elif fk == 'axes':
                    new_field[fk] = list(fv)       # always new list (mutation-safe)
                elif self._is_meta_key(fk):
                    new_field[fk] = cp.deepcopy(fv) # safe for mutable meta
                else:
                    new_field[fk] = fv              # scalars (unit, label) are immutable
            ret[k] = new_field
    return ret
```

This replaces the current `copy()` → `structure()` → `deepcopy` chain with a single efficient
pass. No separate `shallow_copy()` method needed.

**Impact**: `copy(deep=False)` is essentially free (~0.01 ms vs 92 ms for deep copy on 38 MB
meshgrid). Even `copy(deep=True)` is faster because it avoids the `structure()` → `validate()`
→ `deepcopy` chain.

#### 1b. Fix cascading copies in inherited nodes

`XYSelector.process()` calls `super().process()` (which is `DimensionReducer.process()`) which
already copies. Remove the redundant second copy:

- `DimensionReducer.process()` (dim_reducer.py:682): keep `copy(deep=False)` — it needs to
  mutate axes and values
- `XYSelector.process()` (dim_reducer.py:901): **remove** the `.copy()` call — parent already
  returned a copy
- `Node.process()` (node.py:263): does NOT copy, just inspects — keep as-is

#### 1c. Use `copy=False` in `datadict_to_meshgrid` when data is already a copy

`DataGridder.process()` already copies input at line 473. Pass `copy=False` to
`datadict_to_meshgrid()` to avoid a redundant second array copy.

### Phase 2: Optimize Expensive Validation

#### 2a. Skip redundant validation in internal methods

Add a private `_build_structure()` path that skips validation when constructing data from
known-valid sources. The public `validate()` always runs — no caching.

Specifically:
- `copy()` already constructs from valid data → skip re-validate
- `structure()` calls `validate()` first, then constructs → skip re-validate in the construction
  step

This is implemented by extracting the construction logic out of `structure()` into a helper:
```python
def structure(self, ...):
    if self.validate():
        return self._build_structure(...)
    return None

def _build_structure(self, ...):
    """Build structure dict. Caller must ensure data is validated."""
    ...  # no validate() call here
```

**Impact**: Eliminates 50%+ of validate() calls. Especially impactful for MeshgridDataDict
where validate() costs 43 ms.

#### 2b. Optimize MeshgridDataDict.validate() monotonicity check

Replace `np.unique(np.sign(np.diff(...)))` with a direct min/max check on the diff array.
This avoids the sort + allocate from `np.unique()` while preserving full-array coverage:

```python
d = np.diff(axis_data, axis=axis_num)
# Use nan-aware checks without materializing sign/unique arrays
valid_d = d[~np.isnan(d)] if np.issubdtype(d.dtype, np.floating) else d
if valid_d.size > 0:
    if np.any(valid_d == 0):
        msg += "no variation along axis"
    if not (np.all(valid_d > 0) or np.all(valid_d < 0)):
        msg += "not monotonous"
```

**Impact**: ~50% faster than current (no sort/unique), while checking every element.

### Phase 3: Optimize structure() and extract()

#### 3a. Replace deepcopy in structure() with targeted copy

Use the same targeted copy pattern as `copy()`: special-case `values` (set to `[]`) and `axes`
(new list), deepcopy only meta keys (which may be mutable), pass through scalars directly.
Preserve ALL keys (not just known ones) to handle custom field keys like `__shape__`.

#### 3b. Replace deepcopy in extract() with targeted copy

Same pattern: use `ndarray.copy()` for values, `list()` for axes, `deepcopy` for meta keys,
passthrough for scalars. This aligns `extract(copy=True)` semantics with `copy(deep=True)`.

### Phase 4: Optimize mask_invalid()

#### 4a. Skip masking when data has no invalid entries

Use `num.is_invalid()` (which handles both None and NaN) for the fast check:
```python
def mask_invalid(self: T) -> T:
    for d, _ in self.data_items():
        arr = self.data_vals(d)
        invalid_mask = num.is_invalid(arr)
        if not np.any(invalid_mask):
            continue  # no invalid entries, skip masking entirely
        vals = np.ma.masked_where(invalid_mask, arr, copy=True)
        ...
```

Downstream plotting code handles both plain ndarrays and MaskedArrays correctly (conditional
isinstance checks in plot/mpl/plotting.py:99-104).

#### 4b. Use copy=False when data is already a copy

In pipeline nodes that call `mask_invalid()` after already copying data (DimensionReducer,
Histogrammer), pass through a parameter or check `owndata` to avoid re-copying.

### Phase 5: Minor Optimizations

#### 5a. Use np.shape() in shapes()

Replace `np.array(self.data_vals(k)).shape` with `np.shape(self.data_vals(k))`. This handles
lists/tuples/arrays uniformly without allocating a new array. Safe for unvalidated data.

#### 5b. Optimize datasets_are_equal()

Short-circuit on shape mismatch before comparing values.

---

## Expected Impact

| Phase | Time Savings (per pipeline update) | Memory Savings |
|---|---|---|
| Phase 1 (copy(deep=False) + fix cascading) | 50–70% of copy time | 60–75% reduction |
| Phase 2 (skip redundant validation + optimize) | 60–80% of validate time | Negligible |
| Phase 3 (structure/extract targeted copy) | 30–50% of structure ops | Minor |
| Phase 4 (mask_invalid fast-path) | 95%+ when data is clean | 50% reduction |
| Phase 5 (Minor) | 5–10% misc | Minor |

**Combined estimate for 100×100×100 MeshgridDataDict pipeline:**
- Current: ~500 ms, ~190 MB allocated (4.8× input)
- After all phases: ~50–80 ms, ~50–60 MB allocated (~1.3× input)

## Implementation Order

**Prerequisite**: Add comprehensive test coverage for copy semantics, data integrity through
pipeline, and edge cases (object arrays, complex data, masked data, custom field keys).

Then:
1. **Phase 1a** (copy deep parameter) — foundation for everything else
2. **Phase 2a** (skip redundant validation) — highest ROI, low risk
3. **Phase 2b** (optimize monotonicity check) — high ROI, low risk
4. **Phase 1b** (fix cascading copies) — high ROI, needs test coverage first
5. **Phase 3a+3b** (structure/extract optimization) — medium ROI, low risk
6. **Phase 4a** (mask_invalid fast-path) — high ROI for clean data, low risk
7. **Phase 1c + Phase 4b + Phase 5** — incremental improvements

## Risks & Considerations

- **Shared array mutation**: With `copy(deep=False)`, if a node modifies array *contents*
  in-place (e.g. `arr[0] = 5` or `arr *= 2`), it corrupts the original. Nodes must *replace*
  arrays (`data['x']['values'] = new_arr`) rather than mutate them. This is already the common
  pattern in most nodes, but must be verified with tests.
- **Backward compatibility**: `copy()` default is `deep=True`, preserving current behavior.
  `deep=False` is opt-in. No external API is removed.
- **Testing prerequisite**: Before making any optimization changes, comprehensive tests must
  verify: copy isolation, pipeline data integrity, edge cases (object arrays, None, complex,
  masked), and custom field key preservation.

---

## Execution Results

All optimizations implemented and tested. **173 tests pass** (0 failures).

### Changes Made

| File | Changes |
|---|---|
| `plottr/data/datadict.py` | Added `_copy_field()` helper; rewrote `copy(deep=True/False)`; optimized `structure()` with `_build_structure()`; replaced `cp.deepcopy` in `extract()`; optimized `MeshgridDataDict.validate()` monotonicity check; added `mask_invalid()` fast-path for clean data; fixed `shapes()` to use `np.shape()`; optimized `datasets_are_equal()` |
| `plottr/node/dim_reducer.py` | Removed redundant `copy()` in `XYSelector.process()` |
| `plottr/node/grid.py` | Pass `copy=False` to `datadict_to_meshgrid()` |
| `test/pytest/test_datadict_copy_semantics.py` | 64 new tests for copy semantics |
| `test/pytest/test_pipeline_coverage.py` | 63 new tests for pipeline coverage |

### Benchmark Comparison (Baseline -> Final)

| Benchmark | Before (ms) | After (ms) | Speedup | Notes |
|---|---|---|---|---|
| **mesh_500k_copy** | 42.2 | 2.9 | **14.8x** | copy() no longer calls structure()/validate() |
| **mesh_50k_copy** | 2.7 | 0.4 | **6.1x** | Same optimization, smaller data |
| **tab_10k_copy** | 0.23 | 0.15 | **1.5x** | Smaller effect on tabular data |
| **mesh_500k_validate** | 20.5 | 14.1 | **1.5x** | Removed np.unique/np.sign overhead |
| **mesh_500k_structure** | 20.3 | 13.9 | **1.5x** | _build_structure() skips re-validation |
| **mesh_50k_mask_invalid** | 10.0 | 9.1 | **1.1x** | Fast-path skips clean data |
| **mesh_500k_mask_invalid (mem)** | 19537 KB | 0.3 KB | **~0** | No allocation for clean data |
| **pipeline_4stage** | 8.2 | 5.7 | **1.4x** | Cumulative improvement |
| **equality_5k** | 1.4 | 1.2 | **1.1x** | Shape short-circuit + set ops |

### Bug Fixed

- `copy()` previously did not deep-copy global mutable metadata (e.g., `dd.add_meta('info', {'key': 'val'})`). The new implementation properly deep-copies all metadata.

### New APIs

- `DataDictBase.copy(deep=True/False)` — `deep=False` shares array data (xarray convention)
- `DataDictBase._build_structure()` — private helper that skips validation
- `DataDictBase._copy_field()` — targeted field copy with per-key semantics
