# DCF/CAPEX Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run a reproducible Python pipeline in `app/` that calculates the DCF/CAPEX model, validates it against a recalculated Excel workbook, executes risk scenarios, and generates all required Russian-language artifacts.

**Architecture:** Typed dataclasses carry validated project data and immutable calculation results between focused modules. Python and formula-driven Excel implement the same documented cash-flow architecture independently; the orchestrator stops before reporting unless Excel recalculation, comparison, and automated tests succeed.

**Tech Stack:** Python 3.10+, pytest, NumPy, openpyxl, pywin32/Microsoft Excel COM, Matplotlib, python-docx.

**Spec:** `docs/superpowers/specs/2026-09-16-dcf-capex-pipeline-design.md`

## Global Constraints

- All production code and generated artifacts live under `app/`; inputs under `1/data/` remain unchanged.
- Machine calculations use CSV values when PDF and CSV conflict, while every conflict is disclosed.
- Excel visible labels are Russian and its model uses cell formulas followed by actual Microsoft Excel recalculation.
- Python/Excel relative deviation for key numeric metrics must be strictly below `0.01%`.
- Base cash flow uses `I0 = TCI`, depreciation base `FCI`, no terminal value, no repeated operating-year CAPEX, and no invented annual `ΔNWC`.
- Monte Carlo uses 1000 seeded lognormal iterations with CAPEX CV `30%` and Revenue CV `20%`.
- The Word report is created only after all blocking validation and comparison gates pass.

---

### Task 1: Project foundation and validated input model

**Files:**
- Create: `app/requirements.txt`
- Create: `app/src/__init__.py`
- Create: `app/src/models.py`
- Create: `app/src/data_loader.py`
- Create: `app/tests/conftest.py`
- Create: `app/tests/test_data_loader.py`

**Interfaces:**
- Produces: `ProjectData`, `InputConflict`, `ValidationRecord`, `load_project_data(path: Path) -> ProjectData`.
- Consumes: CSV columns `Category`, `Item`, `Value` and known PDF control values WACC `0.10`, working-capital share `0.12`.

- [ ] **Step 1: Declare exact dependencies**

```text
numpy>=2.0,<3
openpyxl>=3.1,<4
pywin32>=306
matplotlib>=3.8,<4
python-docx>=1.1,<2
pytest>=8,<9
```

- [ ] **Step 2: Write failing loader tests**

```python
def test_loads_real_csv_and_reports_pdf_conflicts(real_csv_path):
    data = load_project_data(real_csv_path)
    assert data.project_lifetime_years == 10
    assert data.revenue[2] == 0.0
    assert data.revenue[3] == 45.0
    assert {(c.field, c.pdf_value, c.csv_value) for c in data.conflicts} == {
        ("wacc", 0.10, 0.12),
        ("working_capital_share", 0.12, 0.15),
    }

def test_rejects_duplicate_profile_year(tmp_path):
    csv_path = write_csv(tmp_path, rows_with_duplicate_revenue_year())
    with pytest.raises(DataValidationError, match="дублируется"):
        load_project_data(csv_path)
```

- [ ] **Step 3: Run tests and verify RED**

Run: `app/.venv/Scripts/python.exe -m pytest app/tests/test_data_loader.py -v`

Expected: collection/import failure because `app.src.data_loader` does not exist.

- [ ] **Step 4: Implement typed models and strict CSV validation**

```python
@dataclass(frozen=True)
class ProjectData:
    equipment: tuple[EquipmentItem, ...]
    lang_factor: float
    working_capital_share: float
    wacc: float
    tax_rate: float
    project_lifetime_years: int
    revenue: dict[int, float]
    opex: dict[int, float]
    conflicts: tuple[InputConflict, ...]
    validations: tuple[ValidationRecord, ...]

def load_project_data(path: Path) -> ProjectData:
    rows = _read_rows(path)
    _validate_headers(rows.headers)
    parsed = _parse_unique_rows(rows)
    _validate_ranges(parsed)
    _validate_horizon(parsed)
    return _build_project_data(parsed)
```

Validation must reject missing columns/values, non-numeric `Value`, duplicate `(Category, Item)`, missing parameters, non-integral/non-positive lifetime, WACC or tax below zero, WC outside `[0,1)`, non-positive Lang factor, and incomplete/mismatched yearly profiles.

- [ ] **Step 5: Run loader tests and full tests**

Run: `app/.venv/Scripts/python.exe -m pytest app/tests/test_data_loader.py -v`

Expected: PASS.

- [ ] **Step 6: Commit the input layer**

