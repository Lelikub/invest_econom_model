"""Passive, typed input and result records. No financial operations live here."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from enum import StrEnum
import pandas as pd


class MetricId(StrEnum):
    T_EFF='t_eff'
    DE_PEER='de_peer'
    BETA_U='beta_u'
    DE='de'
    BETA_L='beta_l'
    RF='rf'
    ERP='erp'
    CRP='crp'
    WE='we'
    WD='wd'
    KE='ke'
    KD='kd'
    KD_AFTER_TAX='kd_after_tax'
    WACC='wacc'
    DSCR='dscr'
    EQUITY='equity'
    DEBT='debt'
    EBITDA='ebitda'
    CREDIT_SPREAD='credit_spread'
    DELTA_TOTAL='delta_total'
    PI_EXP='pi_exp'
    BETA_MULTIPLIER='beta_multiplier'


@dataclass(frozen=True)
class ProjectInputData:
    capex: float
    we: float
    wd: float
    de_control: float
    t_nominal: float
    rd_relief: float
    t_floor: float
    s_base: float
    dscr0: float
    covenant: float
    revenue: float
    opex: float
    ebitda: float
    debt_service: float
    pan_capacity: float
    carbon_capacity: float
    name: str = 'AeroCarbon Synth'
    currency: str = 'USD'


@dataclass(frozen=True)
class MarketAssumptions:
    horizon_years: float
    horizon_months: float
    equity_peer: float
    debt_peer: float
    tax_peer: float
    rf: float
    erp: float
    crp: float
    beta_peer: float
    peer: str
    index: str


@dataclass(frozen=True)
class ShockParameters:
    oil: float
    eta: float
    psi_energy: float
    taiwan: float
    psi_tw: float
    alpha_cross: float
    tariff: float
    psi_tariff: float
    psi_cross: float
    term_premium: float
    crp_europe: float
    spread_europe: float
    flight: float
    crash: float
    panic_lambda: float
    mu_ebitda: float
    gamma1: float


@dataclass(frozen=True)
class MarketPriceSeries:
    frame: pd.DataFrame
    source: Path
    sha256: str


@dataclass(frozen=True)
class ScenarioInputs:
    name: str
    project: ProjectInputData
    market: MarketAssumptions
    shocks: ShockParameters


@dataclass(frozen=True)
class CalculationResult:
    scenario: str
    metrics: dict[MetricId, float]

    def __post_init__(self):
        object.__setattr__(self,'metrics',{MetricId(k):v for k,v in self.metrics.items()})


@dataclass(frozen=True)
class StressResult(CalculationResult):
    assumptions: tuple[str, ...] = ('CRP_Taiwan = GPR_Taiwan', 'E0=we*CAPEX, D0=wd*CAPEX: условная оценка')


@dataclass(frozen=True)
class RegressionResult:
    beta_ols: float
    alpha_raw: float
    r_squared: float
    p_value: float
    stderr: float
    intercept_stderr: float
    n: int
    alpha_jensen: float | None = None
    alpha_jensen_status: str = 'NOT_CALCULATED: отсутствует месячный ряд Rf'


@dataclass(frozen=True)
class WaterfallResult:
    mode: str
    dividend_lockup: bool
    debt_service: float
    debt_paid: float
    cfads_before_debt_service: float
    cash_after_debt_service: float
    dsra: float
    dividends: float
    retained: float
    shortfall: float
    flows: list[dict[str, Any]]


@dataclass(frozen=True)
class ChartAuditResult:
    chart_id: str
    validation_status: str
    checks: dict[str, Any]
    visual_status: str = 'NOT_VERIFIED'


@dataclass(frozen=True)
class TestResult:
    test_id: str
    inputs: str
    expected: str
    actual: str
    tolerance: float
    passed: bool
    exception: str = ''
    source: str = ''


@dataclass(frozen=True)
class HarnessEntry:
    issue_id: str
    stage: str
    task: str
    code: str
    issue: str
    cause: str
    resolution: str
    recheck: str
    category: str
    run_id: str = ''
    timestamp: str = ''


@dataclass(frozen=True)
class PipelineConfig:
    app_dir: Path
    pdf: Path
    prices: Path
    lecture: Path
    output: Path
    excel_timeout: int = 90
