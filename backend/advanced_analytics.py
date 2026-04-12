"""
advanced_analytics.py — Institutional grade portfolio analytics (v5 spec).

Monte Carlo VaR/CVaR uses Cholesky decomposition for correlated draws and
a Student t marginal distribution to capture tail risk in tech equities.
The optimizer uses box constraints and a Black Litterman style mean
estimator. Stress testing includes a reverse stress test and uses the
same canonical OLS beta as the rest of the system.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize_scalar

from backend.portfolio import (
    TRADING_DAYS_STOCKS,
    beta_ols,
    log_returns_from_prices,
)

logger = logging.getLogger("fingpt.analytics")


# ── Macro helpers (spec module 12) ───────────────────────────

def cpi_yoy_pct(cpi_current: float, cpi_year_ago: float) -> float:
    """CPI year over year inflation rate as a percentage.

    CPI_YoY = ((CPI_t / CPI_{t minus 12}) minus 1) * 100
    """
    if cpi_year_ago <= 0:
        return 0.0
    return float((cpi_current / cpi_year_ago - 1.0) * 100.0)


# ── Monte Carlo VaR / CVaR (spec module 5) ───────────────────

def _fit_student_t_dof(returns: np.ndarray, default: float = 5.0) -> float:
    """Fit Student t degrees of freedom to a return series via MLE.

    Falls back to the default if there is too little data or the fit
    is not believable.
    """
    if returns.size < 30:
        return default
    try:
        df, _, _ = stats.t.fit(returns, floc=0)
        if df < 2.5 or df > 30:
            return default
        return float(df)
    except Exception:
        return default


def monte_carlo_simulation(
    daily_data: dict[str, list[dict]],
    holdings: list[dict],
    n_simulations: int = 10_000,
    horizon_days: int = 30,
) -> dict:
    """Monte Carlo VaR/CVaR using Cholesky + Student t marginals.

    Step 1: Build the daily log return matrix and align by length.
    Step 2: Estimate mean vector, covariance matrix, and t degrees of freedom.
    Step 3: Cholesky factor L of the covariance matrix.
    Step 4: For each draw, sample iid t variables, multiply by L,
            add the mean vector, then compound across the horizon.
    Step 5: Build the portfolio P&L distribution and read VaR / CVaR
            off the empirical quantiles.
    """
    weights, returns_matrix, symbols = _build_portfolio_matrix(daily_data, holdings)
    if returns_matrix is None or returns_matrix.shape[0] < 30:
        return {"error": "Insufficient price history for Monte Carlo (need 30 days minimum)"}

    n_assets = returns_matrix.shape[1]

    mean_vector = np.mean(returns_matrix, axis=0)
    cov_matrix = np.cov(returns_matrix, rowvar=False, ddof=1)
    if cov_matrix.ndim == 0:
        cov_matrix = np.array([[float(cov_matrix)]])

    # Per asset Student t degrees of freedom, then take the conservative minimum.
    per_asset_dof = [_fit_student_t_dof(returns_matrix[:, i]) for i in range(n_assets)]
    nu = float(min(per_asset_dof))
    nu = max(2.5, min(nu, 30.0))

    # Cholesky. If the covariance matrix is degenerate, fall back to a tiny
    # ridge term so we still get a usable factorization.
    try:
        L = np.linalg.cholesky(cov_matrix + 1e-10 * np.eye(n_assets))
    except np.linalg.LinAlgError:
        return {"error": "Covariance matrix is not positive definite"}

    total_value = sum(
        h["shares"] * _latest_price(daily_data.get(h["symbol"], []))
        for h in holdings
    )
    if total_value <= 0:
        return {"error": "Portfolio value is zero"}

    rng = np.random.default_rng(seed=42)

    # iid Student t draws then correlated via L. Scale factor sqrt((nu-2)/nu)
    # makes the resulting covariance match cov_matrix exactly.
    scale = math.sqrt(max(nu - 2.0, 1e-6) / nu) if nu > 2 else 1.0
    z = rng.standard_t(df=nu, size=(n_simulations, horizon_days, n_assets)) * scale

    # Apply the Cholesky factor day by day. Vectorised over (sims, days).
    # epsilon[s, d, :] = L @ z[s, d, :]
    correlated = z @ L.T
    daily_log_rets = mean_vector + correlated  # shape (sims, days, assets)

    # Portfolio daily log return is the weight dot product.
    port_daily_log = daily_log_rets @ weights  # (sims, days)
    cumulative_log = np.sum(port_daily_log, axis=1)
    cumulative_simple = np.exp(cumulative_log) - 1.0  # fraction
    pnl = total_value * cumulative_simple

    final_returns_pct = cumulative_simple * 100

    var_95 = float(np.percentile(final_returns_pct, 5))
    var_99 = float(np.percentile(final_returns_pct, 1))
    tail_5 = final_returns_pct[final_returns_pct <= var_95]
    tail_1 = final_returns_pct[final_returns_pct <= var_99]
    cvar_95 = float(np.mean(tail_5)) if tail_5.size else var_95
    cvar_99 = float(np.mean(tail_1)) if tail_1.size else var_99

    # Percentile fan chart for the visualization.
    cum_paths = np.exp(np.cumsum(port_daily_log, axis=1))
    all_value_paths = total_value * cum_paths
    percentile_paths = {}
    for p in [5, 25, 50, 75, 95]:
        path = np.percentile(all_value_paths, p, axis=0)
        percentile_paths[f"p{p}"] = [round(float(v), 2) for v in path]

    hist_counts, hist_edges = np.histogram(final_returns_pct, bins=50)
    histogram = {
        "counts": hist_counts.tolist(),
        "edges": [round(float(e), 2) for e in hist_edges.tolist()],
    }

    # Diagnostics for the test suite (Test 6) and the info modal.
    historical_corr = np.corrcoef(returns_matrix, rowvar=False)
    if historical_corr.ndim == 0:
        historical_corr = np.array([[1.0]])

    # Reshape simulated daily returns into (sims*days, assets) to extract the
    # marginal correlation structure.
    flat = daily_log_rets.reshape(-1, n_assets)
    simulated_corr = np.corrcoef(flat, rowvar=False)
    if simulated_corr.ndim == 0:
        simulated_corr = np.array([[1.0]])

    return {
        "total_value": round(total_value, 2),
        "horizon_days": horizon_days,
        "n_simulations": n_simulations,
        "method": "cholesky_student_t",
        "student_t_dof": round(nu, 2),
        "symbols": symbols,
        "var_95": round(var_95, 2),
        "var_99": round(var_99, 2),
        "cvar_95": round(cvar_95, 2),
        "cvar_99": round(cvar_99, 2),
        "var_95_dollar": round(total_value * var_95 / 100, 2),
        "var_99_dollar": round(total_value * var_99 / 100, 2),
        "cvar_95_dollar": round(total_value * cvar_95 / 100, 2),
        "cvar_99_dollar": round(total_value * cvar_99 / 100, 2),
        "expected_return": round(float(np.mean(final_returns_pct)), 2),
        "median_return": round(float(np.median(final_returns_pct)), 2),
        "best_case": round(float(np.max(final_returns_pct)), 2),
        "worst_case": round(float(np.min(final_returns_pct)), 2),
        "histogram": histogram,
        "percentile_paths": percentile_paths,
        "debug_historical_correlation": historical_corr.tolist(),
        "debug_simulated_correlation": simulated_corr.tolist(),
    }


# ── Optimizer (spec module 8) ────────────────────────────────

def efficient_frontier(
    daily_data: dict[str, list[dict]],
    holdings: list[dict],
    risk_free_rate: float = 0.0435,
    n_points: int = 50,
    weight_min: float = 0.05,
    weight_max: float = 0.60,
) -> dict:
    """Efficient frontier with box constraints and Black Litterman style means.

    Expected returns are not the raw historical means. Instead the implied
    equilibrium returns are computed from the current market cap (or value)
    weights, then blended with the historical mean. This stops the optimizer
    producing the corner solution that the v4 dashboard suffered from.
    """
    symbols = [h["symbol"] for h in holdings]
    returns_df = _build_returns_dataframe(daily_data, symbols)

    if returns_df is None or returns_df.shape[1] < 2:
        return {"error": "Need at least 2 holdings with price data for frontier"}

    if len(returns_df) < 30:
        return {"error": "Insufficient data points for optimization"}

    try:
        from pypfopt import EfficientFrontier, risk_models, expected_returns

        # Annualised covariance with Ledoit Wolf shrinkage for stability.
        S = risk_models.CovarianceShrinkage(returns_df, frequency=TRADING_DAYS_STOCKS).ledoit_wolf()

        # Current value weights.
        total_value = 0.0
        current_weights = {}
        for h in holdings:
            price = _latest_price(daily_data.get(h["symbol"], []))
            val = h["shares"] * price
            current_weights[h["symbol"]] = val
            total_value += val
        if total_value > 0:
            current_weights = {k: v / total_value for k, v in current_weights.items()}

        # Black Litterman style implied equilibrium returns.
        # Pi = lambda * Sigma * w_market with lambda = 2.5 risk aversion.
        cw_array = np.array([current_weights.get(s, 1.0 / len(symbols)) for s in returns_df.columns])
        risk_aversion = 2.5
        pi = risk_aversion * S.values @ cw_array

        # Blend with historical mean to stabilise. Half weight each.
        mu_hist = expected_returns.mean_historical_return(
            returns_df, compounding=True, frequency=TRADING_DAYS_STOCKS
        ).values
        mu_blend = 0.5 * pi + 0.5 * mu_hist
        mu_series = pd.Series(mu_blend, index=returns_df.columns)

        n_assets = len(returns_df.columns)
        eff_min = max(weight_min, 0.0)
        eff_max = min(weight_max, 1.0)
        if eff_min * n_assets > 1.0:
            eff_min = 1.0 / (n_assets * 2)
        if eff_max * n_assets < 1.0:
            eff_max = 1.0 / n_assets

        # Current portfolio performance.
        cw_aligned = np.array([current_weights.get(s, 0) for s in returns_df.columns])
        current_ret = float(cw_aligned @ mu_series.values)
        current_vol = float(math.sqrt(cw_aligned @ S.values @ cw_aligned))

        # Max Sharpe.
        ef_sharpe = EfficientFrontier(mu_series, S, weight_bounds=(eff_min, eff_max))
        ef_sharpe.max_sharpe(risk_free_rate=risk_free_rate)
        sharpe_weights = ef_sharpe.clean_weights()
        sharpe_perf = ef_sharpe.portfolio_performance(risk_free_rate=risk_free_rate)

        # Min vol.
        ef_min_vol = EfficientFrontier(mu_series, S, weight_bounds=(eff_min, eff_max))
        ef_min_vol.min_volatility()
        min_vol_weights = ef_min_vol.clean_weights()
        min_vol_perf = ef_min_vol.portfolio_performance(risk_free_rate=risk_free_rate)

        # Frontier sweep.
        frontier_points = []
        min_ret = float(min_vol_perf[0])
        max_ret = float(sharpe_perf[0]) * 1.5
        target_returns = np.linspace(min_ret, max_ret, n_points)
        for target in target_returns:
            try:
                ef_point = EfficientFrontier(mu_series, S, weight_bounds=(eff_min, eff_max))
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
            "constraints": {
                "weight_min_pct": round(eff_min * 100, 2),
                "weight_max_pct": round(eff_max * 100, 2),
            },
            "expected_returns_method": "black_litterman_blended",
            "covariance_method": "ledoit_wolf_shrunk",
            "symbols": list(returns_df.columns),
        }

    except Exception as e:
        logger.error("Efficient frontier calculation failed: %s", e)
        return {"error": str(e)}


# ── Correlation (spec module 9) ──────────────────────────────

def correlation_matrix(
    daily_data: dict[str, list[dict]],
    symbols: list[str],
) -> dict:
    """Pairwise correlation plus 60 day rolling correlation (spec item 18)."""
    returns_df = _build_returns_dataframe(daily_data, symbols)

    if returns_df is None or returns_df.shape[1] < 2:
        return {"error": "Need at least 2 holdings with data"}

    log_returns_df = np.log(returns_df / returns_df.shift(1)).dropna()
    if log_returns_df.shape[0] < 5:
        return {"error": "Need more data for correlation"}

    corr = log_returns_df.corr()
    labels = list(corr.columns)
    matrix = [[round(float(corr.iloc[i, j]), 3) for j in range(len(labels))] for i in range(len(labels))]

    n = len(labels)
    if n > 1:
        off_diag = [corr.iloc[i, j] for i in range(n) for j in range(n) if i != j]
        avg_corr = float(np.mean(off_diag))
    else:
        avg_corr = 1.0

    # 60 day rolling correlation for the first pair (used for the sparkline chart).
    rolling = {}
    if n >= 2 and len(log_returns_df) > 60:
        for i in range(n):
            for j in range(i + 1, n):
                key = f"{labels[i]}_{labels[j]}"
                series = log_returns_df.iloc[:, i].rolling(60).corr(log_returns_df.iloc[:, j])
                series = series.dropna()
                rolling[key] = {
                    "dates": [d.strftime("%Y-%m-%d") for d in series.index],
                    "values": [round(float(v), 3) for v in series.values],
                }

    return {
        "labels": labels,
        "matrix": matrix,
        "avg_correlation": round(avg_corr, 3),
        "interpretation": _interpret_correlation(avg_corr),
        "rolling_60d": rolling,
        "window_days": 252,
    }


def _interpret_correlation(avg: float) -> str:
    if avg > 0.7:
        return "Very high. Holdings move together. Diversification benefit is weak."
    elif avg > 0.5:
        return "Moderate to high. Some diversification but concentrated risk remains."
    elif avg > 0.3:
        return "Moderate. Reasonable diversification across holdings."
    elif avg > 0.0:
        return "Low. Good diversification. Holdings behave fairly independently."
    else:
        return "Negative. Excellent diversification. Holdings offset each other."


# ── Stress testing (spec module 10) ──────────────────────────

HISTORICAL_SCENARIOS = {
    "2008_gfc": {
        "name": "2008 Global Financial Crisis",
        "description": "Sept to Nov 2008. Lehman collapse and banking crisis.",
        "spy_return": -0.389,
        "period": "2008 09 01 to 2009 03 09",
    },
    "covid_crash": {
        "name": "COVID 19 Crash",
        "description": "Feb to Mar 2020. Pandemic selloff.",
        "spy_return": -0.337,
        "period": "2020 02 19 to 2020 03 23",
    },
    "2022_rate_hikes": {
        "name": "2022 Rate Hike Selloff",
        "description": "Jan to Oct 2022. Aggressive Fed tightening.",
        "spy_return": -0.252,
        "period": "2022 01 03 to 2022 10 12",
    },
    "dot_com": {
        "name": "Dot Com Bust",
        "description": "Mar 2000 to Oct 2002. Tech bubble burst.",
        "spy_return": -0.491,
        "period": "2000 03 24 to 2002 10 09",
    },
    "flash_crash_2010": {
        "name": "2010 Flash Crash",
        "description": "May 6 2010. Sudden 9 percent drop in minutes.",
        "spy_return": -0.069,
        "period": "2010 05 06",
    },
}


def stress_test(
    daily_data: dict[str, list[dict]],
    holdings: list[dict],
    custom_shock_pct: Optional[float] = None,
    market_data: Optional[list[dict]] = None,
    loss_threshold_pct: float = 20.0,
) -> dict:
    """Beta adjusted stress test using the canonical OLS beta against SPY.

    Also returns a reverse stress test: what market drop produces a given
    portfolio loss threshold (default 20 percent).
    """
    weights, returns_matrix, valid_symbols = _build_portfolio_matrix(daily_data, holdings)
    if returns_matrix is None:
        return {"error": "Insufficient data for stress testing"}

    total_value = sum(
        h["shares"] * _latest_price(daily_data.get(h["symbol"], []))
        for h in holdings
    )

    market_log = np.array([])
    if market_data:
        market_log = log_returns_from_prices([d["close"] for d in market_data])

    # Per holding beta against SPY using the canonical OLS beta source.
    betas = {}
    for i, sym in enumerate(valid_symbols):
        stock_log = returns_matrix[:, i]
        if market_log.size:
            b = beta_ols(stock_log, market_log)
            betas[sym] = float(b) if b is not None else 1.0
        else:
            # Fall back to portfolio beta if SPY missing.
            port_returns = returns_matrix @ weights
            cov = np.cov(stock_log, port_returns, ddof=1)[0, 1]
            var = np.var(port_returns, ddof=1)
            betas[sym] = float(cov / var) if var > 0 else 1.0

    portfolio_beta = float(np.sum(weights * np.array([betas.get(s, 1.0) for s in valid_symbols])))

    results = []
    for key, scenario in HISTORICAL_SCENARIOS.items():
        market_drop = scenario["spy_return"]
        portfolio_loss = portfolio_beta * market_drop
        dollar_loss = total_value * portfolio_loss

        per_holding = []
        for i, sym in enumerate(valid_symbols):
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

    if custom_shock_pct is not None:
        shock = custom_shock_pct / 100
        portfolio_loss = portfolio_beta * shock
        results.append({
            "scenario": "custom",
            "name": f"Custom shock {custom_shock_pct} percent",
            "description": f"User defined market move of {custom_shock_pct} percent.",
            "period": "Hypothetical",
            "market_return_pct": custom_shock_pct,
            "portfolio_return_pct": round(portfolio_loss * 100, 1),
            "portfolio_loss_dollar": round(total_value * portfolio_loss, 2),
            "per_holding": [],
        })

    # Reverse stress test: what market drop produces a given portfolio loss?
    reverse = None
    if portfolio_beta != 0:
        market_drop_needed = -loss_threshold_pct / portfolio_beta
        reverse = {
            "loss_threshold_pct": loss_threshold_pct,
            "market_drop_pct_needed": round(market_drop_needed, 2),
            "portfolio_beta": round(portfolio_beta, 4),
            "explanation": (
                f"With a portfolio beta of {portfolio_beta:.2f}, the market would have to "
                f"drop by {abs(market_drop_needed):.1f} percent to produce a "
                f"{loss_threshold_pct:.0f} percent portfolio loss."
            ),
        }

    return {
        "total_value": round(total_value, 2),
        "scenarios": results,
        "betas": {k: round(v, 4) for k, v in betas.items()},
        "portfolio_beta": round(portfolio_beta, 4),
        "reverse_stress_test": reverse,
        "beta_method": "ols_252d_vs_spy",
    }


# ── Helpers ──────────────────────────────────────────────────

def _latest_price(data: list[dict]) -> float:
    if data and len(data) > 0:
        return float(data[0].get("close", 0))
    return 0.0


def _build_portfolio_matrix(
    daily_data: dict[str, list[dict]],
    holdings: list[dict],
):
    """Build (weights, log_returns_matrix, symbols) aligned by length.

    Returns (None, None, []) if there is not enough data.
    """
    symbols = [h["symbol"] for h in holdings]
    all_returns = {}
    total_value = 0.0
    values = {}

    for h in holdings:
        sym = h["symbol"]
        data = daily_data.get(sym, [])
        if not data:
            continue

        closes = [d["close"] for d in data]  # newest first
        if len(closes) < 2:
            continue

        log_rets = log_returns_from_prices(closes)
        all_returns[sym] = log_rets
        price = closes[0]
        val = h["shares"] * price
        values[sym] = val
        total_value += val

    if not all_returns or total_value <= 0:
        return None, None, []

    valid_symbols = [s for s in symbols if s in all_returns]
    min_len = min(all_returns[s].size for s in valid_symbols)
    if min_len < 10:
        return None, None, []

    returns_matrix = np.column_stack([all_returns[s][-min_len:] for s in valid_symbols])
    weights = np.array([values.get(s, 0) / total_value for s in valid_symbols], dtype=float)

    return weights, returns_matrix, valid_symbols


def _build_returns_dataframe(
    daily_data: dict[str, list[dict]],
    symbols: list[str],
) -> Optional[pd.DataFrame]:
    """Build a DataFrame of close prices aligned by date for all symbols."""
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


# ── What-If Trade Simulator (feature 1) ──────────────────────

def what_if_simulation(
    daily_data: dict[str, list[dict]],
    current_holdings: list[dict],
    trade_symbol: str,
    trade_shares: float,
    trade_action: str,
    risk_free: float = 0.0435,
    market_data: list[dict] | None = None,
) -> dict:
    """Simulate adding or removing a position and return metric deltas.

    trade_action is 'buy' or 'sell'. Returns before/after/delta for
    Sharpe, volatility, beta, HHI, and VaR (95%, parametric).
    """
    from backend.portfolio import (
        portfolio_volatility_full,
        weighted_portfolio_beta,
    )

    def _metrics(hlds, dd):
        weights, ret_mat, syms = _build_portfolio_matrix(dd, hlds)
        if ret_mat is None or ret_mat.shape[0] < 20:
            return None

        # Market returns for beta
        mkt_log = np.array([])
        if market_data:
            mkt_log = log_returns_from_prices([d["close"] for d in market_data])

        n = ret_mat.shape[1]
        cov = np.cov(ret_mat, rowvar=False, ddof=1)
        if cov.ndim == 0:
            cov = np.array([[float(cov)]])

        vol = float(np.sqrt(weights @ cov @ weights)) * math.sqrt(TRADING_DAYS_STOCKS)
        mean_ret = float(np.mean(ret_mat @ weights)) * TRADING_DAYS_STOCKS

        sharpe = (mean_ret - risk_free) / vol if vol > 0 else 0.0

        betas = {}
        for i, sym in enumerate(syms):
            if mkt_log.size:
                b = beta_ols(ret_mat[:, i], mkt_log)
                betas[sym] = float(b) if b is not None else 1.0
            else:
                betas[sym] = 1.0
        port_beta = float(np.sum(weights * np.array([betas.get(s, 1.0) for s in syms])))

        hhi = float(np.sum(weights ** 2))
        eff_n = 1.0 / hhi if hhi > 0 else len(syms)

        # Parametric VaR 95
        var_95 = -(mean_ret / TRADING_DAYS_STOCKS * 30 - 1.645 * vol / math.sqrt(TRADING_DAYS_STOCKS) * math.sqrt(30)) * 100

        total_val = sum(
            h["shares"] * _latest_price(dd.get(h["symbol"], []))
            for h in hlds
        )

        return {
            "sharpe": round(sharpe, 4),
            "volatility": round(vol, 4),
            "beta": round(port_beta, 4),
            "hhi": round(hhi, 4),
            "effective_n": round(eff_n, 2),
            "var_95_pct": round(var_95, 2),
            "total_value": round(total_val, 2),
            "weights": {s: round(float(w), 4) for s, w in zip(syms, weights)},
        }

    before = _metrics(current_holdings, daily_data)
    if before is None:
        return {"error": "Insufficient data for current portfolio"}

    # Build modified holdings
    modified = [dict(h) for h in current_holdings]
    found = False
    for h in modified:
        if h["symbol"].upper() == trade_symbol.upper():
            found = True
            if trade_action == "sell":
                h["shares"] = max(0, h["shares"] - trade_shares)
            else:
                h["shares"] += trade_shares
            break

    if not found and trade_action == "buy":
        price = _latest_price(daily_data.get(trade_symbol.upper(), []))
        modified.append({
            "symbol": trade_symbol.upper(),
            "shares": trade_shares,
            "avg_cost": price,
        })

    modified = [h for h in modified if h["shares"] > 0]
    if not modified:
        return {"error": "Resulting portfolio would be empty"}

    after = _metrics(modified, daily_data)
    if after is None:
        return {"error": "Insufficient data for modified portfolio"}

    delta = {}
    for k in before:
        if k in ("weights", "total_value"):
            continue
        delta[k] = round(after[k] - before[k], 4)

    return {
        "trade": {"symbol": trade_symbol.upper(), "shares": trade_shares, "action": trade_action},
        "before": before,
        "after": after,
        "delta": delta,
    }


# ── Regime-Aware Risk Engine (feature 2) ──────────────────────

def regime_detection(
    daily_data: dict[str, list[dict]],
    holdings: list[dict],
    market_data: list[dict] | None = None,
    window: int = 21,
) -> dict:
    """Detect volatility regime and compute regime-conditional VaR.

    Rolling 21-day realised volatility of the portfolio classifies into:
    - low:      annualised vol < 12%
    - normal:   12% to 20%
    - elevated: 20% to 30%
    - crisis:   > 30%

    Returns rolling vol history, current regime, and regime-conditional VaR.
    """
    weights, ret_mat, syms = _build_portfolio_matrix(daily_data, holdings)
    if ret_mat is None or ret_mat.shape[0] < window + 10:
        return {"error": "Insufficient data for regime detection (need 30+ days)"}

    port_rets = ret_mat @ weights  # daily log returns

    # Rolling realised vol (annualised)
    rolling_vol = []
    dates = []

    # Try to get dates from the first symbol's data
    first_sym = syms[0] if syms else None
    sym_data = daily_data.get(first_sym, []) if first_sym else []
    all_dates = [d.get("date", "") for d in sym_data]
    all_dates.reverse()  # oldest first

    for i in range(window, len(port_rets)):
        chunk = port_rets[i - window:i]
        vol = float(np.std(chunk, ddof=1)) * math.sqrt(TRADING_DAYS_STOCKS)
        rolling_vol.append(round(vol * 100, 2))
        if i < len(all_dates):
            dates.append(all_dates[i])
        else:
            dates.append(f"t-{len(port_rets) - i}")

    if not rolling_vol:
        return {"error": "Not enough data for rolling volatility"}

    current_vol = rolling_vol[-1]

    def _classify(v):
        if v < 12:
            return "low"
        elif v < 20:
            return "normal"
        elif v < 30:
            return "elevated"
        else:
            return "crisis"

    current_regime = _classify(current_vol)

    # Regime history
    regime_history = [_classify(v) for v in rolling_vol]
    regime_counts = {}
    for r in regime_history:
        regime_counts[r] = regime_counts.get(r, 0) + 1

    # Regime-conditional VaR: compute VaR using only returns from the current regime
    regime_returns = []
    for i in range(window, len(port_rets)):
        chunk = port_rets[i - window:i]
        vol = float(np.std(chunk, ddof=1)) * math.sqrt(TRADING_DAYS_STOCKS)
        r_class = _classify(vol * 100)
        if r_class == current_regime:
            regime_returns.append(float(port_rets[i]))

    regime_returns = np.array(regime_returns) if regime_returns else port_rets

    # Parametric VaR from regime-conditional returns
    mu = float(np.mean(regime_returns)) * TRADING_DAYS_STOCKS
    sigma = float(np.std(regime_returns, ddof=1)) * math.sqrt(TRADING_DAYS_STOCKS)
    var_95_regime = -(mu / TRADING_DAYS_STOCKS * 30 - 1.645 * sigma / math.sqrt(TRADING_DAYS_STOCKS) * math.sqrt(30)) * 100

    # Unconditional VaR for comparison
    mu_all = float(np.mean(port_rets)) * TRADING_DAYS_STOCKS
    sigma_all = float(np.std(port_rets, ddof=1)) * math.sqrt(TRADING_DAYS_STOCKS)
    var_95_unconditional = -(mu_all / TRADING_DAYS_STOCKS * 30 - 1.645 * sigma_all / math.sqrt(TRADING_DAYS_STOCKS) * math.sqrt(30)) * 100

    # Regime transition probabilities
    transitions = {}
    for i in range(1, len(regime_history)):
        prev = regime_history[i - 1]
        curr = regime_history[i]
        key = f"{prev}_to_{curr}"
        transitions[key] = transitions.get(key, 0) + 1

    total_transitions = len(regime_history) - 1
    if total_transitions > 0:
        transitions = {k: round(v / total_transitions, 4) for k, v in transitions.items()}

    return {
        "current_regime": current_regime,
        "current_vol_pct": round(current_vol, 2),
        "regime_counts": regime_counts,
        "regime_pct": {k: round(v / len(regime_history) * 100, 1) for k, v in regime_counts.items()},
        "var_95_regime_conditional": round(var_95_regime, 2),
        "var_95_unconditional": round(var_95_unconditional, 2),
        "regime_vol_annualized": round(sigma * 100, 2),
        "transitions": transitions,
        "rolling_vol": rolling_vol[-60:],  # last 60 data points for chart
        "rolling_dates": dates[-60:],
        "window_days": window,
    }


# ── Data Quality Dashboard (feature 4) ────────────────────────

def data_quality_report(
    daily_data: dict[str, list[dict]],
    symbols: list[str],
) -> dict:
    """Per-ticker data quality assessment.

    Reports expected vs actual bars, missing percentage, zero volume days,
    staleness, and gap detection (weekday gaps > 1 business day).
    """
    from datetime import datetime, timedelta

    reports = {}
    for sym in symbols:
        data = daily_data.get(sym, [])
        if not data:
            reports[sym] = {
                "status": "no_data",
                "actual_bars": 0,
                "expected_bars": 0,
                "missing_pct": 100.0,
                "zero_volume_days": 0,
                "staleness_days": None,
                "gaps": [],
                "quality_score": 0,
            }
            continue

        # Data is newest-first
        dates_str = [d.get("date", "") for d in data]
        dates_parsed = []
        for ds in dates_str:
            try:
                dates_parsed.append(datetime.strptime(ds[:10], "%Y-%m-%d"))
            except (ValueError, TypeError):
                pass

        if not dates_parsed:
            reports[sym] = {
                "status": "no_valid_dates",
                "actual_bars": len(data),
                "expected_bars": 0,
                "missing_pct": 100.0,
                "zero_volume_days": 0,
                "staleness_days": None,
                "gaps": [],
                "quality_score": 0,
            }
            continue

        newest = dates_parsed[0]
        oldest = dates_parsed[-1]
        actual_bars = len(data)

        # Expected business days between oldest and newest
        is_crypto = "-USD" in sym
        if is_crypto:
            expected_bars = (newest - oldest).days + 1
        else:
            # Count weekdays
            expected_bars = int(np.busday_count(
                oldest.strftime("%Y-%m-%d"),
                (newest + timedelta(days=1)).strftime("%Y-%m-%d"),
            ))

        missing_pct = max(0, (1 - actual_bars / max(expected_bars, 1)) * 100)

        # Zero volume days
        zero_vol = sum(1 for d in data if d.get("volume", 1) == 0)

        # Staleness
        today = datetime.now()
        staleness = (today - newest).days

        # Gap detection (sorted oldest to newest)
        sorted_dates = sorted(dates_parsed)
        gaps = []
        for i in range(1, len(sorted_dates)):
            delta = (sorted_dates[i] - sorted_dates[i - 1]).days
            threshold = 4 if not is_crypto else 2
            if delta > threshold:
                gaps.append({
                    "from": sorted_dates[i - 1].strftime("%Y-%m-%d"),
                    "to": sorted_dates[i].strftime("%Y-%m-%d"),
                    "days": delta,
                })

        # Quality score (0-100)
        completeness = min(actual_bars / max(expected_bars, 1), 1.0) * 40
        freshness = max(0, 30 - staleness) / 30 * 30  # 30 points for being fresh
        vol_quality = max(0, (1 - zero_vol / max(actual_bars, 1))) * 15
        gap_penalty = min(len(gaps) * 5, 15)
        quality_score = max(0, min(100, completeness + freshness + vol_quality + (15 - gap_penalty)))

        reports[sym] = {
            "status": "ok",
            "actual_bars": actual_bars,
            "expected_bars": expected_bars,
            "missing_pct": round(missing_pct, 1),
            "zero_volume_days": zero_vol,
            "staleness_days": staleness,
            "latest_date": newest.strftime("%Y-%m-%d"),
            "oldest_date": oldest.strftime("%Y-%m-%d"),
            "gaps": gaps[:5],  # cap at 5 gaps
            "quality_score": round(quality_score, 1),
        }

    # Overall quality
    scores = [r["quality_score"] for r in reports.values() if r.get("quality_score")]
    overall = round(sum(scores) / len(scores), 1) if scores else 0

    return {
        "tickers": reports,
        "overall_score": overall,
        "ticker_count": len(symbols),
    }
