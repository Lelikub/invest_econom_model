"""Typed domain objects shared by the DCF/CAPEX pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EquipmentItem:
    """One equipment item and its delivered cost."""

    name: str
    cost: float


@dataclass(frozen=True)
class InputConflict:
    """A disclosed difference between a PDF control value and the CSV."""

    field: str
    pdf_value: float
    csv_value: float
    pdf_source: str
    csv_source: str = "data.csv"


@dataclass(frozen=True)
class ValidationRecord:
    """One successful input validation check."""

    check: str
    status: str
    details: str


@dataclass(frozen=True)
class ProjectData:
    """Validated inputs for one investment-project scenario."""

    equipment: tuple[EquipmentItem, ...]
    lang_factor: float
    working_capital_share: float
    wacc: float
    tax_rate: float
    project_lifetime_years: int
    revenue: dict[int, float]
    opex: dict[int, float]
    conflicts: tuple[InputConflict, ...] = ()
    validations: tuple[ValidationRecord, ...] = ()
    source_path: Path | None = None

    @property
    def years(self) -> tuple[int, ...]:
        """Return the modeled years in chronological order."""

        return tuple(range(1, self.project_lifetime_years + 1))

