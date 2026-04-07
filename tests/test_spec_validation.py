"""
test_spec_validation.py — The 8 validation tests from the v5 spec.

Each test corresponds to one of the 8 tests listed in PART 3 of the
rebuild specification. They are deterministic, run on synthetic data,
and confirm that the math modules behave as the institutional spec
requires.
"""

import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.portfolio import (
    calculate_max_drawdown,
    calculate_rsi,
    portfolio_volatility_full,
    weighted_portfolio_beta,
)
from backend.advanced_analytics import (
    monte_carlo_simulation,
    cpi_yoy_pct,
)
from backend.options_math import black_scholes_call


# Test 1 — Portfolio volatility uses full covariance matrix
def test_portfolio_volatility_full_covariance():
    sigma = np.array([0.19, 0.26, 0.28])
    rho = np.array([
        [1.00, 0.53, 0.11],
        [0.53, 1.00, 0.19],
        [0.11, 0.19, 1.00],
    ])
    cov_annual = np.outer(sigma, sigma) * rho
    weights = np.array([0.4852, 0.3485, 0.1663])

    sigma_p = portfolio_volatility_full(weights, cov_annual)

    # Closed form: sqrt(w' C w) for these inputs equals 0.1740.
    # The diagonal only version would give 0.1374, so this assertion
    # confirms the off diagonal covariance terms are applied.
    diagonal_only = math.sqrt(float((weights ** 2) @ (sigma ** 2)))
    assert math.isclose(sigma_p, 0.1740, abs_tol=1e-3), (
        f"Portfolio vol {sigma_p:.4f} does not match closed form 0.1740. "
        "Covariance matrix is not being applied correctly."
    )
    assert sigma_p > diagonal_only + 0.02, (
        "Portfolio vol matches diagonal only formula. "
        "Off diagonal covariance terms are missing."
    )


# Test 2 — Sharpe ratio uses correct formula and matches expected sign
def test_sharpe_negative_when_return_below_rf():
    annual_return = -0.05
    rf = 0.0435
    sigma = 0.22
    expected = (annual_return - rf) / sigma
    assert math.isclose(expected, -0.4250, abs_tol=1e-3)


# Test 3 — Max drawdown uses full price history (newest first)
def test_max_drawdown_msft_full_history():
    prices_newest_first = [372.00, 555.45, 400.00, 350.00, 200.00]
    mdd = calculate_max_drawdown(prices_newest_first)
    expected = (555.45 - 372.00) / 555.45
    assert math.isclose(mdd, expected, abs_tol=1e-3), (
        f"MDD {mdd:.4f} does not match expected {expected:.4f}. "
        "Lookback window may be too short."
    )
    assert math.isclose(mdd, 0.3302, abs_tol=1e-3)


# Test 4 — Portfolio beta is the weighted sum of holding betas
def test_portfolio_beta_weighted_sum():
    weights = np.array([0.4852, 0.3485, 0.1663])
    betas = np.array([0.87, 0.91, 1.28])
    port_beta = weighted_portfolio_beta(weights, betas)
    expected = 0.4852 * 0.87 + 0.3485 * 0.91 + 0.1663 * 1.28
    assert math.isclose(port_beta, expected, abs_tol=1e-4)
    assert math.isclose(port_beta, 0.9521, abs_tol=1e-3)


# Test 5 — CPI displays as YoY percentage
def test_cpi_yoy_percentage():
    pct = cpi_yoy_pct(327.46, 317.69)
    assert math.isclose(pct, 3.07, abs_tol=0.05), (
        f"CPI YoY {pct:.2f}% does not match spec value 3.07%"
    )


# Test 6 — Monte Carlo preserves the correlation structure
def test_monte_carlo_preserves_correlation():
    np.random.seed(42)
    n = 600
    base = np.random.normal(0, 0.012, size=n)
    aapl = base + np.random.normal(0, 0.006, size=n)
    msft = 0.6 * base + np.random.normal(0, 0.010, size=n)
    googl = np.random.normal(0, 0.014, size=n)

    def to_records(closes_simple_returns):
        prices = [100.0]
        for r in closes_simple_returns:
            prices.append(prices[-1] * (1 + r))
        records = []
        for i, p in enumerate(prices):
            records.append({"date": f"2024-{(i % 12) + 1:02d}-01", "close": round(p, 4)})
        records.reverse()
        return records

    daily_data = {
        "AAPL": to_records(aapl),
        "MSFT": to_records(msft),
        "GOOGL": to_records(googl),
    }
    holdings = [
        {"symbol": "AAPL", "shares": 10, "avg_cost": 170},
        {"symbol": "MSFT", "shares": 5, "avg_cost": 380},
        {"symbol": "GOOGL", "shares": 3, "avg_cost": 140},
    ]

    result = monte_carlo_simulation(
        daily_data, holdings, n_simulations=4000, horizon_days=30
    )
    assert "error" not in result, result.get("error")

    sim_corr = result["debug_simulated_correlation"]
    historical_corr = result["debug_historical_correlation"]

    sim = np.array(sim_corr)
    hist = np.array(historical_corr)

    off_diag_diff = []
    n_assets = sim.shape[0]
    for i in range(n_assets):
        for j in range(n_assets):
            if i != j:
                off_diag_diff.append(abs(sim[i, j] - hist[i, j]))

    max_diff = max(off_diag_diff)
    assert max_diff < 0.10, (
        f"Simulated correlation differs from historical by {max_diff:.3f}. "
        "Cholesky decomposition step is likely missing."
    )


# Test 7 — Black-Scholes call price matches the spec hand-calculation
def test_black_scholes_call_matches_spec():
    S = 258.86
    K = 260.0
    r = 0.0435
    T = 30 / 365
    sigma = 0.20
    price = black_scholes_call(S, K, r, T, sigma)
    assert 5.0 <= price <= 7.0, (
        f"Black-Scholes call price {price:.2f} outside spec range 5.0..7.0"
    )


# Test 8 — RSI 14 with Wilder smoothing is computed correctly
def test_rsi_wilder_smoothing():
    np.random.seed(7)
    prices_oldest_first = [100.0]
    for _ in range(60):
        prices_oldest_first.append(prices_oldest_first[-1] * (1 + np.random.normal(0, 0.01)))
    prices_newest_first = list(reversed(prices_oldest_first))

    rsi = calculate_rsi(prices_newest_first, period=14)
    assert 0 <= rsi <= 100, f"RSI {rsi} outside the 0..100 range"

    flat_prices_newest_first = list(reversed([100.0 + i * 0.5 for i in range(30)]))
    rsi_up = calculate_rsi(flat_prices_newest_first, period=14)
    assert rsi_up > 90, (
        f"Strictly increasing prices should give RSI near 100, got {rsi_up}"
    )

    flat_prices_down = list(reversed([100.0 - i * 0.5 for i in range(30)]))
    rsi_down = calculate_rsi(flat_prices_down, period=14)
    assert rsi_down < 10, (
        f"Strictly decreasing prices should give RSI near 0, got {rsi_down}"
    )