```powershell
git add app/requirements.txt app/src app/tests/conftest.py app/tests/test_data_loader.py
git commit -m "feat: validate DCF project inputs"
```

### Task 2: Deterministic financial model and comparison primitives

**Files:**
- Create: `app/src/financial_model.py`
- Create: `app/src/comparator.py`
- Create: `app/tests/test_financial_model.py`
- Create: `app/tests/test_comparator.py`

**Interfaces:**
- Consumes: `ProjectData`.
- Produces: `FinancialModel.calculate() -> FinancialResult`, `calculate_lang_capex() -> CapitalEstimate`, `compare_metrics(python_metrics, excel_metrics, tolerance_percent=0.01) -> ComparisonResult`.

- [ ] **Step 1: Write failing formula and edge-status tests**

```python
def test_lang_capex_uses_equipment_fci_and_wc_tci(real_project_data):
    estimate = FinancialModel(real_project_data).calculate_lang_capex()
    assert estimate.equipment_cost == pytest.approx(230.0)
    assert estimate.fci == pytest.approx(834.9)
    assert estimate.tci == pytest.approx(834.9 / 0.85)

def test_dcf_does_not_repeat_initial_capex(real_project_data):
    result = FinancialModel(real_project_data).calculate()
    assert result.cash_flows[0] == pytest.approx(-result.capital.tci)
    assert all(row.capex == 0.0 and row.delta_nwc == 0.0 for row in result.rows)
    assert all(row.depreciation == pytest.approx(result.capital.fci / 10) for row in result.rows)

def test_zero_capex_returns_undefined_pi(project_data_factory):
    result = FinancialModel(project_data_factory(equipment_costs=(0.0,))).calculate()
    assert result.pi.value is None
    assert result.pi.status == "НЕ ОПРЕДЕЛЕН: первоначальные инвестиции равны нулю"
```

- [ ] **Step 2: Run finance tests and verify RED**

Run: `app/.venv/Scripts/python.exe -m pytest app/tests/test_financial_model.py app/tests/test_comparator.py -v`

Expected: import failure because finance modules do not exist.

- [ ] **Step 3: Implement deterministic formulas and robust statuses**

```python
class FinancialModel:
    def calculate_lang_capex(self) -> CapitalEstimate:
        equipment_cost = sum(item.cost for item in self.data.equipment)
        fci = self.data.lang_factor * equipment_cost
        tci = fci / (1.0 - self.data.working_capital_share)
        return CapitalEstimate(equipment_cost, fci, tci)

    def calculate(self) -> FinancialResult:
        capital = self.calculate_lang_capex()
        depreciation = capital.fci / self.data.project_lifetime_years
        rows = tuple(self._year_row(year, depreciation) for year in self.data.years)
        cash_flows = (-capital.tci, *(row.fcf for row in rows))
        return self._metrics(capital, rows, cash_flows)
```

Implement IRR with bracket scanning plus bisection over economically valid rates greater than `-1`, reporting zero/multiple/no roots. Implement PI from discounted positive-year FCF divided by `I0`. Implement interpolated DPBP from cumulative discounted flow. Use immutable result dataclasses.

- [ ] **Step 4: Implement comparison with zero-safe relative deviation**

```python
def compare_value(name: str, python_value: float, excel_value: float, tolerance_percent: float) -> MetricComparison:
    absolute = abs(python_value - excel_value)
    relative_percent = 0.0 if excel_value == 0 and absolute == 0 else (
        None if excel_value == 0 else absolute / abs(excel_value) * 100.0
    )
    matches = absolute < 1e-9 if relative_percent is None else relative_percent < tolerance_percent
    return MetricComparison(name, python_value, excel_value, absolute, relative_percent, "СОВПАДАЕТ" if matches else "НЕ СОВПАДАЕТ")
```

- [ ] **Step 5: Run tests and verify GREEN**

Run: `app/.venv/Scripts/python.exe -m pytest app/tests/test_financial_model.py app/tests/test_comparator.py -v`

Expected: PASS.

- [ ] **Step 6: Commit deterministic model**

```powershell
git add app/src/financial_model.py app/src/comparator.py app/src/models.py app/tests
git commit -m "feat: calculate and compare DCF metrics"
```

### Task 3: Boundary scenarios, Monte Carlo, stress test, and charts

**Files:**
- Create: `app/src/scenarios.py`
- Create: `app/src/monte_carlo.py`
- Create: `app/src/charts.py`
- Create: `app/tests/test_scenarios.py`
- Create: `app/tests/test_monte_carlo.py`

