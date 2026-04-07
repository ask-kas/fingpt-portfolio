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


def calculate_volatility(returns: list[float], annualize: bool = True, trading_days: int = 252) -> float:
    """Calculate volatility (std dev of returns). Annualized by default."""
    if not returns:
        return 0.0
    vol = float(np.std(returns))
    if annualize:
        vol *= np.sqrt(trading_days)
    return round(vol, 4)


def calculate_sharpe(returns: list[float], risk_free_rate: float = 0.05, trading_days: int = 252) -> float:
    """
    Calculate annualized Sharpe ratio.
    risk_free_rate: annual (e.g. 0.05 for 5%), converted internally to daily.
    """
    if not returns or np.std(returns) == 0:
        return 0.0
    daily_rf = risk_free_rate / trading_days
    excess = [r - daily_rf for r in returns]
    sharpe = (np.mean(excess) / np.std(excess)) * np.sqrt(trading_days)
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


def calculate_sma(prices: list[float], window: int = 20) -> float:
    """Simple moving average of the most recent `window` prices. Prices are newest-first."""
    if not prices:
        return 0.0
    subset = prices[:window]
    return round(float(np.mean(subset)), 2)


def calculate_rsi(prices: list[float], period: int = 14) -> float:
    """Relative Strength Index. Prices are newest-first."""
    p = list(reversed(prices))  # oldest first
    if len(p) < period + 1:
        return 50.0  # neutral default
    deltas = [p[i] - p[i - 1] for i in range(1, len(p))]
    recent = deltas[-period:]
    gains = [d if d > 0 else 0 for d in recent]
    losses = [-d if d < 0 else 0 for d in recent]
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(float(100 - (100 / (1 + rs))), 2)


def calculate_sortino(returns: list[float], risk_free_rate: float = 0.05, trading_days: int = 252) -> float:
    """Sortino ratio: like Sharpe but only penalizes downside volatility."""
    if not returns:
        return 0.0
    daily_rf = risk_free_rate / trading_days
    excess = [r - daily_rf for r in returns]
    downside = [r for r in excess if r < 0]
    if not downside:
        return 0.0
    downside_std = float(np.std(downside))
    if downside_std == 0:
        return 0.0
    return round(float((np.mean(excess) / downside_std) * np.sqrt(trading_days)), 4)


def calculate_calmar(returns: list[float], prices: list[float], trading_days: int = 252) -> float:
    """Calmar ratio: annualized return / max drawdown."""
    if not returns or not prices:
        return 0.0
    ann_return = float(np.mean(returns)) * trading_days
    max_dd = calculate_max_drawdown(prices)
    if max_dd == 0:
        return 0.0
    return round(ann_return / max_dd, 4)


def calculate_beta(stock_returns: list[float], market_returns: list[float]) -> float:
    """Beta: sensitivity of stock returns to market returns."""
    min_len = min(len(stock_returns), len(market_returns))
    if min_len < 10:
        return 1.0
    sr = np.array(stock_returns[:min_len])
    mr = np.array(market_returns[:min_len])
    cov = np.cov(sr, mr)[0, 1]
    var = np.var(mr)
    if var == 0:
        return 1.0
    return round(float(cov / var), 4)


def calculate_alpha(
    stock_returns: list[float],
    market_returns: list[float],
    risk_free_rate: float = 0.05,
    trading_days: int = 252,
) -> float:
    """Jensen's Alpha: excess return beyond what beta predicts."""
    min_len = min(len(stock_returns), len(market_returns))
    if min_len < 10:
        return 0.0
    daily_rf = risk_free_rate / trading_days
    beta = calculate_beta(stock_returns, market_returns)
    stock_mean = float(np.mean(stock_returns[:min_len]))
    market_mean = float(np.mean(market_returns[:min_len]))
    daily_alpha = stock_mean - (daily_rf + beta * (market_mean - daily_rf))
    annual_alpha = daily_alpha * trading_days
    return round(annual_alpha, 4)


def calculate_treynor(returns: list[float], beta: float, risk_free_rate: float = 0.05, trading_days: int = 252) -> float:
    """Treynor ratio: excess return per unit of systematic risk (beta)."""
    if not returns or beta == 0:
        return 0.0
    ann_return = float(np.mean(returns)) * trading_days
    return round((ann_return - risk_free_rate) / beta, 4)


