from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    id: int
    name: str
    code: str
    margin: float
    yield_rate: float


@dataclass(frozen=True)
class Machine:
    id: int
    name: str
    capacity: float
    fixed_cost: float


@dataclass(frozen=True)
class Material:
    id: int
    name: str
    capacity: float
    unit: str


@dataclass(frozen=True)
class InvestmentProject:
    id: int
    name: str
    capex: float
    npv: float
    score: int


Link = tuple[str, int, int]


@dataclass(frozen=True)
class OperationalInputs:
    products: tuple[Product, ...]
    machines: tuple[Machine, ...]
    materials: tuple[Material, ...]
    machine_coefficients: tuple[tuple[float, ...], ...]
    material_coefficients: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class PortfolioInputs:
    projects: tuple[InvestmentProject, ...]
    budget: float
    links: tuple[Link, ...]


@dataclass(frozen=True)
class Scenario:
    zero_nmp: float
    negative_margin: float
    forbidden_machine: int
    extra_link: Link
    stress_budget: float
    budget_cut: float
    npv_cut: float
    carbon_tax: float
    emission_factor: float
    score_floor: int
    epsilon_step: int
    mrt_limit: float
    gap_limit: float


@dataclass(frozen=True)
class OperationResult:
    status: str
    x: tuple[float, ...]
    y: tuple[float, ...]
    objective: float
    load: tuple[float, ...]
    rhs: tuple[float, ...]
    slack: tuple[float, ...]
    bound: float | None = None
    gap: float | None = None
    shadow: tuple[float, ...] = ()
    reduced: tuple[float, ...] = ()
    upper_shadow: tuple[float, ...] = ()
    launch_reduced: tuple[float, ...] = ()


@dataclass(frozen=True)
class PortfolioResult:
    ids: tuple[int, ...]
    capex: float
    npv: float
    score: int
    slack: float
    status: str
    bound: float | None = None
    gap: float | None = None