**Interfaces:**
- Consumes: `ProjectData`, `FinancialResult`.
- Produces: `run_boundary_tests(data) -> tuple[ScenarioTestResult, ...]`, `run_stress_test(data) -> StressResult`, `run_monte_carlo(data, iterations=1000, seed=20260916) -> MonteCarloResult`, `save_monte_carlo_charts(result, output_dir) -> tuple[Path, Path]`.

- [ ] **Step 1: Write failing scenario and reproducibility tests**

```python
def test_wacc_zero_equals_undiscounted_cash_flow(real_project_data):
    result = run_boundary_tests(real_project_data)
    case = next(item for item in result if item.code == "WACC_ZERO")
    assert case.passed

def test_monte_carlo_is_seeded_and_has_exact_iteration_count(real_project_data):
    first = run_monte_carlo(real_project_data, iterations=1000, seed=20260916)
    second = run_monte_carlo(real_project_data, iterations=1000, seed=20260916)
    np.testing.assert_array_equal(first.npv_values, second.npv_values)
    assert len(first.npv_values) == 1000
    assert 0.0 <= first.probability_negative <= 1.0
```

- [ ] **Step 2: Run scenario tests and verify RED**

Run: `app/.venv/Scripts/python.exe -m pytest app/tests/test_scenarios.py app/tests/test_monte_carlo.py -v`

Expected: import failure because scenario modules do not exist.

- [ ] **Step 3: Implement immutable scenario transforms**

```python
def scaled_project(data: ProjectData, *, equipment_factor: float = 1.0, revenue_factor: float = 1.0, wacc: float | None = None) -> ProjectData:
    return replace(
        data,
        equipment=tuple(replace(item, cost=item.cost * equipment_factor) for item in data.equipment),
        revenue={year: value * revenue_factor for year, value in data.revenue.items()},
        wacc=data.wacc if wacc is None else wacc,
    )
```

Boundary tests use assertions on mathematical properties. Stress uses equipment factor `2.0` and Revenue factor `0.7`, then calculates absolute and zero-safe relative changes.

- [ ] **Step 4: Implement mathematically parameterized lognormal simulation**

```python
def lognormal_parameters(cv: float) -> tuple[float, float]:
    sigma = math.sqrt(math.log1p(cv * cv))
    mu = -0.5 * sigma * sigma
    return mu, sigma

capex_factors = rng.lognormal(*lognormal_parameters(0.30), size=iterations)
revenue_factors = rng.lognormal(*lognormal_parameters(0.20), size=iterations)
```

Calculate summary statistics with population standard deviation and quantiles `[0.05, 0.25, 0.50, 0.75, 0.95]`. Plot a Russian histogram and sorted empirical CDF `P(NPV ≤ x)` using Matplotlib's non-interactive `Agg` backend.

- [ ] **Step 5: Run tests and verify GREEN**

Run: `app/.venv/Scripts/python.exe -m pytest app/tests/test_scenarios.py app/tests/test_monte_carlo.py -v`

Expected: PASS and two non-empty PNG files in a temporary test directory.

- [ ] **Step 6: Commit risk analysis**

```powershell
git add app/src/scenarios.py app/src/monte_carlo.py app/src/charts.py app/tests
git commit -m "feat: add DCF risk and stress analysis"
```

### Task 4: Formula-driven Excel Ground Truth and real recalculation

**Files:**
- Create: `app/src/excel_builder.py`
- Create: `app/tests/test_excel_builder.py`

**Interfaces:**
- Consumes: validated inputs, Python results, boundary/Monte Carlo/stress results.
- Produces: `build_workbook(context, path) -> ExcelCellMap`, `recalculate_with_excel(path) -> None`, `read_excel_metrics(path, cell_map) -> dict[str, float | str]`.

- [ ] **Step 1: Write failing workbook-structure tests**

```python
def test_workbook_contains_russian_sheets_and_formulas(real_project_data, tmp_path):
    path = tmp_path / "DCF_Ground_Truth.xlsx"
    cell_map = build_workbook(minimal_context(real_project_data), path)
    workbook = load_workbook(path, data_only=False)
    assert workbook.sheetnames == EXPECTED_RUSSIAN_SHEETS
    assert workbook["DCF-модель"]["F5"].value.startswith("=")
    assert workbook["Ключевые показатели"][cell_map.metrics["NPV"]].value.startswith("=")
```

- [ ] **Step 2: Run Excel tests and verify RED**

Run: `app/.venv/Scripts/python.exe -m pytest app/tests/test_excel_builder.py -v`

