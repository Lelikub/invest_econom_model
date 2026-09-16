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


@dataclass(frozen=True)
class CapitalEstimate:
    """Lang-factor capital estimate in the source monetary scale."""

    equipment_cost: float
    fci: float
    tci: float


@dataclass(frozen=True)
class DCFRow:
    """One operating year of the deterministic DCF model."""

    year: int
    revenue: float
    opex: float
    depreciation: float
    ebit: float
    nopat: float
    capex: float
    delta_nwc: float
    fcf: float
    discount_factor: float
    discounted_fcf: float
    cumulative_discounted_cash_flow: float


@dataclass(frozen=True)
class MetricOutcome:
    """A financial metric with an explicit availability status."""

    value: float | None
    status: str


@dataclass(frozen=True)
class FinancialResult:
    """Complete deterministic model output."""

    capital: CapitalEstimate
    rows: tuple[DCFRow, ...]
    cash_flows: tuple[float, ...]
    npv: float
    irr: MetricOutcome
    pi: MetricOutcome
    dpbp: MetricOutcome

    def numeric_metrics(self) -> dict[str, float | None]:
        """Return stable metric keys used by Excel comparison."""

        metrics: dict[str, float | None] = {
            "FCI": self.capital.fci,
            "TCI": self.capital.tci,
            "NPV": self.npv,
            "IRR": self.irr.value,
            "PI": self.pi.value,
            "DPBP": self.dpbp.value,
        }
        for row in self.rows:
            metrics[f"Амортизация_{row.year}"] = row.depreciation
            metrics[f"EBIT_{row.year}"] = row.ebit
            metrics[f"NOPAT_{row.year}"] = row.nopat
            metrics[f"FCF_{row.year}"] = row.fcf
        return metrics


@dataclass(frozen=True)
class MetricComparison:
    """One Python-to-Excel metric comparison."""

    name: str
    python_value: float | None
    excel_value: float | None
    absolute_difference: float | None
    relative_difference_percent: float | None
    status: str


@dataclass(frozen=True)
class ComparisonResult:
    """Aggregate result of numerical comparison."""

    items: tuple[MetricComparison, ...]
    all_match: bool
    max_absolute_difference: float
    max_relative_deviation_percent: float

