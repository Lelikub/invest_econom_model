"""Boundary and stress scenarios for the DCF model."""

from __future__ import annotations

import math
from dataclasses import replace

from .financial_model import FinancialModel
from .models import (
    EquipmentItem,
    ProjectData,
    ScenarioMetricComparison,
    ScenarioTestResult,
    StressResult,
)


def scaled_project(
    data: ProjectData,
    *,
    equipment_factor: float = 1.0,
    revenue_factor: float = 1.0,
    wacc: float | None = None,
) -> ProjectData:
    """Return a transformed scenario without mutating the source data."""

    return replace(
        data,
        equipment=tuple(EquipmentItem(item.name, item.cost * equipment_factor) for item in data.equipment),
        revenue={year: value * revenue_factor for year, value in data.revenue.items()},
        wacc=data.wacc if wacc is None else wacc,
    )


def run_boundary_tests(data: ProjectData) -> tuple[ScenarioTestResult, ...]:
    """Execute the three boundary cases required by the assignment."""

    capex_zero = FinancialModel(scaled_project(data, equipment_factor=0.0)).calculate()
    capex_passed = (
        math.isfinite(capex_zero.npv)
        and capex_zero.pi.value is None
        and capex_zero.capital.tci == 0.0
        and capex_zero.dpbp.value == 0.0
    )
    capex_case = ScenarioTestResult(
        code="CAPEX_ZERO",
        name="CAPEX = 0",
        inputs="Стоимость всего оборудования принята равной 0",
        expected_property="Нет деления на ноль; PI имеет явный неопределенный статус",
        actual_result=f"NPV={capex_zero.npv:.6f}; PI={capex_zero.pi.status}; DPBP={capex_zero.dpbp.value}",
        passed=capex_passed,
        comment="Проверена безопасная обработка нулевых первоначальных инвестиций",
    )

    wacc_zero = FinancialModel(scaled_project(data, wacc=0.0)).calculate()
    undiscounted = sum(wacc_zero.cash_flows)
    wacc_passed = math.isclose(wacc_zero.npv, undiscounted, rel_tol=0.0, abs_tol=1e-9) and all(
        math.isclose(row.discount_factor, 1.0, rel_tol=0.0, abs_tol=1e-12) for row in wacc_zero.rows
    )
    wacc_case = ScenarioTestResult(
        code="WACC_ZERO",
        name="WACC = 0%",
        inputs="Ставка дисконтирования принята равной 0%",
        expected_property="NPV совпадает с недисконтированной суммой денежных потоков",
        actual_result=(
            f"NPV={wacc_zero.npv:.6f}; сумма потоков={undiscounted:.6f}; "
            f"{'совпадает' if wacc_passed else 'не совпадает'}"
        ),
        passed=wacc_passed,
        comment="Все коэффициенты дисконтирования должны быть равны 1",
    )

    negative_data = replace(
        data,
        revenue={year: -(abs(value) + 1.0) for year, value in data.revenue.items()},
    )
    negative = FinancialModel(negative_data).calculate()
    negative_passed = all(
        row.revenue < 0
        and row.opex > row.revenue
        and row.ebit < 0
        and math.isclose(row.nopat, row.ebit * (1.0 - data.tax_rate), abs_tol=1e-9)
        and math.isclose(row.fcf, row.nopat + row.depreciation, abs_tol=1e-9)
        for row in negative.rows
    )
    negative_case = ScenarioTestResult(
        code="NEGATIVE_ECONOMY",
        name="Отрицательная экономика",
        inputs="Revenue < 0 и OPEX > Revenue во всех годах",
        expected_property="EBIT отрицателен; NOPAT и FCF следуют формулам задания с налоговым щитом",
        actual_result=(
            f"EBIT год 1={negative.rows[0].ebit:.6f}; NOPAT год 1={negative.rows[0].nopat:.6f}; "
            f"FCF год 1={negative.rows[0].fcf:.6f}"
        ),
        passed=negative_passed,
        comment="Перенос налоговых убытков не моделируется; применяется заданная формула NOPAT",
    )
    return capex_case, wacc_case, negative_case


def run_stress_test(data: ProjectData) -> StressResult:
    """Run the prescribed CAPEX +100% and Revenue -30% scenario."""

    base = FinancialModel(data).calculate()
    stress = FinancialModel(scaled_project(data, equipment_factor=2.0, revenue_factor=0.7)).calculate()
    pairs = {
        "NPV": (base.npv, stress.npv),
        "IRR": (base.irr.value, stress.irr.value),
        "PI": (base.pi.value, stress.pi.value),
        "DPBP": (base.dpbp.value, stress.dpbp.value),
        "FCI": (base.capital.fci, stress.capital.fci),
        "TCI": (base.capital.tci, stress.capital.tci),
    }
    pairs.update(
        {f"FCF_{row.year}": (row.fcf, stress.rows[row.year - 1].fcf) for row in base.rows}
    )
    comparisons = tuple(_scenario_comparison(name, values[0], values[1]) for name, values in pairs.items())
    return StressResult(base=base, stress=stress, comparisons=comparisons)


def _scenario_comparison(
    name: str, base_value: float | None, stress_value: float | None
) -> ScenarioMetricComparison:
    if base_value is None or stress_value is None:
        return ScenarioMetricComparison(name, base_value, stress_value, None, None)
    absolute = stress_value - base_value
    relative = None if math.isclose(base_value, 0.0, abs_tol=1e-12) else absolute / abs(base_value) * 100.0
    return ScenarioMetricComparison(name, base_value, stress_value, absolute, relative)

