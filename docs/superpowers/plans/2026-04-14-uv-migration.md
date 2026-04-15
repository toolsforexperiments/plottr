# uv Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace pip-based environment management with `uv` across local dev and CI, keeping the `setuptools` + `versioningit` build backend intact.

**Architecture:** Consolidate all dependencies into `pyproject.toml` using `[dependency-groups]` for test deps. Delete legacy `requirements.txt`, `test_requirements.txt`, and `setup.py`. Update CI to use `astral-sh/setup-uv` and `uv run` for all commands. Generate and commit `uv.lock`.

**Tech Stack:** uv, pyproject.toml (PEP 735 dependency groups), GitHub Actions (`astral-sh/setup-uv@v6`)

---

## Files Modified / Deleted / Created

| File | Action | What changes |
|------|--------|-------------|
| `pyproject.toml` | Modify | Add `[dependency-groups]` section with test deps |
| `requirements.txt` | Delete | Duplicates `[project.dependencies]` |
| `test_requirements.txt` | Delete | Moves into `[dependency-groups]` |
| `setup.py` | Delete | Legacy shim, not needed with uv |
| `.github/actions/install-dependencies-and-plottr/action.yml` | Modify | Replace pip commands with `uv sync` |
| `.github/workflows/python-app.yml` | Modify | Replace `setup-python` + pip with `setup-uv`; prefix commands with `uv run` |
| `.github/workflows/python-release.yml` | Modify | Replace pip + twine with `uv build` + `uv publish` |
| `uv.lock` | Create (generated) | Lockfile for reproducible installs |

---

## Task 1: Add dependency-groups to pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add `[dependency-groups]` block**

Open `pyproject.toml`. After the `[project.optional-dependencies]` block (line ~54), add:

```toml
[dependency-groups]
test = [
    "qcodes",
    "pytest",
    "pytest-qt",
    "mypy==1.13.0",
    "PyQt5-stubs==5.15.6.0",
    "pandas-stubs",
]
```

Note: `watchdog` is already in `[project.dependencies]` — do NOT add it here.

- [ ] **Step 2: Verify pyproject.toml parses correctly**

```bash
python -c "import tomllib; tomllib.loads(open('pyproject.toml', 'rb').read())" 2>&1
```

Expected: no output (no errors).

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "build: add dependency-groups for test deps in pyproject.toml"
```

---

## Task 2: Delete legacy dependency files and setup.py

**Files:**
- Delete: `requirements.txt`
- Delete: `test_requirements.txt`
- Delete: `setup.py`

- [ ] **Step 1: Delete the files**

```bash
git rm requirements.txt test_requirements.txt setup.py
```

- [ ] **Step 2: Commit**

```bash
git commit -m "build: remove legacy requirements files and setup.py"
```

---

## Task 3: Generate and commit uv.lock

**Files:**
- Create: `uv.lock` (generated)

- [ ] **Step 1: Install uv if not already present**

```bash
uv --version
```

If not installed: follow https://docs.astral.sh/uv/getting-started/installation/

- [ ] **Step 2: Generate lockfile**

```bash
uv lock
```

Expected: `uv.lock` created in repo root.

- [ ] **Step 3: Verify uv.lock is not gitignored**

```bash
git status uv.lock
```

Expected: shows as untracked (not ignored). If it does NOT appear, open `.gitignore` and remove any line matching `uv.lock` or `*.lock`.

- [ ] **Step 4: Install env and verify it works**

```bash
uv sync --extra pyqt5 --group test
```

Expected: uv creates `.venv`, installs all packages, no errors.

- [ ] **Step 5: Run tests to verify env is correct**

```bash
uv run pytest test/pytest -x -q
```

Expected: tests pass (same result as before migration).

- [ ] **Step 6: Commit lockfile**

```bash
git add uv.lock
git commit -m "build: add uv.lock"
```

---

## Task 4: Update composite install action

**Files:**
- Modify: `.github/actions/install-dependencies-and-plottr/action.yml`

- [ ] **Step 1: Replace pip steps with uv sync**

Replace the entire file content with:

```yaml
name: "Install-dependencies-and-plottr"
description: "Install plottr and its dependencies"
runs:
  using: "composite"
  steps:
    - name: Install-dependencies
      run: uv sync --extra pyqt5 --group test
      shell: bash
```

Note: `setup-uv` (which installs uv itself) lives in each workflow, not here. This action only syncs.

- [ ] **Step 2: Commit**

```bash
git add .github/actions/install-dependencies-and-plottr/action.yml
git commit -m "ci: update install action to use uv sync"
```

---

## Task 5: Update test CI workflow

**Files:**
- Modify: `.github/workflows/python-app.yml`

- [ ] **Step 1: Replace setup-python + mypy/pytest steps**

Replace the entire file content with:

```yaml
name: Python application

on:
  push:
    branches: [ master ]
  pull_request:
    branches: [ master ]

jobs:
  build:

    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]
    env:
      DISPLAY: ':99.0'

    steps:
    - name: setup ubuntu-latest xvfb
      run: |
        sudo apt install libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-xinerama0 libxcb-xfixes0 x11-utils
        /sbin/start-stop-daemon --start --quiet --pidfile /tmp/custom_xvfb_99.pid --make-pidfile --background --exec /usr/bin/Xvfb -- :99 -screen 0 1920x1200x24 -ac +extension GLX
    - uses: actions/checkout@v4
    - name: Set up uv
      uses: astral-sh/setup-uv@v6
      with:
        python-version: ${{ matrix.python-version }}
    - uses: ./.github/actions/install-dependencies-and-plottr
    - name: Run Mypy
      run: uv run mypy plottr
    - name: Test with pytest
      run: uv run pytest test/pytest
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/python-app.yml
git commit -m "ci: switch test workflow to uv"
```

---

## Task 6: Update release CI workflow

**Files:**
- Modify: `.github/workflows/python-release.yml`

**Pre-condition:** Before merging this, update the GitHub repo secret. Go to repo Settings → Secrets and variables → Actions:
- Add secret: `PYPI_TOKEN` — value is a PyPI API token (from pypi.org → Account Settings → API tokens)
- The old `PYPI_USERNAME` / `PYPI_PASSWORD` secrets can be removed after confirming publish works.

- [ ] **Step 1: Replace build + twine steps with uv**

Replace the entire file content with:

```yaml
name: Upload Python Package

on:
  push:
    tags:
      - v*

jobs:
  deploy:

    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v4
    - name: Set up uv
      uses: astral-sh/setup-uv@v6
      with:
        python-version: '3.12'
    - name: Build
      run: uv build
    - name: Publish
      env:
        UV_PUBLISH_TOKEN: ${{ secrets.PYPI_TOKEN }}
      run: uv publish
```

Note: The install-dependencies action is no longer called here — publishing doesn't need a full dev install.

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/python-release.yml
git commit -m "ci: switch release workflow to uv build + uv publish"
```

---

## Task 7: Final local verification

- [ ] **Step 1: Clean env and re-sync from scratch**

```bash
rm -rf .venv
uv sync --extra pyqt5 --group test
```

Expected: clean install, no errors.

- [ ] **Step 2: Run full test suite**

```bash
uv run pytest test/pytest -v
```

Expected: same pass/fail result as before migration.

- [ ] **Step 3: Run mypy**

```bash
uv run mypy plottr
```

Expected: no new errors compared to pre-migration baseline.

- [ ] **Step 4: Verify app entry points work**

```bash
uv run plottr-autoplot-ddh5 --help
```

Expected: help text printed, no import errors.
