"""Tests for numerical Python-to-Excel comparison."""

from __future__ import annotations

import pytest

from app.src.comparator import compare_metrics


def test_comparison_uses_strict_relative_tolerance():
    """Using a tolerance of 0.01 as a fraction instead of percent must fail."""

    result = compare_metrics({"NPV": 100.009}, {"NPV": 100.0}, tolerance_percent=0.01)

    assert result.items[0].relative_difference_percent == pytest.approx(0.009)
    assert result.items[0].status == "СОВПАДАЕТ"
    assert result.all_match


def test_comparison_rejects_value_at_tolerance_boundary():
    """Treating the strict '< 0.01%' requirement as inclusive must fail."""

    result = compare_metrics({"NPV": 100.01}, {"NPV": 100.0}, tolerance_percent=0.01)

    assert result.items[0].status == "НЕ СОВПАДАЕТ"
    assert not result.all_match


def test_comparison_handles_zero_excel_value_without_division():
    """Dividing by a zero Excel value must fail this behavior."""

    result = compare_metrics({"FCF_1": 0.0}, {"FCF_1": 0.0}, tolerance_percent=0.01)

    item = result.items[0]
    assert item.absolute_difference == 0.0
    assert item.relative_difference_percent == 0.0
    assert item.status == "СОВПАДАЕТ"


def test_comparison_requires_matching_undefined_statuses():
    """Treating one undefined metric as equal to a number must fail."""

    result = compare_metrics({"PI": None}, {"PI": 1.0}, tolerance_percent=0.01)

    assert result.items[0].status == "НЕ СОВПАДАЕТ"
    assert not result.all_match
