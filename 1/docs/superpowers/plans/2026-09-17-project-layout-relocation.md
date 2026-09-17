# Project Layout Relocation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Move all implemented project materials beneath `1/` and preserve the user's formatted Word report as a versioned project deliverable.

**Architecture:** The Python application becomes a self-contained script-oriented package at `1/app`, with `1/` treated as the assignment root rather than the repository root. Generated artifacts remain ignored under `1/app/output`, while the user-edited report is stored separately under tracked `1/reports` so pipeline reruns cannot overwrite it.

**Tech Stack:** Python 3.10, pytest, pathlib, Git, PowerShell, Microsoft Excel COM through pywin32.

**Spec:** `1/docs/superpowers/specs/2026-09-17-project-layout-relocation-design.md`

## Global Constraints

- All substantive project material must live under `1/`.
- Do not change calculation formulas or the contents of `1/data/data.csv`.
- Preserve `.worktrees/dcf-capex-pipeline` unchanged as an ignored backup checkout.
- Preserve `Итоговый_отчет_ФИП_оформленный.docx` byte-for-byte and track it in Git under `1/reports/`.
- Generated output and logs remain ignored.
- Work directly on `main`, as explicitly authorized by the user.

---

### Task 1: Establish the relocated-layout contract

**Files:**
- Create: `app/tests/test_project_layout.py`

**Interfaces:**
- Consumes: current test file location and the existing user report in `app/output/`.
- Produces: executable assertions for the assignment root and protected report destination.

- [x] **Step 1: Record the source report checksum**

Run:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath 'app\output\Итоговый_отчет_ФИП_оформленный.docx'
Get-Item -LiteralPath 'app\output\Итоговый_отчет_ФИП_оформленный.docx' | Select-Object Length
```

Expected: SHA-256 `5DFA48A68599C1CDD2DEDD05A161CF516C367D207DC2EEF962D931787936C338`, length `174398` bytes.

- [x] **Step 2: Write the failing layout test**

```python
"""Repository-level contract for the assignment's directory layout."""

from pathlib import Path


def test_all_project_materials_live_under_assignment_directory():
    assignment_root = Path(__file__).resolve().parents[2]

    assert assignment_root.name == "1"
    assert (assignment_root / "data" / "data.csv").is_file()
    assert (assignment_root / "task").is_dir()
    assert (assignment_root / "docs").is_dir()
    assert (
        assignment_root / "reports" / "Итоговый_отчет_ФИП_оформленный.docx"
    ).is_file()
```

- [x] **Step 3: Run the contract and verify RED**

Run:

```powershell
& 'C:\Program Files\PostgreSQL\15\pgAdmin 4\python\python.exe' `
  -c "import sys,site; sys.path.insert(0,r'.'); site.addsitedir(r'app\.python-packages'); import pytest; raise SystemExit(pytest.main([r'app\tests\test_project_layout.py','-q']))"
```

Expected: FAIL because the test resolves the repository root rather than a directory named `1`, and `1/reports` does not exist yet.

---

### Task 2: Relocate code and documentation and repair runtime paths

**Files:**
- Move: `app/` → `1/app/`
- Move: `docs/superpowers/plans/2026-09-16-dcf-capex-pipeline.md` → `1/docs/superpowers/plans/2026-09-16-dcf-capex-pipeline.md`
- Move: `docs/superpowers/specs/2026-09-16-dcf-capex-pipeline-design.md` → `1/docs/superpowers/specs/2026-09-16-dcf-capex-pipeline-design.md`
- Modify: `1/app/main.py`
- Modify: `1/app/run_tests.py`
- Modify: `1/app/src/pipeline.py`
- Modify: `1/app/tests/conftest.py`
- Modify: `1/app/tests/test_pipeline.py`
- Modify: `1/app/tests/test_excel_builder.py`
- Modify: all test modules importing `app.src` or `app.tests`
- Create: `1/reports/Итоговый_отчет_ФИП_оформленный.docx`

**Interfaces:**
- Consumes: `PipelineConfig.defaults(assignment_root: Path) -> PipelineConfig`.
- Produces: direct execution through `1/app/main.py`, imports through `src.*`, and output under `1/app/output`.

- [x] **Step 1: Move tracked trees while preserving Git history**

Use `git mv` for tracked application files and the two existing documentation files. Keep the newly written relocation spec and plan in their current `1/docs` locations.

- [x] **Step 2: Preserve the formatted report outside generated output**

Copy `app/output/Итоговый_отчет_ФИП_оформленный.docx` to `1/reports/Итоговый_отчет_ФИП_оформленный.docx`, then verify its length and SHA-256 against Task 1 before removing or relocating the old generated-output tree.

- [x] **Step 3: Update package imports**

In `1/app/main.py` and tests, replace imports such as:

```python
from app.src.pipeline import PipelineConfig, run_pipeline
```

with:

