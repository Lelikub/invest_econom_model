"""Numerical comparison of Python and recalculated Excel results."""

from __future__ import annotations

import math
from collections.abc import Mapping

from .models import ComparisonResult, MetricComparison


def compare_metrics(
    python_metrics: Mapping[str, float | None],
    excel_metrics: Mapping[str, float | None],
    tolerance_percent: float = 0.01,
) -> ComparisonResult:
    """Compare identically named metrics using a strict percentage tolerance."""

    if set(python_metrics) != set(excel_metrics):
        missing_in_excel = sorted(set(python_metrics) - set(excel_metrics))
        missing_in_python = sorted(set(excel_metrics) - set(python_metrics))
        raise ValueError(
            f"Наборы метрик различаются: нет в Excel={missing_in_excel}, нет в Python={missing_in_python}"
        )

    items = tuple(
        _compare_value(name, python_metrics[name], excel_metrics[name], tolerance_percent)
        for name in python_metrics
    )
    absolute_values = [item.absolute_difference for item in items if item.absolute_difference is not None]
    relative_values = [
        item.relative_difference_percent for item in items if item.relative_difference_percent is not None
    ]
    return ComparisonResult(
        items=items,
        all_match=all(item.status == "СОВПАДАЕТ" for item in items),
        max_absolute_difference=max(absolute_values, default=0.0),
        max_relative_deviation_percent=max(relative_values, default=0.0),
    )


def _compare_value(
    name: str,
    python_value: float | None,
    excel_value: float | None,
    tolerance_percent: float,
) -> MetricComparison:
    if python_value is None or excel_value is None:
        matches = python_value is None and excel_value is None
        return MetricComparison(
            name=name,
            python_value=python_value,
            excel_value=excel_value,
            absolute_difference=0.0 if matches else None,
            relative_difference_percent=0.0 if matches else None,
            status="СОВПАДАЕТ" if matches else "НЕ СОВПАДАЕТ",
        )

    python_number = float(python_value)
    excel_number = float(excel_value)
    if not math.isfinite(python_number) or not math.isfinite(excel_number):
        matches = python_number == excel_number
        return MetricComparison(
            name, python_number, excel_number, None, None, "СОВПАДАЕТ" if matches else "НЕ СОВПАДАЕТ"
        )

    absolute = abs(python_number - excel_number)
    if math.isclose(excel_number, 0.0, abs_tol=1e-15):
        relative = 0.0 if math.isclose(absolute, 0.0, abs_tol=1e-9) else None
        matches = relative == 0.0
    else:
        relative = absolute / abs(excel_number) * 100.0
        matches = relative < tolerance_percent
    return MetricComparison(
        name=name,
        python_value=python_number,
        excel_value=excel_number,
        absolute_difference=absolute,
        relative_difference_percent=relative,
        status="СОВПАДАЕТ" if matches else "НЕ СОВПАДАЕТ",
    )

