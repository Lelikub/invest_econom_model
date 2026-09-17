"""Russian-language plots for Monte Carlo results."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .models import MonteCarloResult


def save_monte_carlo_charts(result: MonteCarloResult, output_dir: Path) -> tuple[Path, Path]:
    """Save the NPV histogram and empirical cumulative S-curve."""

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    histogram_path = destination / "histogram_npv.png"
    s_curve_path = destination / "s_curve_npv.png"

    plt.figure(figsize=(10, 6), dpi=150)
    plt.hist(result.npv_values, bins=35, color="#4472C4", edgecolor="white", alpha=0.9)
    plt.axvline(0.0, color="#C00000", linestyle="--", linewidth=1.5, label="NPV = 0")
    plt.axvline(result.mean, color="#548235", linewidth=1.5, label="Среднее NPV")
    plt.title("Распределение чистой приведённой стоимости (NPV)")
    plt.xlabel("NPV, условные денежные единицы")
    plt.ylabel("Количество сценариев")
    plt.legend()
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(histogram_path)
    plt.close()

    sorted_values = np.sort(result.npv_values)
    probabilities = np.arange(1, result.iterations + 1, dtype=float) / result.iterations
    plt.figure(figsize=(10, 6), dpi=150)
    plt.plot(sorted_values, probabilities, color="#7030A0", linewidth=2.0)
    plt.axvline(0.0, color="#C00000", linestyle="--", linewidth=1.5, label="NPV = 0")
    plt.title("S-Curve: эмпирическая вероятность P(NPV ≤ x)")
    plt.xlabel("NPV, условные денежные единицы")
    plt.ylabel("Вероятность P(NPV ≤ x)")
    plt.ylim(0.0, 1.0)
    plt.legend()
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(s_curve_path)
    plt.close()
    return histogram_path, s_curve_path

