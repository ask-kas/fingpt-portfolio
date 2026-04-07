"""
advanced_analytics.py — Institutional-grade portfolio analytics.

Monte Carlo VaR/CVaR, Efficient Frontier, Correlation Matrix, Stress Testing.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger("fingpt.analytics")


# ── Monte Carlo Simulation + VaR/CVaR ────────────────────────

def monte_carlo_simulation(
    daily_data: dict[str, list[dict]],
    holdings: list[dict],
    n_simulations: int = 10_000,
    horizon_days: int = 30,
) -> dict:
    """
    Run Monte Carlo simulation on portfolio.

    Returns VaR (95%, 99%), CVaR, simulated final values distribution,
    and percentile paths for visualization.
    """
    weights, returns_matrix = _build_portfolio_matrix(daily_data, holdings)
    if returns_matrix is None or len(returns_matrix) < 20:
        return {"error": "Insufficient price data for simulation"}

    # Portfolio parameters
    mean_returns = np.mean(returns_matrix, axis=0)
    cov_matrix = np.cov(returns_matrix.T)

    # Current portfolio value
    total_value = sum(
        h["shares"] * _latest_price(daily_data.get(h["symbol"], []))
        for h in holdings
    )
    if total_value <= 0:
        return {"error": "Portfolio value is zero"}

    # Simulate paths
    np.random.seed(42)
    simulated_returns = np.random.multivariate_normal(
        mean_returns, cov_matrix, size=(n_simulations, horizon_days)
    )

    # Portfolio return for each simulation day
    portfolio_daily = simulated_returns @ weights
    cumulative = np.cumprod(1 + portfolio_daily, axis=1)
    final_values = total_value * cumulative[:, -1]
    final_returns = (final_values / total_value - 1) * 100  # percentage

    # VaR and CVaR
    var_95 = float(np.percentile(final_returns, 5))
    var_99 = float(np.percentile(final_returns, 1))
    cvar_95 = float(np.mean(final_returns[final_returns <= np.percentile(final_returns, 5)]))
    cvar_99 = float(np.mean(final_returns[final_returns <= np.percentile(final_returns, 1)]))

    # Percentile paths for fan chart
    all_paths = total_value * cumulative
    percentile_paths = {}
    for p in [5, 25, 50, 75, 95]:
        path = np.percentile(all_paths, p, axis=0)
        percentile_paths[f"p{p}"] = [round(float(v), 2) for v in path]

    # Histogram bins
    hist_counts, hist_edges = np.histogram(final_returns, bins=50)
    histogram = {
        "counts": hist_counts.tolist(),
        "edges": [round(float(e), 2) for e in hist_edges.tolist()],
    }

    return {
        "total_value": round(total_value, 2),
        "horizon_days": horizon_days,
        "n_simulations": n_simulations,
        "var_95": round(var_95, 2),
        "var_99": round(var_99, 2),
        "cvar_95": round(cvar_95, 2),
        "cvar_99": round(cvar_99, 2),
        "expected_return": round(float(np.mean(final_returns)), 2),
        "median_return": round(float(np.median(final_returns)), 2),
        "best_case": round(float(np.max(final_returns)), 2),
        "worst_case": round(float(np.min(final_returns)), 2),
        "histogram": histogram,
        "percentile_paths": percentile_paths,
        "var_95_dollar": round(total_value * var_95 / 100, 2),
        "var_99_dollar": round(total_value * var_99 / 100, 2),
    }


# ── Efficient Frontier / Markowitz ────────────────────────────

def efficient_frontier(
    daily_data: dict[str, list[dict]],
    holdings: list[dict],
    risk_free_rate: float = 0.05,
    n_points: int = 50,
) -> dict:
    """
    Calculate the efficient frontier and optimal portfolios.

    Returns frontier curve, current allocation position,
    max-Sharpe portfolio, and min-volatility portfolio.
    """
    symbols = [h["symbol"] for h in holdings]
    returns_df = _build_returns_dataframe(daily_data, symbols)

    if returns_df is None or returns_df.shape[1] < 2:
        return {"error": "Need at least 2 holdings with price data for frontier"}

    if len(returns_df) < 30:
        return {"error": "Insufficient data points for optimization"}

    try:
        from pypfopt import expected_returns, risk_models, EfficientFrontier

        # Calculate expected returns and covariance
        mu = expected_returns.mean_historical_return(
            returns_df, compounding=True, frequency=252
        )
        S = risk_models.sample_cov(returns_df, frequency=252)

        # Current weights
        total_value = 0
        current_weights = {}
        for h in holdings:
            price = _latest_price(daily_data.get(h["symbol"], []))
            val = h["shares"] * price
            current_weights[h["symbol"]] = val
            total_value += val

        if total_value > 0:
            current_weights = {k: v / total_value for k, v in current_weights.items()}

        # Current portfolio performance
        cw = np.array([current_weights.get(s, 0) for s in symbols])
        current_ret = float(cw @ mu.values) if len(mu) == len(cw) else 0
        current_vol = float(np.sqrt(cw @ S.values @ cw)) if len(cw) == S.shape[0] else 0

        # Max Sharpe portfolio
        ef_sharpe = EfficientFrontier(mu, S)
        ef_sharpe.max_sharpe(risk_free_rate=risk_free_rate)
        sharpe_weights = ef_sharpe.clean_weights()
        sharpe_perf = ef_sharpe.portfolio_performance(risk_free_rate=risk_free_rate)

        # Min volatility portfolio
        ef_min = EfficientFrontier(mu, S)
        ef_min.min_volatility()
        min_vol_weights = ef_min.clean_weights()
        min_vol_perf = ef_min.portfolio_performance(risk_free_rate=risk_free_rate)

        # Generate frontier curve
        frontier_points = []
        # Get the range of target returns
        min_ret = float(min_vol_perf[0])
        max_ret = float(sharpe_perf[0]) * 1.5

        target_returns = np.linspace(min_ret, max_ret, n_points)
        for target in target_returns:
            try:
                ef_point = EfficientFrontier(mu, S)
                ef_point.efficient_return(float(target))
                perf = ef_point.portfolio_performance(risk_free_rate=risk_free_rate)
                frontier_points.append({
                    "return": round(float(perf[0]) * 100, 2),
                    "volatility": round(float(perf[1]) * 100, 2),
                    "sharpe": round(float(perf[2]), 3),
                })
            except Exception:
                continue

        return {
            "frontier": frontier_points,
            "current": {
                "return": round(current_ret * 100, 2),
                "volatility": round(current_vol * 100, 2),
                "weights": {k: round(v * 100, 1) for k, v in current_weights.items()},
            },
            "max_sharpe": {
                "return": round(float(sharpe_perf[0]) * 100, 2),
                "volatility": round(float(sharpe_perf[1]) * 100, 2),
                "sharpe": round(float(sharpe_perf[2]), 3),
                "weights": {k: round(v * 100, 1) for k, v in sharpe_weights.items() if v > 0.001},
            },
            "min_volatility": {
                "return": round(float(min_vol_perf[0]) * 100, 2),
                "volatility": round(float(min_vol_perf[1]) * 100, 2),
                "sharpe": round(float(min_vol_perf[2]), 3),
                "weights": {k: round(v * 100, 1) for k, v in min_vol_weights.items() if v > 0.001},
            },
            "symbols": symbols,
        }

    except Exception as e:
        logger.error("Efficient frontier calculation failed: %s", e)
        return {"error": str(e)}


# ── Correlation Matrix ────────────────────────────────────────

def correlation_matrix(
    daily_data: dict[str, list[dict]],
    symbols: list[str],
) -> dict:
    """
    Calculate pairwise correlation matrix between holdings.

    Returns matrix values and labels for heatmap rendering.
    """
    returns_df = _build_returns_dataframe(daily_data, symbols)

    if returns_df is None or returns_df.shape[1] < 2:
        return {"error": "Need at least 2 holdings with data"}

    corr = returns_df.corr()
    labels = list(corr.columns)
    matrix = [[round(float(corr.iloc[i, j]), 3) for j in range(len(labels))] for i in range(len(labels))]

    # Average correlation (excluding diagonal)
    n = len(labels)
    if n > 1:
        off_diag = [corr.iloc[i, j] for i in range(n) for j in range(n) if i != j]
        avg_corr = float(np.mean(off_diag))
    else:
        avg_corr = 1.0

    return {
        "labels": labels,
        "matrix": matrix,
        "avg_correlation": round(avg_corr, 3),
        "interpretation": _interpret_correlation(avg_corr),
    }


def _interpret_correlation(avg: float) -> str:
    if avg > 0.7:
        return "Very high — holdings move together. Diversification is weak."
    elif avg > 0.5:
        return "Moderate-high — some diversification, but concentrated risk remains."
    elif avg > 0.3:
        return "Moderate — reasonable diversification across holdings."
    elif avg > 0.0:
        return "Low — good diversification. Holdings behave independently."
    else:
        return "Negative — excellent diversification. Holdings offset each other."


# ── Stress Testing / Scenario Analysis ────────────────────────

HISTORICAL_SCENARIOS = {
    "2008_gfc": {
        "name": "2008 Global Financial Crisis",
        "description": "Sept-Nov 2008: Lehman collapse, banking crisis",
        "spy_return": -0.389,
        "period": "2008-09-01 to 2009-03-09",
    },
    "covid_crash": {
        "name": "COVID-19 Crash",
        "description": "Feb-Mar 2020: Pandemic selloff",
        "spy_return": -0.337,
        "period": "2020-02-19 to 2020-03-23",
    },
    "2022_rate_hikes": {
        "name": "2022 Rate Hike Selloff",
        "description": "Jan-Oct 2022: Aggressive Fed tightening",
        "spy_return": -0.252,
        "period": "2022-01-03 to 2022-10-12",
    },
    "dot_com": {
        "name": "Dot-Com Bust",
        "description": "Mar 2000 - Oct 2002: Tech bubble burst",
        "spy_return": -0.491,
        "period": "2000-03-24 to 2002-10-09",
    },
    "flash_crash_2010": {
        "name": "2010 Flash Crash",
        "description": "May 6, 2010: Sudden 9% drop in minutes",
        "spy_return": -0.069,
        "period": "2010-05-06",
    },
}


def stress_test(
    daily_data: dict[str, list[dict]],
    holdings: list[dict],
    custom_shock_pct: Optional[float] = None,
) -> dict:
    """
    Stress test portfolio against historical crises and custom scenarios.

    Uses beta-adjusted returns: stock_loss = beta * market_loss.
    """
    weights, returns_matrix = _build_portfolio_matrix(daily_data, holdings)
    if returns_matrix is None:
        return {"error": "Insufficient data for stress testing"}

    symbols = [h["symbol"] for h in holdings]
    total_value = sum(
        h["shares"] * _latest_price(daily_data.get(h["symbol"], []))
        for h in holdings
    )

    # Calculate beta for each holding vs portfolio
    portfolio_returns = returns_matrix @ weights
    betas = {}
    for i, sym in enumerate(symbols):
        if returns_matrix.shape[1] > i:
            stock_returns = returns_matrix[:, i]
            cov = np.cov(stock_returns, portfolio_returns)[0, 1]
            var = np.var(portfolio_returns)
            betas[sym] = float(cov / var) if var > 0 else 1.0

    results = []
    for key, scenario in HISTORICAL_SCENARIOS.items():
        market_drop = scenario["spy_return"]
        # Beta-adjusted portfolio loss
        portfolio_loss = sum(
            weights[i] * betas.get(sym, 1.0) * market_drop
            for i, sym in enumerate(symbols)
        )
        dollar_loss = total_value * portfolio_loss

        per_holding = []
        for i, sym in enumerate(symbols):
            h = next((h for h in holdings if h["symbol"] == sym), None)
            if h:
                pos_val = h["shares"] * _latest_price(daily_data.get(sym, []))
                holding_loss = betas.get(sym, 1.0) * market_drop
                per_holding.append({
                    "symbol": sym,
                    "beta": round(betas.get(sym, 1.0), 2),
                    "estimated_loss_pct": round(holding_loss * 100, 1),
                    "estimated_loss_dollar": round(pos_val * holding_loss, 2),
                })

        results.append({
            "scenario": key,
            "name": scenario["name"],
            "description": scenario["description"],
            "period": scenario["period"],
            "market_return_pct": round(market_drop * 100, 1),
            "portfolio_return_pct": round(portfolio_loss * 100, 1),
            "portfolio_loss_dollar": round(dollar_loss, 2),
            "per_holding": per_holding,
        })

    # Custom scenario
    if custom_shock_pct is not None:
        shock = custom_shock_pct / 100
        portfolio_loss = sum(
            weights[i] * betas.get(sym, 1.0) * shock
            for i, sym in enumerate(symbols)
        )
        results.append({
            "scenario": "custom",
            "name": f"Custom Shock ({custom_shock_pct}%)",
            "description": f"User-defined market move of {custom_shock_pct}%",
            "period": "Hypothetical",
            "market_return_pct": custom_shock_pct,
            "portfolio_return_pct": round(portfolio_loss * 100, 1),
            "portfolio_loss_dollar": round(total_value * portfolio_loss, 2),
            "per_holding": [],
        })

    return {
        "total_value": round(total_value, 2),
        "scenarios": results,
        "betas": {k: round(v, 2) for k, v in betas.items()},
    }


# ── Helper Functions ──────────────────────────────────────────

def _latest_price(data: list[dict]) -> float:
    """Get latest closing price from daily data (newest-first)."""
    if data and len(data) > 0:
        return float(data[0].get("close", 0))
    return 0.0


def _build_portfolio_matrix(
    daily_data: dict[str, list[dict]],
    holdings: list[dict],
) -> tuple:
    """
    Build weight vector and aligned returns matrix.

    Returns (weights_array, returns_matrix) or (None, None).
    """
    symbols = [h["symbol"] for h in holdings]
    all_returns = {}
    total_value = 0
    values = {}

    for h in holdings:
        sym = h["symbol"]
        data = daily_data.get(sym, [])
        if not data:
            continue

        closes = [d["close"] for d in reversed(data)]  # oldest first
        if len(closes) < 2:
            continue

        rets = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]
        all_returns[sym] = rets
        price = data[0]["close"]  # newest
        val = h["shares"] * price
        values[sym] = val
        total_value += val

    if not all_returns or total_value <= 0:
        return None, None

    # Align to shortest series
    valid_symbols = [s for s in symbols if s in all_returns]
    min_len = min(len(all_returns[s]) for s in valid_symbols)

    if min_len < 10:
        return None, None

    returns_matrix = np.array([all_returns[s][:min_len] for s in valid_symbols]).T
    weights = np.array([values.get(s, 0) / total_value for s in valid_symbols])

    return weights, returns_matrix


def _build_returns_dataframe(
    daily_data: dict[str, list[dict]],
    symbols: list[str],
) -> Optional[pd.DataFrame]:
    """Build a DataFrame of daily returns aligned by date for all symbols."""
    price_series = {}
    for sym in symbols:
        data = daily_data.get(sym, [])
        if not data:
            continue
        df = pd.DataFrame(data)
        if "date" not in df.columns or "close" not in df.columns:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        price_series[sym] = df["close"]

    if len(price_series) < 2:
        return None

    prices_df = pd.DataFrame(price_series).dropna()
    if len(prices_df) < 20:
        return None

    return prices_df