def _trading_days_for_symbol(symbol: str) -> int:
    """Return annualization factor: 365 for crypto, 252 for stocks."""
    return 365 if "-USD" in symbol.upper() else 252


def analyze_portfolio(holdings: list[dict], daily_data: dict[str, list[dict]], risk_free_rate: float = 0.05, market_data: Optional[list[dict]] = None) -> dict:
    """
    Full portfolio analysis.

    holdings: [{"symbol": "AAPL", "shares": 10, "avg_cost": 150.0}, ...]
    daily_data: {"AAPL": [{"date": ..., "close": ...}, ...], ...}
    risk_free_rate: annual rate (from FRED)

    Returns a comprehensive analytics dict.
    """
    if not holdings:
        return {"error": "No holdings provided"}

    # Market returns for beta/alpha (SPY benchmark)
    market_returns = []
    if market_data:
        market_closes = [d["close"] for d in market_data]
        market_returns = calculate_returns(market_closes)

    stock_analyses = []
    portfolio_value = 0.0
    total_cost = 0.0

    # Per-holding analysis
    all_returns = []
    all_weights = []

    for h in holdings:
        sym = h["symbol"]
        shares = h["shares"]
        avg_cost = h["avg_cost"]
        trading_days = _trading_days_for_symbol(sym)

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

        beta = calculate_beta(returns, market_returns) if market_returns else None
        alpha = calculate_alpha(returns, market_returns, risk_free_rate, trading_days) if market_returns else None

        stock_analyses.append({
            "symbol": sym,
            "current_price": round(current_price, 2),
            "shares": shares,
            "position_value": round(position_value, 2),
            "cost_basis": round(cost_basis, 2),
            "gain_loss": round(position_value - cost_basis, 2),
            "gain_loss_pct": round(((position_value - cost_basis) / cost_basis) * 100, 2) if cost_basis else 0,
            "volatility": calculate_volatility(returns, trading_days=trading_days),
            "sharpe_ratio": calculate_sharpe(returns, risk_free_rate, trading_days=trading_days),
            "sortino_ratio": calculate_sortino(returns, risk_free_rate, trading_days=trading_days),
            "calmar_ratio": calculate_calmar(returns, closes, trading_days=trading_days),
            "max_drawdown": calculate_max_drawdown(closes),
            "beta": beta,
            "alpha": alpha,
            "treynor_ratio": calculate_treynor(returns, beta, risk_free_rate, trading_days) if beta else None,
            "avg_daily_return": round(float(np.mean(returns)) * 100, 4) if returns else 0,
            "sma_20": calculate_sma(closes, 20),
            "sma_50": calculate_sma(closes, 50),
            "rsi_14": calculate_rsi(closes, 14),
        })

        # Collect for portfolio-level value-weighted returns
        if returns:
            all_returns.append(returns)
            all_weights.append(position_value)

    # Portfolio-level metrics
    weights = [s.get("position_value", 0) for s in stock_analyses if "error" not in s]

    # Value-weighted portfolio returns
    if all_returns and all_weights:
        total_weight = sum(all_weights)
        normalized_weights = [w / total_weight for w in all_weights] if total_weight > 0 else []
        min_len = min(len(r) for r in all_returns)
        port_returns = []
        for i in range(min_len):
            day_ret = sum(normalized_weights[j] * all_returns[j][i] for j in range(len(all_returns)))
            port_returns.append(float(day_ret))
    else:
        port_returns = []

    port_beta = calculate_beta(port_returns, market_returns) if market_returns and port_returns else None
    port_alpha = calculate_alpha(port_returns, market_returns, risk_free_rate) if market_returns and port_returns else None

    return {
        "summary": {
            "total_value": round(portfolio_value, 2),
            "total_cost": round(total_cost, 2),
            "total_gain_loss": round(portfolio_value - total_cost, 2),
            "total_gain_loss_pct": round(((portfolio_value - total_cost) / total_cost) * 100, 2) if total_cost else 0,
            "portfolio_volatility": calculate_volatility(port_returns),
            "portfolio_sharpe": calculate_sharpe(port_returns, risk_free_rate),
            "portfolio_sortino": calculate_sortino(port_returns, risk_free_rate),
            "portfolio_calmar": calculate_calmar(port_returns, [], 252) if port_returns else 0,
            "portfolio_beta": port_beta,
            "portfolio_alpha": port_alpha,
            "diversification_score": diversification_score(weights),
            "num_holdings": len(holdings),
        },
        "holdings": stock_analyses,
    }
