"""
mcp_tools.py — Volatility analytics exposed as MCP tools.

This module is the single source of truth for the tools the AI assistant can
call. Both the standalone MCP server (`backend/mcp_server.py`) and the in-app
chat endpoint (`backend/app.py`) read from `TOOLS` here, so adding a tool in
one place exposes it everywhere.

Each entry is a dict with:
  - name:        snake_case tool identifier
  - description: short summary the LLM uses to decide when to call it
  - parameters:  JSON Schema for arguments
  - handler:     pure Python callable that takes **kwargs and returns a dict
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf


# ── Helpers ─────────────────────────────────────────────────

def _fetch_daily_returns(symbol: str, lookback_days: int) -> pd.Series:
    """Fetch daily simple returns for `symbol` over the last `lookback_days`."""
    period_days = max(lookback_days + 30, 60)
    period = f"{period_days}d" if period_days <= 730 else "5y"
    df = yf.Ticker(symbol).history(period=period, auto_adjust=True)
    if df.empty:
        raise ValueError(f"No price history for {symbol}")
    closes = df["Close"].dropna()
    if len(closes) < 5:
        raise ValueError(f"Insufficient history for {symbol} ({len(closes)} bars)")
    returns = closes.pct_change().dropna().tail(lookback_days)
    return returns


def _annualization_factor(symbol: str) -> int:
    """Crypto trades 365 days/year, equities 252."""
    upper = symbol.upper()
    if "-USD" in upper or upper in {"BTC", "ETH", "SOL", "DOGE", "ADA", "XRP"}:
        return 365
    return 252


# ── Tool implementations ────────────────────────────────────

def realized_volatility(symbol: str, lookback_days: int = 60) -> dict:
    """Sample standard deviation of daily returns, annualized."""
    returns = _fetch_daily_returns(symbol, lookback_days)
    daily_std = float(returns.std(ddof=1))
    factor = _annualization_factor(symbol)
    return {
        "symbol": symbol.upper(),
        "method": "realized_historical",
        "lookback_days": lookback_days,
        "daily_volatility": round(daily_std, 6),
        "annualized_volatility": round(daily_std * math.sqrt(factor), 6),
        "annualized_volatility_pct": round(daily_std * math.sqrt(factor) * 100, 3),
        "n_observations": int(len(returns)),
        "annualization_factor": factor,
    }


def ewma_volatility(
    symbol: str,
    lookback_days: int = 252,
    lambda_: float = 0.94,
) -> dict:
    """
    RiskMetrics-style exponentially weighted volatility.

    sigma_t^2 = lambda * sigma_{t-1}^2 + (1 - lambda) * r_{t-1}^2

    More responsive to recent moves than plain historical vol — what banks use.
    """
    if not 0 < lambda_ < 1:
        raise ValueError("lambda_ must be between 0 and 1")
    returns = _fetch_daily_returns(symbol, lookback_days)
    if len(returns) < 30:
        raise ValueError(f"Need at least 30 returns for EWMA, got {len(returns)}")
    seed_var = float(returns.iloc[:20].var(ddof=1))
    var = seed_var
    for r in returns.iloc[20:]:
        var = lambda_ * var + (1 - lambda_) * (r ** 2)
    daily_std = math.sqrt(var)
    factor = _annualization_factor(symbol)
    return {
        "symbol": symbol.upper(),
        "method": "ewma_riskmetrics",
        "lookback_days": lookback_days,
        "lambda": lambda_,
        "daily_volatility": round(daily_std, 6),
        "annualized_volatility": round(daily_std * math.sqrt(factor), 6),
        "annualized_volatility_pct": round(daily_std * math.sqrt(factor) * 100, 3),
        "n_observations": int(len(returns)),
    }


def garch_volatility(symbol: str, lookback_days: int = 504) -> dict:
    """
    GARCH(1,1) one-step-ahead volatility forecast.

    Captures volatility clustering — periods of high vol persist, periods of
    calm persist. Industry standard for short-term risk forecasting.
    """
    try:
        from arch import arch_model
    except ImportError:
        raise RuntimeError(
            "GARCH requires the 'arch' package. Install with: pip install arch"
        )

    returns = _fetch_daily_returns(symbol, lookback_days)
    if len(returns) < 100:
        raise ValueError(f"GARCH needs at least 100 returns, got {len(returns)}")

    # arch package expects returns scaled to percentages for numerical stability
    scaled = returns * 100
    am = arch_model(scaled, mean="constant", vol="GARCH", p=1, q=1, dist="t")
    res = am.fit(disp="off", show_warning=False)
    forecast = res.forecast(horizon=1, reindex=False)
    daily_var_pct2 = float(forecast.variance.iloc[-1, 0])
    daily_std = math.sqrt(daily_var_pct2) / 100  # un-scale
    factor = _annualization_factor(symbol)

    params = res.params.to_dict()
    return {
        "symbol": symbol.upper(),
        "method": "garch_1_1_t",
        "lookback_days": lookback_days,
        "daily_volatility_forecast": round(daily_std, 6),
        "annualized_volatility_forecast": round(daily_std * math.sqrt(factor), 6),
        "annualized_volatility_forecast_pct": round(
            daily_std * math.sqrt(factor) * 100, 3
        ),
        "params": {k: round(float(v), 6) for k, v in params.items()},
        "log_likelihood": round(float(res.loglikelihood), 3),
        "aic": round(float(res.aic), 3),
        "n_observations": int(len(returns)),
    }


def implied_volatility(symbol: str, expiration: str | None = None) -> dict:
    """
    At-the-money implied volatility from the options chain.

    Forward-looking: reflects market consensus on future volatility, unlike
    historical methods which only look at the past.
    """
    ticker = yf.Ticker(symbol)
    expirations = list(ticker.options or [])
    if not expirations:
        raise ValueError(f"No options chain available for {symbol}")
    target_exp = expiration or expirations[0]
    if target_exp not in expirations:
        raise ValueError(
            f"Expiration {target_exp} not in available: {expirations[:5]}..."
        )

    spot = float(ticker.history(period="1d", auto_adjust=True)["Close"].iloc[-1])
    chain = ticker.option_chain(target_exp)
    calls = chain.calls
    puts = chain.puts
    if calls.empty and puts.empty:
        raise ValueError(f"Empty options chain for {symbol} {target_exp}")

    def _atm_iv(df):
        if df.empty or "impliedVolatility" not in df.columns:
            return None
        df = df.dropna(subset=["impliedVolatility", "strike"])
        if df.empty:
            return None
        idx = (df["strike"] - spot).abs().idxmin()
        row = df.loc[idx]
        return {
            "strike": float(row["strike"]),
            "iv": float(row["impliedVolatility"]),
            "iv_pct": round(float(row["impliedVolatility"]) * 100, 3),
            "volume": int(row.get("volume") or 0),
            "openInterest": int(row.get("openInterest") or 0),
        }

    call_iv = _atm_iv(calls)
    put_iv = _atm_iv(puts)
    avg_iv = None
    if call_iv and put_iv:
        avg_iv = (call_iv["iv"] + put_iv["iv"]) / 2

    return {
        "symbol": symbol.upper(),
        "method": "implied_volatility_atm",
        "expiration": target_exp,
        "spot_price": round(spot, 4),
        "atm_call": call_iv,
        "atm_put": put_iv,
        "atm_average_iv": round(avg_iv, 6) if avg_iv else None,
        "atm_average_iv_pct": round(avg_iv * 100, 3) if avg_iv else None,
        "available_expirations": expirations[:10],
    }


def vol_term_structure(symbol: str, max_expirations: int = 8) -> dict:
    """
    Implied volatility across expirations — the IV term structure.

    Useful for spotting event-driven vol (earnings, Fed) and contango/backwardation.
    """
    ticker = yf.Ticker(symbol)
    expirations = list(ticker.options or [])[:max_expirations]
    if not expirations:
        raise ValueError(f"No options chain available for {symbol}")
    spot = float(ticker.history(period="1d", auto_adjust=True)["Close"].iloc[-1])

    points = []
    for exp in expirations:
        try:
            chain = ticker.option_chain(exp)
            calls = chain.calls.dropna(subset=["impliedVolatility", "strike"])
            if calls.empty:
                continue
            atm = calls.loc[(calls["strike"] - spot).abs().idxmin()]
            points.append({
                "expiration": exp,
                "atm_strike": float(atm["strike"]),
                "iv": round(float(atm["impliedVolatility"]), 6),
                "iv_pct": round(float(atm["impliedVolatility"]) * 100, 3),
            })
        except Exception:
            continue

    if not points:
        raise ValueError(f"No usable IV data for {symbol}")

    ivs = [p["iv"] for p in points]
    shape = (
        "contango" if ivs[-1] > ivs[0] + 0.01
        else "backwardation" if ivs[0] > ivs[-1] + 0.01
        else "flat"
    )
    return {
        "symbol": symbol.upper(),
        "method": "iv_term_structure_atm_calls",
        "spot_price": round(spot, 4),
        "shape": shape,
        "points": points,
    }


def portfolio_volatility(holdings: list[dict], lookback_days: int = 252) -> dict:
    """
    Annualized portfolio volatility using the full covariance matrix.

    holdings: [{"symbol": "AAPL", "shares": 10, ...}, ...]
    Computes weights from market value, then sqrt(w' Σ w) * sqrt(252).
    """
    if not holdings:
        raise ValueError("holdings cannot be empty")

    symbols = [h["symbol"].upper() for h in holdings]
    shares = np.array([float(h.get("shares", 0)) for h in holdings])
    if (shares <= 0).any():
        raise ValueError("All holdings must have positive shares")

    # Fetch closes for all symbols at once
    period_days = max(lookback_days + 30, 90)
    period = f"{period_days}d" if period_days <= 730 else "5y"
    data = yf.download(
        symbols, period=period, auto_adjust=True, progress=False,
        group_by="ticker" if len(symbols) > 1 else None,
    )
    if data.empty:
        raise ValueError("No price data for any holdings")

    if len(symbols) == 1:
        closes = data["Close"].to_frame(symbols[0])
    else:
        closes = pd.DataFrame({s: data[s]["Close"] for s in symbols if s in data})

    closes = closes.dropna(how="any").tail(lookback_days + 1)
    if len(closes) < 30:
        raise ValueError(f"Insufficient overlapping history: {len(closes)} bars")

    # Current prices for weights
    current_prices = closes.iloc[-1].values
    market_values = shares * current_prices
    total_value = float(market_values.sum())
    weights = market_values / total_value

    # Cov matrix of daily returns
    returns = closes.pct_change().dropna()
    cov_daily = returns.cov().values
    port_var_daily = float(weights @ cov_daily @ weights)
    port_vol_daily = math.sqrt(port_var_daily)
    port_vol_annual = port_vol_daily * math.sqrt(252)

    contributions = []
    for i, sym in enumerate(symbols):
        marginal = (cov_daily @ weights)[i]
        contrib_pct = (weights[i] * marginal / port_var_daily) * 100
        contributions.append({
            "symbol": sym,
            "weight_pct": round(float(weights[i] * 100), 3),
            "individual_vol_pct": round(
                float(math.sqrt(cov_daily[i, i]) * math.sqrt(252) * 100), 3
            ),
            "risk_contribution_pct": round(float(contrib_pct), 3),
        })

    return {
        "method": "portfolio_volatility_full_covariance",
        "lookback_days": lookback_days,
        "n_holdings": len(symbols),
        "total_value": round(total_value, 2),
        "daily_volatility": round(port_vol_daily, 6),
        "annualized_volatility": round(port_vol_annual, 6),
        "annualized_volatility_pct": round(port_vol_annual * 100, 3),
        "risk_contributions": sorted(
            contributions, key=lambda x: x["risk_contribution_pct"], reverse=True
        ),
    }


def volatility_regime(symbol: str, lookback_days: int = 60) -> dict:
    """
    Classify the current realized volatility regime.

    Buckets follow the dashboard's existing thresholds:
      - LOW       : < 12% annualized
      - NORMAL    : 12-20%
      - ELEVATED  : 20-30%
      - CRISIS    : > 30%
    """
    rv = realized_volatility(symbol, lookback_days)
    vol_pct = rv["annualized_volatility_pct"]
    if vol_pct < 12:
        regime = "LOW"
    elif vol_pct < 20:
        regime = "NORMAL"
    elif vol_pct < 30:
        regime = "ELEVATED"
    else:
        regime = "CRISIS"
    return {
        "symbol": symbol.upper(),
        "annualized_volatility_pct": vol_pct,
        "lookback_days": lookback_days,
        "regime": regime,
        "thresholds": {
            "LOW": "< 12%", "NORMAL": "12-20%",
            "ELEVATED": "20-30%", "CRISIS": "> 30%",
        },
    }


# ── Tool registry ──────────────────────────────────────────

TOOLS: list[dict[str, Any]] = [
    {
        "name": "realized_volatility",
        "description": (
            "Compute annualized realized (historical) volatility from daily "
            "returns. Backward-looking. Use when the user asks about a stock's "
            "historical volatility, standard deviation, or realized vol."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker, e.g. 'AAPL' or 'BTC-USD'"},
                "lookback_days": {
                    "type": "integer",
                    "description": "Trading days of history (default 60)",
                    "default": 60,
                },
            },
            "required": ["symbol"],
        },
        "handler": realized_volatility,
    },
    {
        "name": "ewma_volatility",
        "description": (
            "Compute RiskMetrics-style EWMA volatility (lambda=0.94 by default). "
            "More responsive to recent moves than plain historical vol — used by "
            "banks for daily risk reporting. Use when user asks for current/recent "
            "vol, decay-weighted vol, or RiskMetrics."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "lookback_days": {"type": "integer", "default": 252},
                "lambda_": {
                    "type": "number",
                    "description": "Decay parameter, 0<λ<1 (default 0.94)",
                    "default": 0.94,
                },
            },
            "required": ["symbol"],
        },
        "handler": ewma_volatility,
    },
    {
        "name": "garch_volatility",
        "description": (
            "Fit a GARCH(1,1) model with Student-t errors and return the one-step-"
            "ahead volatility forecast. Captures volatility clustering. Use when "
            "user asks for forecasted vol, GARCH, or 'next-day' volatility."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "lookback_days": {"type": "integer", "default": 504},
            },
            "required": ["symbol"],
        },
        "handler": garch_volatility,
    },
    {
        "name": "implied_volatility",
        "description": (
            "At-the-money implied volatility from the options market. "
            "Forward-looking, reflects market consensus. Use when user asks "
            "about IV, implied vol, or what options markets expect."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "expiration": {
                    "type": "string",
                    "description": "YYYY-MM-DD; defaults to nearest expiration",
                },
            },
            "required": ["symbol"],
        },
        "handler": implied_volatility,
    },
    {
        "name": "vol_term_structure",
        "description": (
            "Implied volatility across multiple option expirations. Detects "
            "event-driven vol bumps (earnings, Fed meetings) and contango/"
            "backwardation. Use when user asks about IV term structure or "
            "vol curve."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "max_expirations": {"type": "integer", "default": 8},
            },
            "required": ["symbol"],
        },
        "handler": vol_term_structure,
    },
    {
        "name": "portfolio_volatility",
        "description": (
            "Compute annualized portfolio volatility using the full covariance "
            "matrix, plus per-holding risk contributions. Use when user asks "
            "about overall portfolio risk or which positions drive the vol."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "holdings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string"},
                            "shares": {"type": "number"},
                        },
                        "required": ["symbol", "shares"],
                    },
                },
                "lookback_days": {"type": "integer", "default": 252},
            },
            "required": ["holdings"],
        },
        "handler": portfolio_volatility,
    },
    {
        "name": "volatility_regime",
        "description": (
            "Classify the current vol regime (LOW / NORMAL / ELEVATED / CRISIS) "
            "based on recent realized volatility. Use when user asks 'is vol "
            "high right now' or about the current regime."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "lookback_days": {"type": "integer", "default": 60},
            },
            "required": ["symbol"],
        },
        "handler": volatility_regime,
    },
]

TOOL_HANDLERS = {t["name"]: t["handler"] for t in TOOLS}


def call_tool(name: str, arguments: dict) -> dict:
    """Execute a tool by name. Returns the handler's result dict, or an error dict."""
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return {"error": f"unknown tool: {name}"}
    try:
        return handler(**(arguments or {}))
    except Exception as e:
        return {"error": str(e), "error_type": type(e).__name__}