Expected: import failure because `excel_builder` does not exist.

- [ ] **Step 3: Build all nine formatted sheets and formulas**

Use named cells for `Коэффициент_Ленга`, `Доля_оборотного_капитала`, `WACC`, `Ставка_налога`, `Срок_проекта`. DCF rows reference input profile cells and calculate depreciation, EBIT, NOPAT, FCF, discount factor, discounted flow, and cumulative flow. Metrics formulas reference these ranges:

```excel
NPV: =NPV(WACC, FCF_YEAR_1:FCF_YEAR_N)-TCI
IRR: =IRR(CF_YEAR_0:CF_YEAR_N)
PI: =IF(TCI=0,NA(),SUM(DISCOUNTED_FCF_RANGE)/TCI)
DPBP: numeric interpolation from the first cumulative discounted flow >= 0
```

Store exact metric cells in `ExcelCellMap`; set workbook calculation mode to automatic and full calculation on load.

- [ ] **Step 4: Implement Excel COM recalculation and cached-value reading**

```python
def recalculate_with_excel(path: Path) -> None:
    pythoncom.CoInitialize()
    excel = win32com.client.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    try:
        workbook = excel.Workbooks.Open(str(path.resolve()), UpdateLinks=0, ReadOnly=False)
        excel.CalculateFullRebuild()
        workbook.Save()
        workbook.Close(SaveChanges=True)
    finally:
        excel.Quit()
        pythoncom.CoUninitialize()
```

Reopen via `load_workbook(path, data_only=True)` and fail explicitly on `None`, formula-error strings, or missing metrics.

- [ ] **Step 5: Run workbook tests and an Excel integration test**

Run: `app/.venv/Scripts/python.exe -m pytest app/tests/test_excel_builder.py -v`

Expected: PASS; the integration marker confirms formulas receive non-empty cached values after COM recalculation.

- [ ] **Step 6: Commit Excel implementation**

```powershell
git add app/src/excel_builder.py app/tests/test_excel_builder.py
git commit -m "feat: build and recalculate Excel ground truth"
```

### Task 5: Logging, Harness Log, and Word report

**Files:**
- Create: `app/src/logger_config.py`
- Create: `app/src/harness_log.py`
- Create: `app/src/report_builder.py`
- Create: `app/tests/test_reporting.py`

**Interfaces:**
- Produces: `configure_logging(path)`, `write_harness_log(entries, path)`, `build_word_report(context, path)`.
- Consumes: only finalized pipeline context and chart paths.

- [ ] **Step 1: Write failing artifact-content tests**

```python
def test_harness_contains_real_input_conflicts(report_context, tmp_path):
    path = write_harness_log(report_context.harness_entries, tmp_path / "Harness_Log.xlsx")
    sheet = load_workbook(path, data_only=True).active
    values = " ".join(str(cell.value) for row in sheet.iter_rows() for cell in row if cell.value)
    assert "WACC" in values and "10%" in values and "12%" in values

def test_word_report_contains_required_sections_and_images(report_context, tmp_path):
    path = build_word_report(report_context, tmp_path / "Итоговый_отчет_ФИП.docx")
    document = Document(path)
    headings = {p.text for p in document.paragraphs if p.style.name.startswith("Heading")}
    assert {"Исходные данные", "Монте-Карло", "Стресс-тест", "Итоговый вывод"} <= headings
    assert len(document.inline_shapes) == 2
```

- [ ] **Step 2: Run reporting tests and verify RED**

Run: `app/.venv/Scripts/python.exe -m pytest app/tests/test_reporting.py -v`

Expected: import failure because reporting modules do not exist.

- [ ] **Step 3: Implement runtime and Harness logs**

Configure UTF-8 file logging with format `%(asctime)s | %(levelname)s | %(name)s | %(message)s`. Build the Harness workbook with the exact columns `№`, `Этап`, `Запрос к ИИ / задача`, `Сгенерированный или изменённый фрагмент кода`, `Обнаруженная ошибка / галлюцинация`, `Причина`, `Как исправлено`, `Результат повторной проверки`; include only observed issues and documented methodology decisions.

- [ ] **Step 4: Implement compact Russian Word report**

Use A4, 2 cm margins, Aptos/Times New Roman 10–11 pt, Russian headings, compact tables, consistent number formats, and the two generated charts. Generate every number from the finalized context. The conclusion branches on NPV, risk probability, and stress NPV instead of embedding manual values.

- [ ] **Step 5: Run reporting tests and verify GREEN**

