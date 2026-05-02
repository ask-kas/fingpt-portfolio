"""
portfolio.py — Portfolio analytics engine (v5 spec rebuild).

All statistical calculations use log returns and full covariance matrices.
Beta is computed via OLS regression on a single 252 day window.
Risk free rate is the live 10Y Treasury, fetched from FRED upstream.

Public surface:
    analyze_portfolio        full per holding plus portfolio summary
    calculate_max_drawdown   full history MDD on a newest first price list
    calculate_rsi            Wilder smoothed RSI 14
    portfolio_volatility_full   sqrt(w^T Sigma w), used by tests
    weighted_portfolio_beta     sum(w_i beta_i), used by tests
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

# Trading day conventions
TRADING_DAYS_STOCKS = 252
TRADING_DAYS_CRYPTO = 365

# Default minimum acceptable return for Sortino, set to zero so the
# downside leg only penalises real losses (spec module 2 step 2).
DEFAULT_MAR = 0.0


# ── Return helpers ──────────────────────────────────────────

def log_returns_from_prices(prices_newest_first: list[float]) -> np.ndarray:
    """Compute daily log returns. Input is newest first, output is oldest first.

    r_t = ln(P_t / P_{t minus 1})
    """
    if not prices_newest_first or len(prices_newest_first) < 2:
        return np.array([])
    p = np.array(list(reversed(prices_newest_first)), dtype=float)
    p = np.clip(p, 1e-9, None)
    return np.diff(np.log(p))


def simple_returns_from_prices(prices_newest_first: list[float]) -> np.ndarray:
    """Simple percentage returns, oldest first output."""
    if not prices_newest_first or len(prices_newest_first) < 2:
        return np.array([])
    p = np.array(list(reversed(prices_newest_first)), dtype=float)
    return (p[1:] - p[:-1]) / p[:-1]


def calculate_returns(prices: list[float]) -> list[float]:
    """Backwards compatible wrapper that returns a Python list of log returns."""
    return list(log_returns_from_prices(prices))


def annualized_volatility(log_rets: np.ndarray, trading_days: int = TRADING_DAYS_STOCKS) -> float:
    """Sample (Bessel corrected) std dev of log returns, annualised by sqrt(T)."""
    if log_rets.size < 2:
        return 0.0
    sigma_daily = float(np.std(log_rets, ddof=1))
    return float(sigma_daily * math.sqrt(trading_days))


def calculate_volatility(returns, annualize: bool = True, trading_days: int = TRADING_DAYS_STOCKS) -> float:
    """Backwards compatible volatility wrapper. Accepts numpy or list."""
    arr = np.asarray(returns, dtype=float)
    if arr.size < 2:
        return 0.0
    sigma = float(np.std(arr, ddof=1))
    if annualize:
        sigma *= math.sqrt(trading_days)
    return round(sigma, 4)


def annualized_mean_return(log_rets: np.ndarray, trading_days: int = TRADING_DAYS_STOCKS) -> float:
    """Geometric annualised return from a series of daily log returns.

    R_annual = exp(mean_log_return * trading_days) minus 1
    """
    if log_rets.size == 0:
        return 0.0
    return float(math.exp(float(np.mean(log_rets)) * trading_days) - 1)


# ── Risk adjusted return ratios ─────────────────────────────

def sharpe_ratio(log_rets: np.ndarray, rf_annual: float, trading_days: int = TRADING_DAYS_STOCKS) -> float:
    """Annualised Sharpe ratio computed from log returns.

    Sharpe = (R_p_annual minus Rf) / sigma_p_annual
    """
    if log_rets.size < 2:
        return 0.0
    r_annual = annualized_mean_return(log_rets, trading_days)
    sigma_annual = annualized_volatility(log_rets, trading_days)
    if sigma_annual == 0:
        return 0.0
    return float((r_annual - rf_annual) / sigma_annual)


def calculate_sharpe(returns, risk_free_rate: float = 0.0435, trading_days: int = TRADING_DAYS_STOCKS) -> float:
    arr = np.asarray(returns, dtype=float)
    return round(sharpe_ratio(arr, risk_free_rate, trading_days), 4)


def downside_deviation(log_rets: np.ndarray, mar_daily: float = 0.0) -> float:
    """Downside deviation. Only returns below MAR are squared.

    sigma_downside = sqrt(sum(min(r minus MAR, 0)^2) / n)
    """
    if log_rets.size == 0:
        return 0.0
    diffs = log_rets - mar_daily
    downside = np.minimum(diffs, 0.0)
    return float(math.sqrt(float(np.sum(downside * downside)) / log_rets.size))


def sortino_ratio(log_rets: np.ndarray, rf_annual: float, trading_days: int = TRADING_DAYS_STOCKS) -> float:
    """Annualised Sortino ratio. MAR is set to the daily risk free rate."""
    if log_rets.size < 2:
        return 0.0
    mar_daily = rf_annual / trading_days
    dd_daily = downside_deviation(log_rets, mar_daily)
    if dd_daily == 0:
        return 0.0
    dd_annual = dd_daily * math.sqrt(trading_days)
    r_annual = annualized_mean_return(log_rets, trading_days)
    return float((r_annual - rf_annual) / dd_annual)


def calculate_sortino(returns, risk_free_rate: float = 0.0435, trading_days: int = TRADING_DAYS_STOCKS) -> float:
    arr = np.asarray(returns, dtype=float)
    return round(sortino_ratio(arr, risk_free_rate, trading_days), 4)


def calmar_ratio(log_rets: np.ndarray, prices_newest_first: list[float], trading_days: int = TRADING_DAYS_STOCKS) -> float:
    """Calmar = annualised return / max drawdown."""
    if log_rets.size == 0 or not prices_newest_first:
        return 0.0
    r_annual = annualized_mean_return(log_rets, trading_days)
    mdd = calculate_max_drawdown(prices_newest_first)
    if mdd == 0:
        return 0.0
    return float(r_annual / mdd)


def calculate_calmar(returns, prices, trading_days: int = TRADING_DAYS_STOCKS) -> float:
    arr = np.asarray(returns, dtype=float)
    return round(calmar_ratio(arr, prices, trading_days), 4)


def treynor_ratio(log_rets: np.ndarray, beta: float, rf_annual: float, trading_days: int = TRADING_DAYS_STOCKS) -> float:
    """Treynor = (R_p_annual minus Rf) / beta."""
    if log_rets.size == 0 or beta == 0:
        return 0.0
    r_annual = annualized_mean_return(log_rets, trading_days)
    return float((r_annual - rf_annual) / beta)


def calculate_treynor(returns, beta: float, risk_free_rate: float = 0.0435, trading_days: int = TRADING_DAYS_STOCKS) -> float:
    arr = np.asarray(returns, dtype=float)
    return round(treynor_ratio(arr, beta, risk_free_rate, trading_days), 4)


def information_ratio(port_log_rets: np.ndarray, bench_log_rets: np.ndarray, trading_days: int = TRADING_DAYS_STOCKS) -> float:
    """Information ratio = annualised excess return / tracking error."""
    n = min(port_log_rets.size, bench_log_rets.size)
    if n < 2:
        return 0.0
    p = port_log_rets[-n:]
    b = bench_log_rets[-n:]
    diff = p - b
    te_daily = float(np.std(diff, ddof=1))
    if te_daily == 0:
        return 0.0
    te_annual = te_daily * math.sqrt(trading_days)
    excess_annual = float(np.mean(diff)) * trading_days
    return float(excess_annual / te_annual)


# ── Beta and alpha (single OLS source of truth) ──────────────

def beta_ols(asset_log_rets: np.ndarray, market_log_rets: np.ndarray, lookback: int = TRADING_DAYS_STOCKS) -> Optional[float]:
    """OLS regression beta on daily log returns over the trailing lookback window.

    R_asset = alpha + beta * R_market + epsilon
    beta = Cov(R_asset, R_market) / Var(R_market)
    """
    n = min(asset_log_rets.size, market_log_rets.size)
    if n < 30:
        return None
    a = asset_log_rets[-n:][-lookback:]
    m = market_log_rets[-n:][-lookback:]
    if a.size < 30:
        return None
    var_m = float(np.var(m, ddof=1))
    if var_m == 0:
        return None
    cov = float(np.cov(a, m, ddof=1)[0, 1])
    return cov / var_m


def calculate_beta(stock_returns, market_returns) -> float:
    a = np.asarray(stock_returns, dtype=float)
    m = np.asarray(market_returns, dtype=float)
    b = beta_ols(a, m)
    return round(b, 4) if b is not None else 1.0


def jensen_alpha(asset_log_rets: np.ndarray, market_log_rets: np.ndarray, beta: float, rf_annual: float, trading_days: int = TRADING_DAYS_STOCKS) -> float:
    """Jensen alpha annualised: alpha_J = R_p minus (Rf + beta (R_m minus Rf))."""
    if asset_log_rets.size == 0 or market_log_rets.size == 0:
        return 0.0
    r_asset_annual = annualized_mean_return(asset_log_rets, trading_days)
    r_market_annual = annualized_mean_return(market_log_rets, trading_days)
    return float(r_asset_annual - (rf_annual + beta * (r_market_annual - rf_annual)))


def calculate_alpha(stock_returns, market_returns, risk_free_rate: float = 0.0435, trading_days: int = TRADING_DAYS_STOCKS) -> float:
    a = np.asarray(stock_returns, dtype=float)
    m = np.asarray(market_returns, dtype=float)
    b = beta_ols(a, m)
    if b is None:
        return 0.0
    return round(jensen_alpha(a, m, b, risk_free_rate, trading_days), 4)


def weighted_portfolio_beta(weights: np.ndarray, betas: np.ndarray) -> float:
    """Portfolio beta = sum(w_i beta_i)."""
    w = np.asarray(weights, dtype=float)
    b = np.asarray(betas, dtype=float)
    return float(np.sum(w * b))


# ── Drawdown ────────────────────────────────────────────────

def calculate_max_drawdown(prices_newest_first: list[float]) -> float:
    """Maximum drawdown over the entire history.

    Spec module 5: scans the running peak across every price in the
    series. Input is newest first, internally reversed to oldest first.
    """
    if not prices_newest_first or len(prices_newest_first) < 2:
        return 0.0
    p = np.array(list(reversed(prices_newest_first)), dtype=float)
    running_peak = np.maximum.accumulate(p)
    drawdowns = np.where(running_peak > 0, (running_peak - p) / running_peak, 0.0)
    return float(round(np.max(drawdowns), 4))


# ── Technical indicators ────────────────────────────────────

def calculate_sma(prices: list[float], window: int = 20) -> float:
    if not prices:
        return 0.0
    subset = prices[:window]
    return round(float(np.mean(subset)), 2)


def calculate_rsi(prices: list[float], period: int = 14) -> float:
    """RSI 14 with Wilder smoothing.

    Step 1: deltas
    Step 2: separate gains and losses
    Step 3: seed averages with the simple mean over the first period
    Step 4: smoothed averages: avg_t = (avg_{t-1} * (period-1) + value_t) / period
    Step 5: RS = avg_gain / avg_loss
    Step 6: RSI = 100 minus 100 / (1 + RS)
    """
    if not prices or len(prices) < period + 1:
        return 50.0
    p = np.array(list(reversed(prices)), dtype=float)
    deltas = np.diff(p)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = float(np.mean(gains[:period]))
    avg_loss = float(np.mean(losses[:period]))

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(float(100 - (100 / (1 + rs))), 2)


def rsi_label(value: float) -> str:
    """Return urgency tag for an RSI value (spec part 1 bug 8)."""
    if value <= 20:
        return "extreme_oversold"
    if value < 30:
        return "oversold"
    if value >= 80:
        return "extreme_overbought"
    if value > 70:
        return "overbought"
    return "neutral"


# ── Diversification metrics (spec module 8) ─────────────────

def herfindahl_index(weights: np.ndarray) -> float:
    w = np.asarray(weights, dtype=float)
    if w.size == 0:
        return 0.0
    s = float(np.sum(w))
    if s <= 0:
        return 0.0
    norm = w / s
    return float(np.sum(norm * norm))


def effective_n(weights: np.ndarray) -> float:
    h = herfindahl_index(weights)
    return float(1.0 / h) if h > 0 else 0.0


def diversification_ratio(weights: np.ndarray, asset_vols_annual: np.ndarray, portfolio_vol_annual: float) -> float:
    """DR = sum(w_i sigma_i) / sigma_portfolio. DR > 1 means correlation reduces risk."""
    if portfolio_vol_annual <= 0:
        return 0.0
    weighted = float(np.sum(np.asarray(weights, dtype=float) * np.asarray(asset_vols_annual, dtype=float)))
    return float(weighted / portfolio_vol_annual)


def diversification_score(weights: list[float]) -> float:
    """Legacy 1 minus HHI score, kept for callers that still expect it."""
    if not weights:
        return 0.0
    arr = np.asarray(weights, dtype=float)
    return round(1.0 - herfindahl_index(arr), 4)


# ── Portfolio level math (full covariance) ──────────────────

def portfolio_volatility_full(weights: np.ndarray, cov_annual: np.ndarray) -> float:
    """sigma_p = sqrt(w^T * Sigma * w). Sigma is already annualised."""
    w = np.asarray(weights, dtype=float)
    sigma = np.asarray(cov_annual, dtype=float)
    var_p = float(w @ sigma @ w)
    if var_p < 0:
        var_p = 0.0
    return float(math.sqrt(var_p))


def covariance_matrix_annual(returns_matrix_oldest_first: np.ndarray, trading_days: int = TRADING_DAYS_STOCKS) -> np.ndarray:
    """Annualised covariance of daily log returns. Columns are assets."""
    if returns_matrix_oldest_first.size == 0:
        return np.zeros((0, 0))
    cov_daily = np.cov(returns_matrix_oldest_first, rowvar=False, ddof=1)
    if cov_daily.ndim == 0:
        cov_daily = np.array([[float(cov_daily)]])
    return cov_daily * trading_days


# ── Tax model (spec module 13) ──────────────────────────────

LTCG_RATE = 0.238  # 20% federal plus 3.8% NIIT for high earners
DIVIDEND_RATE = 0.238


def tax_liability_for_holding(gain: float) -> dict:
    """Long term capital gains tax model. Negative gains return a benefit."""
    if gain >= 0:
        owed = gain * LTCG_RATE
        return {
            "rate_pct": LTCG_RATE * 100,
            "type": "long_term_gain",
            "tax_owed": round(owed, 2),
            "after_tax_gain": round(gain - owed, 2),
            "loss_benefit": 0.0,
        }
    benefit = abs(gain) * LTCG_RATE
    return {
        "rate_pct": LTCG_RATE * 100,
        "type": "harvestable_loss",
        "tax_owed": 0.0,
        "after_tax_gain": round(gain, 2),
        "loss_benefit": round(benefit, 2),
    }


# ── Tariff model for AAPL exposure (spec module 10) ─────────

# Empirical inputs documented in the spec, in billions of dollars.
AAPL_CHINA_COGS_BN = 87.0
AAPL_NET_INCOME_BN = 94.0
AAPL_PE_RATIO = 29.0


def aapl_tariff_impact(weight: float, tariff_rate: float = 0.25, pass_through: float = 0.5) -> dict:
    """Empirical AAPL tariff stress: earnings hit translated to a price hit.

    Step 1: dollar hit to earnings from unabsorbed tariff on China COGS.
        impact_dollar     = tariff_rate * china_cogs * (1 minus pass_through)
    Step 2: percentage hit to net income.
        earnings_drop_pct = impact_dollar / net_income
    Step 3: under a constant P/E assumption, price falls by the same
    percentage as earnings. This is the standard "multiple stays flat"
    translation: P = PE * EPS, so if EPS drops x percent, P drops x percent.
        price_impact_pct  = earnings_drop_pct (negative)
    Step 4: portfolio drag is the position weight times the price move.
        portfolio_drag    = weight * price_impact_pct

    AAPL_PE_RATIO is reported as context only; it does not enter the
    arithmetic because it cancels in the ratio P / EPS.
    """
    impact_bn = tariff_rate * AAPL_CHINA_COGS_BN * (1 - pass_through)
    earnings_drop = impact_bn / AAPL_NET_INCOME_BN  # fraction
    price_drop = -earnings_drop  # constant PE translation
    portfolio_drag = weight * price_drop
    return {
        "tariff_rate_pct": tariff_rate * 100,
        "pass_through_pct": pass_through * 100,
        "earnings_reduction_pct": round(earnings_drop * 100, 2),
        "aapl_price_impact_pct": round(price_drop * 100, 2),
        "portfolio_impact_pct": round(portfolio_drag * 100, 2),
        "assumptions": {
            "china_cogs_bn": AAPL_CHINA_COGS_BN,
            "net_income_bn": AAPL_NET_INCOME_BN,
            "pe_ratio_reference": AAPL_PE_RATIO,
            "translation": "constant P/E",
        },
    }


# ── Helpers used by analyze_portfolio ───────────────────────

def _trading_days_for_symbol(symbol: str) -> int:
    return TRADING_DAYS_CRYPTO if "-USD" in symbol.upper() else TRADING_DAYS_STOCKS


def _align_returns(symbol_to_log_rets: dict[str, np.ndarray], symbols: list[str]) -> np.ndarray:
    """Align all return series to the shortest length, oldest first."""
    valid = [s for s in symbols if s in symbol_to_log_rets and symbol_to_log_rets[s].size >= 2]
    if not valid:
        return np.array([])
    min_len = min(symbol_to_log_rets[s].size for s in valid)
    return np.column_stack([symbol_to_log_rets[s][-min_len:] for s in valid])


def analyze_portfolio(
    holdings: list[dict],
    daily_data: dict[str, list[dict]],
    risk_free_rate: float = 0.0435,
    market_data: Optional[list[dict]] = None,
) -> dict:
    """Full portfolio analysis with v5 spec correctness.

    holdings:    [{"symbol": ..., "shares": ..., "avg_cost": ..., "dividends_per_share": optional}]
    daily_data:  {symbol: [{"date": ..., "close": ...}, ...]}  newest first
    risk_free_rate: annual decimal, sourced from the live 10Y Treasury upstream
    market_data: SPY daily data, newest first
    """
    if not holdings:
        return {"error": "No holdings provided"}

    # Market log returns once, used everywhere beta touches.
    market_log_rets = np.array([])
    if market_data:
        market_closes = [d["close"] for d in market_data]
        market_log_rets = log_returns_from_prices(market_closes)

    symbol_to_log_rets: dict[str, np.ndarray] = {}
    symbol_to_closes: dict[str, list[float]] = {}
    holding_records: list[dict] = []

    portfolio_value = 0.0
    total_cost = 0.0
    total_dividends_received = 0.0

    # First pass: collect prices, log returns, and per holding metrics.
    for h in holdings:
        sym = h["symbol"]
        shares = float(h["shares"])
        avg_cost = float(h["avg_cost"])
        td = _trading_days_for_symbol(sym)

        prices_data = daily_data.get(sym, [])
        if not prices_data:
            holding_records.append({"symbol": sym, "error": "No price data"})
            continue

        latest = prices_data[0]
        closes = [d["close"] for d in prices_data]
        current_price = float(latest["close"])
        latest_date = str(latest.get("date", ""))

        log_rets = log_returns_from_prices(closes)
        symbol_to_log_rets[sym] = log_rets
        symbol_to_closes[sym] = closes

        position_value = current_price * shares
        cost_basis = avg_cost * shares
        portfolio_value += position_value
        total_cost += cost_basis

        # Dividends per share, optional. Used to compute total return.
        dps = float(h.get("dividends_per_share", 0.0) or 0.0)
        dividends_received = dps * shares
        total_dividends_received += dividends_received

        # OLS beta on the trailing 252 day window.
        beta = beta_ols(log_rets, market_log_rets) if market_log_rets.size else None
        alpha = jensen_alpha(log_rets, market_log_rets, beta, risk_free_rate, td) if beta is not None else None

        gain_loss_price = position_value - cost_basis
        gain_loss_pct = (gain_loss_price / cost_basis * 100) if cost_basis else 0.0
        total_return_dollar = gain_loss_price + dividends_received
        total_return_pct = (total_return_dollar / cost_basis * 100) if cost_basis else 0.0

        rsi_value = calculate_rsi(closes, 14)

        holding_records.append({
            "symbol": sym,
            "current_price": round(current_price, 2),
            "latest_date": latest_date,
            "shares": shares,
            "avg_cost": round(avg_cost, 2),
            "position_value": round(position_value, 2),
            "cost_basis": round(cost_basis, 2),
            "dividends_received": round(dividends_received, 2),
            "gain_loss": round(gain_loss_price, 2),
            "gain_loss_pct": round(gain_loss_pct, 2),
            "total_return_dollar": round(total_return_dollar, 2),
            "total_return_pct": round(total_return_pct, 2),
            "volatility": round(annualized_volatility(log_rets, td), 4),
            "sharpe_ratio": round(sharpe_ratio(log_rets, risk_free_rate, td), 4),
            "sortino_ratio": round(sortino_ratio(log_rets, risk_free_rate, td), 4),
            "calmar_ratio": round(calmar_ratio(log_rets, closes, td), 4),
            "max_drawdown": calculate_max_drawdown(closes),
            "beta": round(beta, 4) if beta is not None else None,
            "alpha": round(alpha, 4) if alpha is not None else None,
            "treynor_ratio": round(treynor_ratio(log_rets, beta, risk_free_rate, td), 4) if beta else None,
            "avg_daily_return_pct": round(float(np.mean(log_rets)) * 100, 4) if log_rets.size else 0.0,
            "sma_20": calculate_sma(closes, 20),
            "sma_50": calculate_sma(closes, 50),
            "rsi_14": rsi_value,
            "rsi_label": rsi_label(rsi_value),
            "tax": tax_liability_for_holding(gain_loss_price),
            "lookback_days": int(min(log_rets.size, TRADING_DAYS_STOCKS)),
            "rf_annual_pct": round(risk_free_rate * 100, 3),
        })

    # Second pass: portfolio level metrics using the full covariance matrix.
    valid_records = [r for r in holding_records if "error" not in r]
    symbols_valid = [r["symbol"] for r in valid_records]

    if not symbols_valid or portfolio_value <= 0:
        return {
            "summary": {"error": "No valid holdings to summarise"},
            "holdings": holding_records,
        }

    weights_arr = np.array(
        [r["position_value"] / portfolio_value for r in valid_records],
        dtype=float,
    )

    aligned_returns = _align_returns(symbol_to_log_rets, symbols_valid)
    if aligned_returns.size == 0:
        cov_annual = np.zeros((len(symbols_valid), len(symbols_valid)))
        port_log_rets = np.array([])
    else:
        cov_annual = covariance_matrix_annual(aligned_returns, TRADING_DAYS_STOCKS)
        port_log_rets = aligned_returns @ weights_arr

    portfolio_vol_annual = portfolio_volatility_full(weights_arr, cov_annual)
    asset_vols_annual = np.array([r["volatility"] for r in valid_records], dtype=float)

    port_sharpe = 0.0
    port_sortino = 0.0
    port_alpha = 0.0
    port_beta = None
    port_treynor = 0.0
    port_info_ratio = 0.0
    port_calmar = 0.0
    portfolio_geom_return = 0.0

    if port_log_rets.size:
        portfolio_geom_return = annualized_mean_return(port_log_rets, TRADING_DAYS_STOCKS)
        if portfolio_vol_annual > 0:
            port_sharpe = (portfolio_geom_return - risk_free_rate) / portfolio_vol_annual
        port_sortino = sortino_ratio(port_log_rets, risk_free_rate)

    # Portfolio beta as the weighted sum of holding betas (single source of truth).
    holding_betas = np.array(
        [r.get("beta") if r.get("beta") is not None else 0.0 for r in valid_records],
        dtype=float,
    )
    if market_log_rets.size and any(r.get("beta") is not None for r in valid_records):
        port_beta = weighted_portfolio_beta(weights_arr, holding_betas)
        if port_log_rets.size and market_log_rets.size:
            r_market_annual = annualized_mean_return(market_log_rets, TRADING_DAYS_STOCKS)
            port_alpha = portfolio_geom_return - (risk_free_rate + port_beta * (r_market_annual - risk_free_rate))
            if port_beta != 0:
                port_treynor = (portfolio_geom_return - risk_free_rate) / port_beta
            port_info_ratio = information_ratio(port_log_rets, market_log_rets[-port_log_rets.size:])

    if portfolio_vol_annual > 0 and port_log_rets.size:
        # Calmar uses the proxy of portfolio path drawdown reconstructed from cumulative log returns.
        cum_path = np.exp(np.cumsum(port_log_rets))
        peak = np.maximum.accumulate(cum_path)
        dd = np.max((peak - cum_path) / peak)
        if dd > 0:
            port_calmar = portfolio_geom_return / dd

    hhi = herfindahl_index(weights_arr)
    eff_n = effective_n(weights_arr)
    div_ratio = diversification_ratio(weights_arr, asset_vols_annual, portfolio_vol_annual)

    aapl_weight = next(
        (r["position_value"] / portfolio_value for r in valid_records if r["symbol"].upper() == "AAPL"),
        0.0,
    )
    tariff_metric = aapl_tariff_impact(aapl_weight) if aapl_weight > 0 else None

    summary = {
        "total_value": round(portfolio_value, 2),
        "total_cost": round(total_cost, 2),
        "total_gain_loss": round(portfolio_value - total_cost, 2),
        "total_gain_loss_pct": round(((portfolio_value - total_cost) / total_cost) * 100, 2) if total_cost else 0,
        "total_dividends_received": round(total_dividends_received, 2),
        "total_return_dollar": round(portfolio_value - total_cost + total_dividends_received, 2),
        "total_return_pct": round(((portfolio_value - total_cost + total_dividends_received) / total_cost) * 100, 2) if total_cost else 0,
        "portfolio_volatility": round(portfolio_vol_annual, 4),
        "portfolio_geom_return": round(portfolio_geom_return, 4),
        "portfolio_sharpe": round(port_sharpe, 4),
        "portfolio_sortino": round(port_sortino, 4),
        "portfolio_calmar": round(port_calmar, 4),
        "portfolio_treynor": round(port_treynor, 4),
        "portfolio_information_ratio": round(port_info_ratio, 4),
        "portfolio_beta": round(port_beta, 4) if port_beta is not None else None,
        "portfolio_alpha": round(port_alpha, 4),
        "hhi": round(hhi, 4),
        "effective_n": round(eff_n, 2),
        "diversification_ratio": round(div_ratio, 4),
        "diversification_score": round(1.0 - hhi, 4),  # legacy field for any old caller
        "num_holdings": len(symbols_valid),
        "lookback_days": int(min(port_log_rets.size, TRADING_DAYS_STOCKS)) if port_log_rets.size else 0,
        "rf_annual_pct": round(risk_free_rate * 100, 3),
        "trading_days_per_year": TRADING_DAYS_STOCKS,
        "return_type": "log",
        "tariff_exposure": tariff_metric,
    }

    return {
        "summary": summary,
        "holdings": holding_records,
        "weights": {r["symbol"]: round(weights_arr[i], 4) for i, r in enumerate(valid_records)},
        "covariance_matrix_annual": cov_annual.tolist() if cov_annual.size else [],
    }
