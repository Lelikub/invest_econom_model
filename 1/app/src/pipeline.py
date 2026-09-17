"""Fail-fast orchestration for the complete DCF/CAPEX workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .charts import save_monte_carlo_charts
from .comparator import compare_metrics
from .data_loader import load_project_data
from .excel_builder import (
    build_workbook,
    read_excel_metrics,
    recalculate_with_excel,
    write_comparison_sheet,
    write_comparison_workbook,
)
from .financial_model import FinancialModel
from .harness_log import build_harness_entries, write_harness_log
from .logger_config import configure_logging
from .models import PipelineResult, ReportContext
from .monte_carlo import run_monte_carlo
from .report_builder import build_word_report
from .scenarios import run_boundary_tests, run_stress_test


class PipelineError(RuntimeError):
    """Raised when a blocking validation or comparison gate fails."""


@dataclass(frozen=True)
class PipelineConfig:
    """Input and output locations for one reproducible run."""

    csv_path: Path
    output_dir: Path
    log_path: Path

    @classmethod
    def defaults(cls, assignment_root: Path) -> "PipelineConfig":
        """Build default paths relative to the assignment, never absolute literals."""

        root = Path(assignment_root)
        return cls(
            csv_path=root / "data" / "data.csv",
            output_dir=root / "app" / "output",
            log_path=root / "app" / "logs" / "execution.log",
        )


def run_pipeline(config: PipelineConfig) -> PipelineResult:
    """Run every calculation, verification, and artifact stage in one call."""

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = configure_logging(config.log_path)
    excel_path = output_dir / "DCF_Ground_Truth.xlsx"
    harness_path = output_dir / "Harness_Log.xlsx"
    comparison_path = output_dir / "Сравнение_результатов.xlsx"
    report_path = output_dir / "Итоговый_отчет_ФИП.docx"

    try:
        logger.info("Запуск pipeline; этап: чтение CSV")
        data = load_project_data(config.csv_path)
        logger.info("CSV прочитан: оборудование=%d, годы=%d", len(data.equipment), data.project_lifetime_years)
        for conflict in data.conflicts:
            logger.warning(
                "Конфликт исходных данных %s: PDF=%s, CSV=%s; используется CSV",
                conflict.field,
                conflict.pdf_value,
                conflict.csv_value,
            )

        logger.info("Этап: финансовая модель и CAPEX методом Ленга")
        base = FinancialModel(data).calculate()
        logger.info(
            "Базовые результаты: FCI=%.6f, TCI=%.6f, NPV=%.6f",
            base.capital.fci,
            base.capital.tci,
            base.npv,
        )

        logger.info("Этап: граничные тесты")
        boundary_tests = run_boundary_tests(data)
        failed_tests = [item.code for item in boundary_tests if not item.passed]
        if failed_tests:
            raise PipelineError(f"Не пройдены граничные тесты: {', '.join(failed_tests)}")
        logger.info("Граничные тесты: PASS (%d/%d)", len(boundary_tests), len(boundary_tests))

        logger.info("Этап: Монте-Карло, 1000 итераций")
        monte_carlo = run_monte_carlo(data, iterations=1000, seed=20260916)
        logger.info(
            "Монте-Карло завершено: среднее NPV=%.6f, P(NPV<0)=%.6f",
            monte_carlo.mean,
            monte_carlo.probability_negative,
        )
        charts = save_monte_carlo_charts(monte_carlo, output_dir)
        logger.info("Графики Монте-Карло созданы: %s, %s", charts[0].name, charts[1].name)

        logger.info("Этап: стресс-тест CAPEX +100%%, Revenue -30%%")
        stress = run_stress_test(data)
        logger.info("стресс-тест завершен: NPV=%.6f", stress.stress.npv)

        logger.info("Этап: создание Excel Ground Truth с формулами")
        cell_map = build_workbook(data, base, boundary_tests, monte_carlo, stress, excel_path)
        logger.info("Excel создан; запуск фактического пересчета")
        recalculate_with_excel(excel_path)
        excel_metrics = read_excel_metrics(excel_path, cell_map)
        comparison = compare_metrics(base.numeric_metrics(), excel_metrics, tolerance_percent=0.01)
        logger.info(
            "Сравнение Python/Excel: max abs=%.12f, max rel=%.12f%%",
            comparison.max_absolute_difference,
            comparison.max_relative_deviation_percent,
        )
        if not comparison.all_match or comparison.max_relative_deviation_percent >= 0.01:
            mismatches = [item.name for item in comparison.items if item.status != "СОВПАДАЕТ"]
            raise PipelineError(f"Python и Excel не совпали в допуске <0,01%: {', '.join(mismatches)}")

        write_comparison_sheet(excel_path, comparison)
        recalculate_with_excel(excel_path)
        final_excel_metrics = read_excel_metrics(excel_path, cell_map)
        comparison = compare_metrics(base.numeric_metrics(), final_excel_metrics, tolerance_percent=0.01)
        if not comparison.all_match:
            raise PipelineError("Финальная запись Excel нарушила ранее подтвержденную сверку")
        standalone_comparison = write_comparison_workbook(comparison, comparison_path)
        logger.info("Excel Ground Truth и отдельная книга сравнения сохранены")

        harness_entries = build_harness_entries(data, comparison, boundary_tests)
        harness = write_harness_log(harness_entries, harness_path)
        logger.info("Harness Log создан: %d записей", len(harness_entries))

        logger.info("Этап: Word — формирование итогового отчета")
        report_context = ReportContext(
            data=data,
            base=base,
            boundary_tests=boundary_tests,
            monte_carlo=monte_carlo,
            stress=stress,
            comparison=comparison,
            charts=charts,
            harness_entries=harness_entries,
        )
        report = build_word_report(report_context, report_path)
        logger.info("Word-отчет создан: %s", report)
        logger.info("Pipeline успешно завершен")
        for handler in logger.handlers:
            handler.flush()

        artifacts = (
            excel_path,
            harness,
            standalone_comparison,
            charts[0],
            charts[1],
            report,
            Path(config.log_path),
        )
        return PipelineResult(
            success=True,
            data=data,
            base=base,
            boundary_tests=boundary_tests,
            monte_carlo=monte_carlo,
            stress=stress,
            comparison=comparison,
            artifacts=artifacts,
            word_report=report,
        )
    except Exception:
        logger.exception("Pipeline завершен с ошибкой")
        for handler in logger.handlers:
            handler.flush()
        raise

