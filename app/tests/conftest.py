"""Shared pytest fixtures for the DCF/CAPEX application."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

import pytest

from app.src.data_loader import load_project_data
from app.src.models import EquipmentItem, ProjectData


@pytest.fixture
def repository_root() -> Path:
    """Return the repository root for the active worktree."""

    return Path(__file__).resolve().parents[2]


@pytest.fixture
def real_csv_path(repository_root: Path) -> Path:
    """Return the immutable source CSV supplied with the assignment."""

    return repository_root / "1" / "data" / "data.csv"


@pytest.fixture
def real_project_data(real_csv_path: Path) -> ProjectData:
    """Load the real assignment project once per test."""

    return load_project_data(real_csv_path)


@pytest.fixture
def project_data_factory():
    """Build compact deterministic project inputs for finance tests."""

    def factory(
        *,
        equipment_costs: tuple[float, ...] = (10.0,),
        revenue: dict[int, float] | None = None,
        opex: dict[int, float] | None = None,
        wacc: float = 0.10,
        lifetime: int = 2,
    ) -> ProjectData:
        return ProjectData(
            equipment=tuple(EquipmentItem(f"Оборудование {index}", cost) for index, cost in enumerate(equipment_costs, 1)),
            lang_factor=3.0,
            working_capital_share=0.20,
            wacc=wacc,
            tax_rate=0.20,
            project_lifetime_years=lifetime,
            revenue=revenue or {year: 30.0 for year in range(1, lifetime + 1)},
            opex=opex or {year: 5.0 for year in range(1, lifetime + 1)},
        )

    return factory


def write_csv(directory: Path, rows: Iterable[tuple[str, str, object]]) -> Path:
    """Write a controlled CSV fixture and return its path."""

    path = directory / "data.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("Category", "Item", "Value"))
        writer.writerows(rows)
    return path


@pytest.fixture
def valid_rows() -> list[tuple[str, str, object]]:
    """Return the smallest valid two-year project fixture."""

    return [
        ("Equipment_Cost", "Реактор", 10.0),
        ("Parameter", "lang_factor", 3.63),
        ("Parameter", "working_capital_share", 0.15),
        ("Parameter", "wacc", 0.12),
        ("Parameter", "tax_rate", 0.20),
        ("Parameter", "project_lifetime_years", 2),
        ("Revenue_Profile", "Year_1", 0.0),
        ("Revenue_Profile", "Year_2", 30.0),
        ("OPEX_Profile", "Year_1", 5.0),
        ("OPEX_Profile", "Year_2", 10.0),
    ]
