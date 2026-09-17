"""Seeded Monte Carlo analysis for CAPEX and Revenue uncertainty."""

from __future__ import annotations

import math

import numpy as np

from .financial_model import FinancialModel
from .models import MonteCarloResult, ProjectData
from .scenarios import scaled_project


def lognormal_parameters(coefficient_of_variation: float) -> tuple[float, float]:
    """Convert a target mean of 1 and CV into lognormal mu and sigma."""

    if coefficient_of_variation < 0:
        raise ValueError("Коэффициент вариации не может быть отрицательным")
    sigma = math.sqrt(math.log1p(coefficient_of_variation**2))
    mu = -0.5 * sigma**2
    return mu, sigma


def run_monte_carlo(
    data: ProjectData,
    *,
    iterations: int = 1000,
    seed: int = 20260916,
    capex_cv: float = 0.30,
    revenue_cv: float = 0.20,
) -> MonteCarloResult:
    """Recalculate NPV for independent lognormal CAPEX/Revenue factors."""

    if iterations <= 0:
        raise ValueError("Количество итераций должно быть положительным")
    rng = np.random.default_rng(seed)
    capex_mu, capex_sigma = lognormal_parameters(capex_cv)
    revenue_mu, revenue_sigma = lognormal_parameters(revenue_cv)
    capex_factors = rng.lognormal(capex_mu, capex_sigma, size=iterations)
    revenue_factors = rng.lognormal(revenue_mu, revenue_sigma, size=iterations)
    npv_values = np.empty(iterations, dtype=float)

    for index, (capex_factor, revenue_factor) in enumerate(zip(capex_factors, revenue_factors)):
        scenario = scaled_project(
            data,
            equipment_factor=float(capex_factor),
            revenue_factor=float(revenue_factor),
        )
        npv_values[index] = FinancialModel(scenario).calculate().npv

    quantile_levels = (0.05, 0.25, 0.50, 0.75, 0.95)
    quantile_values = np.quantile(npv_values, quantile_levels)
    return MonteCarloResult(
        npv_values=npv_values,
        iterations=iterations,
        seed=seed,
        capex_cv=capex_cv,
        revenue_cv=revenue_cv,
        mean=float(np.mean(npv_values)),
        median=float(np.median(npv_values)),
        standard_deviation=float(np.std(npv_values, ddof=0)),
        minimum=float(np.min(npv_values)),
        maximum=float(np.max(npv_values)),
        quantiles={level: float(value) for level, value in zip(quantile_levels, quantile_values)},
        probability_negative=float(np.mean(npv_values < 0.0)),
    )

