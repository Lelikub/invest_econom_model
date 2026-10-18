"""Financial inputs and Cox–Ross–Rubinstein American expansion option."""
from __future__ import annotations

from dataclasses import dataclass, replace
from math import exp, isfinite, sqrt


class ArbitrageConditionError(ValueError):
    pass


@dataclass(frozen=True)
class ProjectInputData:
    I0: float
    S0: float
    K: float
    r: float
    sigma: float
    delta: float
    T: float
    N: int
    m: float

    def validate(self) -> None:
        for key in ("I0", "S0", "K", "r", "sigma", "delta", "T", "m"):
            if not isfinite(getattr(self, key)):
                raise ValueError(f"{key} must be finite")
        if self.S0 <= 0 or self.I0 < 0 or self.K < 0 or self.r < 0 or self.sigma < 0 or self.delta < 0 or self.T <= 0 or self.m <= 0:
            raise ValueError("Input outside permitted range")
        if isinstance(self.N, bool) or not isinstance(self.N, int) or self.N < 1:
            raise ValueError("N must be a positive integer")

    def changed(self, **kwargs) -> "ProjectInputData":
        return replace(self, **kwargs)


@dataclass(frozen=True)
class CRRParameters:
    dt: float
    u: float
    d: float
    p: float
    discount_factor: float


@dataclass(frozen=True)
class LatticeNode:
    i: int
    j: int
    S: float
    intrinsic: float
    continuation: float | None
    C: float
    decision: str


@dataclass(frozen=True)
class ModelResult:
    inputs: ProjectInputData
    params: CRRParameters
    asset: tuple[tuple[float, ...], ...]
    option: tuple[tuple[LatticeNode, ...], ...]
    npv_trad: float
    rov: float
    npv_strat: float


def calculate(data: ProjectInputData, *, p_override: float | None = None) -> ModelResult:
    data.validate()
    dt = data.T / data.N
    u = exp(data.sigma * sqrt(dt))
    d = 1 / u
    growth = exp((data.r - data.delta) * dt)
    if not d < growth < u:
        raise ArbitrageConditionError(f"No-arbitrage violation: d={d}, growth={growth}, u={u}; r={data.r}, delta={data.delta}, dt={dt}")
    p = (growth - d) / (u - d)
    if not 0 < p < 1:
        raise ArbitrageConditionError(f"Risk-neutral probability outside (0,1): {p}")
    if p_override is not None:
        if not 0 <= p_override <= 1:
            raise ValueError("Synthetic p must be in [0,1]")
        p = p_override
    discount = exp(-data.r * dt)
    params = CRRParameters(dt, u, d, p, discount)
    asset = tuple(tuple(data.S0 * data.m * u**j * d**(i-j) for j in range(i + 1)) for i in range(data.N + 1))
    option: list[tuple[LatticeNode, ...]] = [()] * (data.N + 1)
    option[data.N] = tuple(LatticeNode(data.N, j, s, max(s-data.K, 0), None, max(s-data.K, 0), "EXPIRY") for j, s in enumerate(asset[data.N]))
    for i in range(data.N - 1, -1, -1):
        row = []
        for j, s in enumerate(asset[i]):
            intrinsic = max(s - data.K, 0)
            continuation = discount * ((1-p)*option[i+1][j].C + p*option[i+1][j+1].C)
            exercise = intrinsic > continuation
            row.append(LatticeNode(i, j, s, intrinsic, continuation, max(intrinsic, continuation), "EXERCISE" if exercise else "WAIT"))
        option[i] = tuple(row)
    rov = option[0][0].C
    if not all(isfinite(n.C) and n.C >= n.intrinsic >= 0 and isfinite(n.S) and n.S > 0 for row in option for n in row):
        raise ArithmeticError("Lattice sanity check failed")
    if abs(u*d-1) > 1e-12:
        raise ArithmeticError("Non-recombining CRR factors")
    npv_trad = data.S0 - data.I0
    return ModelResult(data, params, asset, tuple(option), npv_trad, rov, npv_trad + rov)
