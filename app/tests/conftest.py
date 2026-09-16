"""Shared pytest fixtures for the DCF/CAPEX application."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

import pytest


@pytest.fixture
def repository_root() -> Path:
    """Return the repository root for the active worktree."""

    return Path(__file__).resolve().parents[2]


@pytest.fixture
def real_csv_path(repository_root: Path) -> Path:
    """Return the immutable source CSV supplied with the assignment."""

    return repository_root / "1" / "data" / "data.csv"


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

