"""Immutable data only. Financial equations live in calculators."""
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Project:
    capex_base: float
    volume: float
    fixed_opex: float
    years: float
    nwc: float
    wacc: float
    igpr_mean: float
    igpr_sigma: float
    pillar_floor: float
    price_eu: float
    price_asia: float
    calendar_end: float

@dataclass(frozen=True)
class Country:
    code: str
    oecd: float
    spread: float
    volatility: float
    gpr_base: float
    igpr: float
    gamma: float
    nominal_tax: float
    inflation: float
    delay: float
    subsidy_rate: float
    approval: float
    clawback: float
    subsidy_year: float
    equip_duty: float
    duty_free: float
    gov_rate: float
    wht: float
    raw_base: float
    logistics_in: float
    lead_days: float
    input_duty: float
    raw_control: float
    share_eu: float
    share_asia: float
    price_control: float
    logistics_out: float
    outbound_days: float
    cbam: float
    net_price_control: float
    first: float
    last: float
    first_load: float
    last_load: float
    nwc_draw: float
    nwc_release: float
    holiday_tax: float
    holiday_end: float
    tax_credit: float

@dataclass(frozen=True)
class Inputs:
    project: Project
    countries: dict[str, Country]
    scenarios: dict[str, float]
    provenance: tuple[dict, ...]

@dataclass(frozen=True)
class RiskResult:
    crp: float
    gpr: float
    rate: float

@dataclass(frozen=True)
class CapexResult:
    gross: float
    subsidy_pv: float
    net: float

@dataclass(frozen=True)
class SupplyResult:
    price_weighted: float
    raw_landed: float
    price_net: float
    cbam_unit: float
    inbound_unit: float
    duty_unit: float
    outbound_unit: float

@dataclass(frozen=True)
class AnnualResult:
    year: int
    load: float
    volume: float
    revenue_eu: float
    revenue_asia: float
    outbound_cost: float
    cbam_cost: float
    revenue: float
    raw_cost: float
    inbound_cost: float
    duty_cost: float
    fixed_opex: float
    opex: float
    depreciation: float
    ebit: float
    holiday_rate: float
    tax_credit: float
    tax_gross: float
    literal_tax: float
    cash_tax: float
    operating_cf: float
    nwc_change: float
    nwc_cash_effect: float
    investment: float
    local_cf: float
    wht: float
    parent_cf: float
    parent_literal: float
    parent_literal_tax: float
    discount_factor: float
    discounted_parent: float
    cumulative_parent: float

@dataclass(frozen=True)
class MetricResult:
    npv: float
    irr: float | None
    irr_status: str
    irr_roots: tuple[float, ...]
    pi: float | None
    pv_inflows: float
    pv_outflows: float
    dpp: float | None
    dpp_status: str

@dataclass(frozen=True)
class CountryResult:
    country: Country
    risk: RiskResult
    capex: CapexResult
    supply: SupplyResult
    annual: tuple[AnnualResult, ...]
    local: MetricResult
    parent: MetricResult
    literal: MetricResult
    literal_tax: MetricResult

@dataclass(frozen=True)
class StatisticsResult:
    expected: float
    variance: float
    std: float
    probability_negative: float

@dataclass(frozen=True)
class ScenarioResult:
    results: dict[str, dict[str, CountryResult]]
    statistics: dict[str, StatisticsResult]
    probabilities: dict[str, float]

@dataclass(frozen=True)
class PipelineConfig:
    app: Path
    pdf: Path
    lecture: Path
    output: Path
    excel_timeout: int = 90
    template: Path | None = None

@dataclass(frozen=True)
class ReportSectionDTO:
    section_id: str
    title: str
    table_id: str
    chart_id: str | None
    columns: tuple[str, ...]
    rows: tuple[tuple, ...]
    analysis: str

@dataclass(frozen=True)
class ReportTextDTO:
    text: str
    bullet: bool = False

@dataclass(frozen=True)
class ReportHeadingDTO:
    text: str

@dataclass(frozen=True)
class ReportFormulaDTO:
    formula_id: str
    equation: str
    explanation: str

@dataclass(frozen=True)
class ReportChapterDTO:
    title: str
    blocks: tuple[ReportSectionDTO | ReportTextDTO | ReportHeadingDTO | ReportFormulaDTO, ...]
