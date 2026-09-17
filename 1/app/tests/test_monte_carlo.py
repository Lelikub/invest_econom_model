"""Tests for seeded probabilistic analysis and chart artifacts."""

from __future__ import annotations

import numpy as np
from PIL import Image

from src.charts import save_monte_carlo_charts
from src.monte_carlo import lognormal_parameters, run_monte_carlo


def test_lognormal_parameters_produce_requested_mean_and_cv():
    """Passing percentage figures directly as sigma must fail this test."""

    mu, sigma = lognormal_parameters(0.30)
    mean = np.exp(mu + sigma**2 / 2)
    cv = np.sqrt(np.exp(sigma**2) - 1)

    np.testing.assert_allclose(mean, 1.0, rtol=0, atol=1e-12)
    np.testing.assert_allclose(cv, 0.30, rtol=0, atol=1e-12)


def test_monte_carlo_is_seeded_and_has_exact_iteration_count(real_project_data):
    """Changing the seed handling or iteration count must fail."""

    first = run_monte_carlo(real_project_data, iterations=1000, seed=20260916)
    second = run_monte_carlo(real_project_data, iterations=1000, seed=20260916)

    np.testing.assert_array_equal(first.npv_values, second.npv_values)
    assert len(first.npv_values) == 1000
    assert first.iterations == 1000
    assert 0.0 <= first.probability_negative <= 1.0
    assert set(first.quantiles) == {0.05, 0.25, 0.50, 0.75, 0.95}


def test_charts_are_nonempty_readable_png_files(real_project_data, tmp_path):
    """Producing blank or invalid chart files must fail."""

    result = run_monte_carlo(real_project_data, iterations=1000, seed=20260916)
    histogram, s_curve = save_monte_carlo_charts(result, tmp_path)

    for path in (histogram, s_curve):
        assert path.exists() and path.stat().st_size > 10_000
        with Image.open(path) as image:
            assert image.format == "PNG"
            assert image.width >= 1000
            assert image.height >= 600
