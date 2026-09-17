"""Tests for mandatory boundary cases and the stress scenario."""

from __future__ import annotations

import pytest

from src.scenarios import run_boundary_tests, run_stress_test


def test_boundary_suite_passes_all_three_required_cases(real_project_data):
    """Dropping any mandatory test case or its assertion must fail."""

    results = run_boundary_tests(real_project_data)

    assert {item.code for item in results} == {"CAPEX_ZERO", "WACC_ZERO", "NEGATIVE_ECONOMY"}
    assert all(item.passed for item in results)


def test_wacc_zero_equals_undiscounted_cash_flow(real_project_data):
    """Leaving discounting active at WACC=0 must fail this test."""

    results = run_boundary_tests(real_project_data)
    case = next(item for item in results if item.code == "WACC_ZERO")

    assert case.passed
    assert "совпадает" in case.actual_result


def test_stress_doubles_capex_and_reduces_revenue(real_project_data):
    """Applying stress percentages to the wrong bases must fail."""

    result = run_stress_test(real_project_data)

    assert result.stress.capital.fci == pytest.approx(result.base.capital.fci * 2.0)
    assert result.stress.capital.tci == pytest.approx(result.base.capital.tci * 2.0)
    assert result.stress.rows[3].revenue == pytest.approx(result.base.rows[3].revenue * 0.7)
    assert {item.name for item in result.comparisons} >= {"NPV", "IRR", "PI", "DPBP", "FCI", "TCI"}

