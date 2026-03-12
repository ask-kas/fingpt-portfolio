"""
portfolio.py — Portfolio analytics engine.

Calculates quantitative metrics: returns, volatility, Sharpe ratio,
max drawdown, diversification score, and sector allocation.
"""

import numpy as np
from typing import Optional


def calculate_returns(prices: list[float]) -> list[float]:
    """Calculate daily returns from a price series (newest first)."""
    # Reverse so oldest is first for correct calculation
    p = list(reversed(prices))
    if len(p) < 2:
        return []
    returns = [(p[i] - p[i - 1]) / p[i - 1] for i in range(1, len(p))]
    return returns


def calculate_volatility(returns: list[float], annualize: bool = True) -> float:
    """Calculate volatility (std dev of returns). Annualized by default (252 trading days)."""
    if not returns:
        return 0.0
    vol = float(np.std(returns))
    if annualize:
        vol *= np.sqrt(252)
    return round(vol, 4)


def calculate_sharpe(returns: list[float], risk_free_rate: float = 0.05) -> float:
    """
    Calculate annualized Sharpe ratio.
    risk_free_rate: annual (e.g. 0.05 for 5%), converted internally to daily.
    """
    if not returns or np.std(returns) == 0:
        return 0.0
    daily_rf = risk_free_rate / 252
    excess = [r - daily_rf for r in returns]
    sharpe = (np.mean(excess) / np.std(excess)) * np.sqrt(252)
    return round(float(sharpe), 4)


def calculate_max_drawdown(prices: list[float]) -> float:
    """Calculate maximum drawdown from a price series (newest first)."""
    p = list(reversed(prices))  # oldest first
    if len(p) < 2:
        return 0.0
    peak = p[0]
    max_dd = 0.0
    for price in p:
        if price > peak:
            peak = price
        dd = (peak - price) / peak
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 4)


def diversification_score(weights: list[float]) -> float:
    """
    Simple diversification score: 1 - HHI (Herfindahl index).
    0 = concentrated in one asset, approaching 1 = well diversified.
    """
    if not weights:
        return 0.0
    total = sum(weights)
    if total == 0:
        return 0.0
    normalized = [w / total for w in weights]
    hhi = sum(w ** 2 for w in normalized)
    return round(1 - hhi, 4)


def analyze_portfolio(holdings: list[dict], daily_data: dict[str, list[dict]], risk_free_rate: float = 0.05) -> dict:
    """
    Full portfolio analysis.

    holdings: [{"symbol": "AAPL", "shares": 10, "avg_cost": 150.0}, ...]
    daily_data: {"AAPL": [{"date": ..., "close": ...}, ...], ...}
    risk_free_rate: annual rate (from FRED)

    Returns a comprehensive analytics dict.
    """
    if not holdings:
        return {"error": "No holdings provided"}

    stock_analyses = []
    portfolio_value = 0.0
    total_cost = 0.0

    for h in holdings:
        sym = h["symbol"]
        shares = h["shares"]
        avg_cost = h["avg_cost"]

        prices_data = daily_data.get(sym, [])
        if not prices_data:
            stock_analyses.append({"symbol": sym, "error": "No price data"})
            continue

        closes = [d["close"] for d in prices_data]
        current_price = closes[0]  # newest first
        position_value = current_price * shares
        cost_basis = avg_cost * shares
        portfolio_value += position_value
        total_cost += cost_basis

        returns = calculate_returns(closes)

        stock_analyses.append({
            "symbol": sym,
            "current_price": round(current_price, 2),
            "shares": shares,
            "position_value": round(position_value, 2),
            "cost_basis": round(cost_basis, 2),
            "gain_loss": round(position_value - cost_basis, 2),
            "gain_loss_pct": round(((position_value - cost_basis) / cost_basis) * 100, 2) if cost_basis else 0,
            "volatility": calculate_volatility(returns),
            "sharpe_ratio": calculate_sharpe(returns, risk_free_rate),
            "max_drawdown": calculate_max_drawdown(closes),
            "avg_daily_return": round(float(np.mean(returns)) * 100, 4) if returns else 0,
        })

    # Portfolio-level metrics
    weights = [s.get("position_value", 0) for s in stock_analyses if "error" not in s]

    # Weighted portfolio returns (simplified — equal weight by value)
    all_returns = []
    for h in holdings:
        sym = h["symbol"]
        prices_data = daily_data.get(sym, [])
        if prices_data:
            closes = [d["close"] for d in prices_data]
            rets = calculate_returns(closes)
            all_returns.append(rets)

    # Simple portfolio return: average across stocks (value-weighted would need alignment)
    if all_returns:
        min_len = min(len(r) for r in all_returns)
        port_returns = []
        for i in range(min_len):
            day_ret = np.mean([r[i] for r in all_returns])
            port_returns.append(float(day_ret))
    else:
        port_returns = []

    return {
        "summary": {
            "total_value": round(portfolio_value, 2),
            "total_cost": round(total_cost, 2),
            "total_gain_loss": round(portfolio_value - total_cost, 2),
            "total_gain_loss_pct": round(((portfolio_value - total_cost) / total_cost) * 100, 2) if total_cost else 0,
            "portfolio_volatility": calculate_volatility(port_returns),
            "portfolio_sharpe": calculate_sharpe(port_returns, risk_free_rate),
            "diversification_score": diversification_score(weights),
            "num_holdings": len(holdings),
        },
        "holdings": stock_analyses,
    }
