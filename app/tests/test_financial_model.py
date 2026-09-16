"""Tests for deterministic DCF calculations and edge statuses."""

from __future__ import annotations

import pytest

from app.src.financial_model import FinancialModel


def test_lang_capex_uses_equipment_fci_and_wc_tci(real_project_data):
    """Using TCI as the Lang base or omitting WC must fail this test."""

    estimate = FinancialModel(real_project_data).calculate_lang_capex()

    assert estimate.equipment_cost == pytest.approx(230.0)
    assert estimate.fci == pytest.approx(834.9)
    assert estimate.tci == pytest.approx(982.2352941176471)


def test_year_one_fcf_restores_depreciation(real_project_data):
    """Forgetting the D&A add-back must fail against hand-derived values."""

    result = FinancialModel(real_project_data).calculate()
    first = result.rows[0]

    assert first.depreciation == pytest.approx(83.49)
    assert first.ebit == pytest.approx(-138.49)
    assert first.nopat == pytest.approx(-110.792)
    assert first.fcf == pytest.approx(-27.302)


def test_dcf_does_not_repeat_initial_capex(real_project_data):
    """Subtracting the year-zero investment again must fail this test."""

    result = FinancialModel(real_project_data).calculate()

    assert result.cash_flows[0] == pytest.approx(-result.capital.tci)
    assert all(row.capex == 0.0 and row.delta_nwc == 0.0 for row in result.rows)
    assert all(row.depreciation == pytest.approx(result.capital.fci / 10) for row in result.rows)


def test_zero_capex_returns_undefined_pi(project_data_factory):
    """Dividing PI by zero instead of returning an explicit status must fail."""

    result = FinancialModel(project_data_factory(equipment_costs=(0.0,))).calculate()

    assert result.pi.value is None
    assert result.pi.status == "НЕ ОПРЕДЕЛЕН: первоначальные инвестиции равны нулю"


def test_irr_reports_absence_without_cash_flow_sign_change(project_data_factory):
    """Inventing an IRR for same-sign cash flows must fail this test."""

    data = project_data_factory(
        equipment_costs=(0.0,),
        revenue={1: 40.0, 2: 40.0},
        opex={1: 0.0, 2: 0.0},
    )
    result = FinancialModel(data).calculate()

    assert result.irr.value is None
    assert "изменение знака" in result.irr.status


def test_dpbp_reports_non_repayment(project_data_factory):
    """Returning a fabricated payback year for a losing project must fail."""

    data = project_data_factory(
        equipment_costs=(100.0,),
        revenue={1: 0.0, 2: 0.0},
        opex={1: 20.0, 2: 20.0},
    )
    result = FinancialModel(data).calculate()

    assert result.dpbp.value is None
    assert result.dpbp.status == "Не окупается в пределах горизонта модели"