```python
from src.pipeline import PipelineConfig, run_pipeline
```

Replace `from app.tests.conftest import write_csv` with `from tests.conftest import write_csv`. Both `main.py` and `run_tests.py` put `APP_DIR` on `sys.path`, not its parent.

- [x] **Step 4: Update default paths**

In `1/app/main.py`:

```python
APP_DIR = Path(__file__).resolve().parent
ASSIGNMENT_ROOT = APP_DIR.parent
```

Call `PipelineConfig.defaults(ASSIGNMENT_ROOT)`.

In `1/app/src/pipeline.py`, return:

```python
return cls(
    csv_path=root / "data" / "data.csv",
    output_dir=root / "app" / "output",
    log_path=root / "app" / "logs" / "execution.log",
)
```

In `1/app/tests/conftest.py`, rename the fixture to `assignment_root`, keep `Path(__file__).resolve().parents[2]`, and resolve CSV as `assignment_root / "data" / "data.csv"`. Update test parameters using the fixture.

- [x] **Step 5: Run the layout contract and verify GREEN**

Run:

```powershell
& 'C:\Program Files\PostgreSQL\15\pgAdmin 4\python\python.exe' `
  -c "import sys,site; sys.path.insert(0,r'1\app'); site.addsitedir(r'1\app\.python-packages'); import pytest; raise SystemExit(pytest.main([r'1\app\tests\test_project_layout.py','-q']))"
```

Expected: `1 passed`.

- [x] **Step 6: Commit the working relocation**

```powershell
git add -A -- app docs 1/app 1/docs 1/reports
git commit -m "refactor: relocate project under assignment directory"
```

---

### Task 3: Update documentation and ignore rules

**Files:**
- Modify: `.gitignore`
- Modify: `1/app/README.md`
- Modify: `1/docs/superpowers/specs/2026-09-16-dcf-capex-pipeline-design.md`
- Modify: `1/docs/superpowers/plans/2026-09-16-dcf-capex-pipeline.md`

**Interfaces:**
- Consumes: the paths established by Task 2.
- Produces: accurate setup, launch, output, and test instructions for the new layout.

- [x] **Step 1: Replace ignored application paths**

Set `.gitignore` application entries to:

```gitignore
1/app/.venv/
1/app/.python-packages/
1/app/.test-tmp*/
1/app/output/
1/app/logs/
```

Keep `.worktrees/`, `.pytest_cache/`, `__pycache__/`, and `*.py[cod]`. Do not ignore `1/reports/`.

- [x] **Step 2: Update executable documentation paths**

Replace root-level `app/...` references with `1/app/...`, and describe `1/` as the assignment root. Document the protected report separately at `1/reports/Итоговый_отчет_ФИП_оформленный.docx`.

- [x] **Step 3: Scan for stale paths**

Run:

```powershell
rg -n '(^|[^1/])app/|from app\.|root / "1"' 1/app 1/docs
```

Expected: no executable or current architectural reference points to the obsolete root `app/`; historical wording may only remain where clearly labelled as previous state.

- [x] **Step 4: Commit documentation and ignore rules**

```powershell
git add .gitignore 1/app/README.md 1/docs
git commit -m "docs: align instructions with assignment layout"
```

---

### Task 4: Verify the relocated application end to end

**Files:**
- Verify: `1/app/tests/`
- Generate: `1/app/output/`
- Generate: `1/app/logs/execution.log`
- Verify: `1/reports/Итоговый_отчет_ФИП_оформленный.docx`

**Interfaces:**
- Consumes: `1/app/run_tests.py` and `1/app/main.py`.
- Produces: a verified `main` checkout with all project materials beneath `1/`.

- [x] **Step 1: Run all tests**

Run:

```powershell
& 'C:\Program Files\PostgreSQL\15\pgAdmin 4\python\python.exe' 1\app\run_tests.py
```

Expected: all 35 tests PASS, including the layout test and two test-runner path tests added during execution.

- [x] **Step 2: Run the production pipeline**

Run:

```powershell
& 'C:\Program Files\PostgreSQL\15\pgAdmin 4\python\python.exe' 1\app\main.py
```

Expected: successful DCF/CAPEX completion and seven generated artifact paths under `1/app`.

- [x] **Step 3: Verify protected and generated artifacts**

Confirm the protected report is tracked with `git ls-files`, has length `174398`, and has SHA-256 `5DFA48A68599C1CDD2DEDD05A161CF516C367D207DC2EEF962D931787936C338`. Confirm generated output and logs exist but are ignored.

- [x] **Step 4: Verify repository shape and source immutability**

Confirm root-level `app/` and `docs/` do not exist, `git diff --exit-code -- 1/data/data.csv` succeeds, and `git status --short --branch` contains no unexpected changes.

- [x] **Step 5: Commit any verification-only corrections**

If verification required a correction, stage only the relevant tracked files and commit with a focused message. Otherwise, do not create an empty commit.
