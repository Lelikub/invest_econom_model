"""Behavioral tests for strict CSV loading."""

from __future__ import annotations

import csv

import pytest

from conftest import write_csv
from src.data_loader import DataValidationError, load_project_data


def test_loads_real_csv_and_reports_pdf_conflicts(real_csv_path):
    """A change that ignores PDF/CSV differences must fail this test."""

    data = load_project_data(real_csv_path)

    assert data.project_lifetime_years == 10
    assert data.revenue[1] == 0.0
    assert data.revenue[3] == 45.0
    assert {(item.field, item.pdf_value, item.csv_value) for item in data.conflicts} == {
        ("wacc", 0.10, 0.12),
        ("working_capital_share", 0.12, 0.15),
    }


def test_rejects_duplicate_profile_year(tmp_path, valid_rows):
    """A change that silently overwrites duplicate parameters must fail."""

    path = write_csv(tmp_path, [*valid_rows, ("Revenue_Profile", "Year_1", 99.0)])

    with pytest.raises(DataValidationError, match="дублируется"):
        load_project_data(path)


def test_rejects_missing_required_column(tmp_path):
    """A change that accepts malformed CSV schemas must fail."""

    path = tmp_path / "data.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("Category", "Item"))
        writer.writerow(("Parameter", "wacc"))

    with pytest.raises(DataValidationError, match="обязательные столбцы"):
        load_project_data(path)


@pytest.mark.parametrize(
    ("parameter", "value", "message"),
    [
        ("working_capital_share", 1.0, "working_capital_share"),
        ("wacc", -0.01, "wacc"),
        ("tax_rate", -0.01, "tax_rate"),
        ("lang_factor", 0.0, "lang_factor"),
        ("project_lifetime_years", 2.5, "project_lifetime_years"),
    ],
)
def test_rejects_invalid_parameter_ranges(tmp_path, valid_rows, parameter, value, message):
    """A change that drops financial range checks must fail."""

    rows = [(category, item, value if item == parameter else original) for category, item, original in valid_rows]
    path = write_csv(tmp_path, rows)

    with pytest.raises(DataValidationError, match=message):
        load_project_data(path)


def test_rejects_incomplete_revenue_horizon(tmp_path, valid_rows):
    """A change that permits profile gaps must fail this test."""

    rows = [row for row in valid_rows if not (row[0] == "Revenue_Profile" and row[1] == "Year_2")]
    path = write_csv(tmp_path, rows)

    with pytest.raises(DataValidationError, match="Revenue_Profile"):
        load_project_data(path)

