"""Command-line entry point for the complete DCF/CAPEX pipeline."""

from __future__ import annotations

import argparse
import site
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
ASSIGNMENT_ROOT = APP_DIR.parent
LOCAL_PACKAGES = APP_DIR / ".python-packages"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
if LOCAL_PACKAGES.is_dir():
    site.addsitedir(str(LOCAL_PACKAGES))

from src.pipeline import PipelineConfig, run_pipeline


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse optional path overrides while preserving one-command defaults."""

    defaults = PipelineConfig.defaults(ASSIGNMENT_ROOT)
    parser = argparse.ArgumentParser(description="DCF-модель и факторная оценка CAPEX")
    parser.add_argument("--csv", type=Path, default=defaults.csv_path, help="Путь к исходному data.csv")
    parser.add_argument("--output-dir", type=Path, default=defaults.output_dir, help="Каталог итоговых файлов")
    parser.add_argument("--log-path", type=Path, default=defaults.log_path, help="Путь к execution.log")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the pipeline and print a compact machine-calculated summary."""

    args = parse_args(argv)
    try:
        result = run_pipeline(PipelineConfig(args.csv, args.output_dir, args.log_path))
    except Exception as exc:
        print(f"ОШИБКА: {exc}", file=sys.stderr)
        return 1
    print("Pipeline успешно завершен.")
    print(f"FCI: {result.base.capital.fci:.6f}")
    print(f"TCI: {result.base.capital.tci:.6f}")
    print(f"NPV: {result.base.npv:.6f}")
    print(f"IRR: {result.base.irr.value if result.base.irr.value is not None else result.base.irr.status}")
    print(f"PI: {result.base.pi.value if result.base.pi.value is not None else result.base.pi.status}")
    print(f"DPBP: {result.base.dpbp.value if result.base.dpbp.value is not None else result.base.dpbp.status}")
    print(f"Максимальное отклонение Python/Excel: {result.max_relative_deviation_percent:.12f}%")
    print(f"P(NPV < 0): {result.monte_carlo.probability_negative:.6f}")
    print(f"NPV стресс-сценария: {result.stress.stress.npv:.6f}")
    print("Файлы:")
    for artifact in result.artifacts:
        print(f"- {artifact.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

