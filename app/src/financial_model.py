"""Deterministic DCF and Lang-factor calculations."""

from __future__ import annotations

import math

from .models import CapitalEstimate, DCFRow, FinancialResult, MetricOutcome, ProjectData


class FinancialModel:
    """Calculate financial results from validated project inputs."""

    def __init__(self, data: ProjectData):
        self.data = data

    def calculate_lang_capex(self) -> CapitalEstimate:
        """Calculate equipment total, FCI, and TCI by the Lang method."""

        equipment_cost = sum(item.cost for item in self.data.equipment)
        fci = self.data.lang_factor * equipment_cost
        tci = fci / (1.0 - self.data.working_capital_share)
        return CapitalEstimate(equipment_cost=equipment_cost, fci=fci, tci=tci)

    def calculate(self) -> FinancialResult:
        """Calculate the base DCF model without invented future investments."""

        capital = self.calculate_lang_capex()
        depreciation = capital.fci / self.data.project_lifetime_years
        cumulative = -capital.tci
        rows: list[DCFRow] = []

        for year in self.data.years:
            revenue = self.data.revenue[year]
            opex = self.data.opex[year]
            ebit = revenue - opex - depreciation
            nopat = ebit * (1.0 - self.data.tax_rate)
            capex = 0.0
            delta_nwc = 0.0
            fcf = nopat + depreciation - capex - delta_nwc
            discount_factor = (1.0 + self.data.wacc) ** year
            discounted_fcf = fcf / discount_factor
            cumulative += discounted_fcf
            rows.append(
                DCFRow(
                    year=year,
                    revenue=revenue,
                    opex=opex,
                    depreciation=depreciation,
                    ebit=ebit,
                    nopat=nopat,
                    capex=capex,
                    delta_nwc=delta_nwc,
                    fcf=fcf,
                    discount_factor=discount_factor,
                    discounted_fcf=discounted_fcf,
                    cumulative_discounted_cash_flow=cumulative,
                )
            )

        cash_flows = (-capital.tci, *(row.fcf for row in rows))
        pv_future = sum(row.discounted_fcf for row in rows)
        npv = -capital.tci + pv_future
        irr = _calculate_irr(cash_flows)
        pi = (
            MetricOutcome(None, "НЕ ОПРЕДЕЛЕН: первоначальные инвестиции равны нулю")
            if math.isclose(capital.tci, 0.0, abs_tol=1e-12)
            else MetricOutcome(pv_future / capital.tci, "OK")
        )
        dpbp = _calculate_dpbp(capital.tci, rows)
        return FinancialResult(
            capital=capital,
            rows=tuple(rows),
            cash_flows=tuple(cash_flows),
            npv=npv,
            irr=irr,
            pi=pi,
            dpbp=dpbp,
        )


def _calculate_irr(cash_flows: tuple[float, ...]) -> MetricOutcome:
    nonzero_signs = [1 if value > 0 else -1 for value in cash_flows if not math.isclose(value, 0.0, abs_tol=1e-12)]
    sign_changes = sum(left != right for left, right in zip(nonzero_signs, nonzero_signs[1:]))
    if sign_changes == 0:
        return MetricOutcome(None, "НЕ ОПРЕДЕЛЕН: в денежном потоке отсутствует изменение знака")
    if sign_changes > 1:
        return MetricOutcome(None, "НЕ ОПРЕДЕЛЕН ОДНОЗНАЧНО: денежный поток имеет несколько изменений знака")

    rates = [-0.9999, -0.99, -0.95, -0.9, -0.75, -0.5, -0.25, 0.0]
    rates.extend(10.0 ** (index / 20.0) - 1.0 for index in range(1, 121))
    previous_rate = rates[0]
    previous_npv = _npv_at_rate(cash_flows, previous_rate)
    bracket: tuple[float, float] | None = None
    for rate in rates[1:]:
        current_npv = _npv_at_rate(cash_flows, rate)
        if math.isclose(current_npv, 0.0, abs_tol=1e-12):
            return MetricOutcome(rate, "OK")
        if previous_npv * current_npv < 0:
            bracket = (previous_rate, rate)
            break
        previous_rate, previous_npv = rate, current_npv

    if bracket is None:
        return MetricOutcome(None, "НЕ ОПРЕДЕЛЕН: численный корень IRR не найден")

    lower, upper = bracket
    lower_value = _npv_at_rate(cash_flows, lower)
    for _ in range(200):
        midpoint = (lower + upper) / 2.0
        midpoint_value = _npv_at_rate(cash_flows, midpoint)
        if abs(midpoint_value) < 1e-12 or upper - lower < 1e-12:
            return MetricOutcome(midpoint, "OK")
        if lower_value * midpoint_value <= 0:
            upper = midpoint
        else:
            lower = midpoint
            lower_value = midpoint_value
    return MetricOutcome((lower + upper) / 2.0, "OK")


def _npv_at_rate(cash_flows: tuple[float, ...], rate: float) -> float:
    return sum(value / (1.0 + rate) ** year for year, value in enumerate(cash_flows))


def _calculate_dpbp(initial_investment: float, rows: list[DCFRow]) -> MetricOutcome:
    if math.isclose(initial_investment, 0.0, abs_tol=1e-12):
        return MetricOutcome(0.0, "OK")

    previous_cumulative = -initial_investment
    for row in rows:
        current_cumulative = row.cumulative_discounted_cash_flow
        if current_cumulative >= 0 and row.discounted_fcf > 0:
            fraction = -previous_cumulative / row.discounted_fcf
            return MetricOutcome((row.year - 1) + fraction, "OK: линейная интерполяция внутри года")
        previous_cumulative = current_cumulative
    return MetricOutcome(None, "Не окупается в пределах горизонта модели")