Run: `app/.venv/Scripts/python.exe -m pytest app/tests/test_reporting.py -v`

Expected: PASS; XLSX and DOCX reopen successfully.

- [ ] **Step 6: Commit reporting**

```powershell
git add app/src/logger_config.py app/src/harness_log.py app/src/report_builder.py app/tests/test_reporting.py
git commit -m "feat: generate audit logs and Word report"
```

### Task 6: Orchestrator, CLI, README, and end-to-end run

**Files:**
- Create: `app/src/pipeline.py`
- Create: `app/main.py`
- Create: `app/README.md`
- Create: `app/tests/test_pipeline.py`

**Interfaces:**
- Produces: `run_pipeline(config: PipelineConfig) -> PipelineResult` and CLI exit code `0` only on complete success.
- Consumes: every prior module without duplicating its business logic.

- [ ] **Step 1: Write failing orchestration tests**

```python
def test_pipeline_creates_every_required_artifact(pipeline_config):
    result = run_pipeline(pipeline_config)
    assert result.success
    assert result.max_relative_deviation_percent < 0.01
    for path in result.artifacts:
        assert path.exists() and path.stat().st_size > 0
    assert result.word_report.name == "Итоговый_отчет_ФИП.docx"
```

- [ ] **Step 2: Run pipeline test and verify RED**

Run: `app/.venv/Scripts/python.exe -m pytest app/tests/test_pipeline.py -v`

Expected: import failure because `pipeline` does not exist.

- [ ] **Step 3: Implement ordered fail-fast orchestration**

```python
def run_pipeline(config: PipelineConfig) -> PipelineResult:
    logger = configure_logging(config.log_path)
    data = load_project_data(config.csv_path)
    base = FinancialModel(data).calculate()
    boundary = run_boundary_tests(data)
    monte_carlo = run_monte_carlo(data, iterations=1000, seed=20260916)
    stress = run_stress_test(data)
    charts = save_monte_carlo_charts(monte_carlo, config.output_dir)
    initial_context = PipelineContext(
        data=data,
        base=base,
        boundary_tests=boundary,
        monte_carlo=monte_carlo,
        stress=stress,
        comparison=None,
    )
    cell_map = build_workbook(initial_context, config.excel_path)
    recalculate_with_excel(config.excel_path)
    excel_metrics = read_excel_metrics(config.excel_path, cell_map)
    comparison = compare_results(base, excel_metrics)
    require_successful_gates(boundary, comparison)
    write_final_workbook_sections(config.excel_path, comparison, boundary, monte_carlo, stress)
    recalculate_with_excel(config.excel_path)
    harness_entries = build_harness_entries(data.conflicts, comparison, boundary)
    harness = write_harness_log(harness_entries, config.harness_path)
    report_context = ReportContext(
        data=data,
        base=base,
        boundary_tests=boundary,
        monte_carlo=monte_carlo,
        stress=stress,
        comparison=comparison,
        charts=charts,
        harness_entries=harness_entries,
    )
    report = build_word_report(report_context, config.report_path)
    artifacts = (config.excel_path, harness, *charts, report, config.log_path)
    return PipelineResult(
        success=True,
        max_relative_deviation_percent=comparison.max_relative_deviation_percent,
        artifacts=artifacts,
        word_report=report,
    )
```

Ensure later workbook writes preserve formulas and trigger a final Excel save. On exceptions, log stack trace, return nonzero from CLI, and never claim completion.

- [ ] **Step 4: Document setup and one-command execution**

README lists interpreter creation, dependency installation, test command, pipeline command, expected artifacts, Excel requirement, formulas/assumptions, and the two PDF/CSV conflicts.

- [ ] **Step 5: Run the complete automated suite**

Run: `app/.venv/Scripts/python.exe -m pytest app/tests -v`

Expected: all tests PASS with no warnings attributable to application code.

- [ ] **Step 6: Run the real pipeline**

Run: `app/.venv/Scripts/python.exe app/main.py`

Expected: exit code `0`; Excel comparison is below `0.01%`; all required artifacts exist.

- [ ] **Step 7: Inspect generated files programmatically**

Run: `app/.venv/Scripts/python.exe -m pytest app/tests/test_pipeline.py -v`

Run: open XLSX/DOCX as ZIP containers and verify they contain required Office XML parts; load workbook with formulas and cached values; load DOCX with python-docx; inspect both PNG dimensions.

- [ ] **Step 8: Commit completed application**

```powershell
git add app
git commit -m "feat: deliver reproducible DCF CAPEX pipeline"
```
