"""
app.py — FastAPI backend for Veris Portfolio Intelligence.

Run with:  python backend/app.py
Serves API at :8000 and frontend at http://localhost:8000
"""

import hmac
import logging
import os
import sys
import asyncio
from pathlib import Path
from typing import Optional

# Load config/.env so FRED_API_KEY (and any other secrets) are available.
_env_path = Path(__file__).parent.parent / "config" / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

from fastapi import FastAPI, HTTPException, Depends, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Add project root to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.cache import cache
from backend.data_fetcher import create_clients
from backend.model_client import create_model_client
from backend.portfolio import analyze_portfolio
from backend.advanced_analytics import (
    monte_carlo_simulation,
    efficient_frontier,
    correlation_matrix,
    stress_test,
    what_if_simulation,
    regime_detection,
    data_quality_report,
    find_arbitrage,
)
from backend.database import init_db, get_db, close_db, crud, schemas

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("veris")

# ── Init ────────────────────────────────────────────────────
app = FastAPI(title="Veris — Portfolio Intelligence")

# Initialize database on startup
@app.on_event("startup")
def startup_db():
    init_db()
    logger.info("Database layer initialized")

@app.on_event("shutdown")
def shutdown_db():
    close_db()
    logger.info("Database connections closed")

# CORS — restrict to known verbs and headers; reject wildcard origins to prevent
# combined CSRF/IDOR risk if a deployer accidentally sets CORS_ORIGINS=*.
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:8000").split(",") if o.strip() and o.strip() != "*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["http://localhost:8000"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Admin-Key"],
)
clients = create_clients()
model = create_model_client()

yf_client = clients["yfinance"]
fred = clients["fred"]
sec = clients["sec"]
polymarket = clients["polymarket"]
kalshi = clients["kalshi"]


# ── Request Models ──────────────────────────────────────────
class Holding(BaseModel):
    symbol: str
    shares: float
    avg_cost: float
    dividends_per_share: float = 0.0  # Optional: total dividends per share since purchase


class PortfolioRequest(BaseModel):
    holdings: list[Holding]


class AnalyzeTextRequest(BaseModel):
    text: str
    task: str = "sentiment"  # sentiment | headline | insight


class WhatIfRequest(BaseModel):
    holdings: list[Holding]
    trade_symbol: str
    trade_shares: float
    trade_action: str = "buy"  # buy | sell


# ── API Routes ──────────────────────────────────────────────

@app.get("/api/health")
async def health():
    """Check backend health and AI model availability."""
    model_ok = await model.health_check()
    return {
        "backend": "ok",
        "model_server": "connected" if model_ok else "unavailable",
        "model_name": model.model_name,
        "model_url": model.base_url,
    }


@app.get("/api/quote/{symbol}")
async def get_quote(symbol: str):
    """Get real-time quote for a stock symbol."""
    result = await yf_client.get_quote(symbol.upper())
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.get("/api/daily/{symbol}")
async def get_daily(symbol: str, days: int = 100):
    """Get daily OHLCV data."""
    result = await yf_client.get_daily(symbol.upper(), days)
    if not result:
        raise HTTPException(404, f"No daily data found for {symbol.upper()}")
    return result


@app.get("/api/intraday/{symbol}")
async def get_intraday(
    symbol: str,
    interval: str = "1m",
    period: str | None = None,
    prepost: bool = False,
):
    """Get intraday OHLCV bars for a symbol.

    Query parameters:
      interval: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h (default: 1m)
      period:   window to fetch. Defaults are interval-aware:
                1m → 1d, 5m → 5d, 30m → 1mo, 1h → 3mo.
                Yahoo caps 1m at 7d and most others at 60d.
      prepost:  include pre/post-market bars (default: false)
    """
    try:
        result = await yf_client.get_intraday(
            symbol.upper(), interval=interval, period=period, prepost=prepost
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not result:
        raise HTTPException(404, f"No intraday data found for {symbol.upper()} ({interval})")
    return result


@app.get("/api/news")
async def get_news(tickers: str = "AAPL", limit: int = 10):
    """Get financial news for given tickers (comma-separated)."""
    symbols = [t.strip().upper() for t in tickers.split(",")]
    return await yf_client.get_news(symbols, limit)


@app.get("/api/macro")
async def get_macro():
    """Get macroeconomic indicators snapshot from FRED."""
    return await fred.get_macro_snapshot()


@app.get("/api/filings/{ticker}")
async def get_filings(ticker: str, filing_type: str = "10-K", count: int = 5):
    """Get SEC filings for a company."""
    return await sec.get_company_filings(ticker.upper(), filing_type, count)


@app.get("/api/polymarket")
async def get_polymarket(limit: int = 20):
    """Get trending prediction markets from Polymarket."""
    result = await polymarket.get_trending_markets(limit)
    if "error" in result:
        raise HTTPException(503, result["error"])
    return result


@app.get("/api/kalshi")
async def get_kalshi(limit: int = 20):
    """Get trending prediction events from Kalshi."""
    result = await kalshi.get_trending_events(limit)
    if "error" in result:
        raise HTTPException(503, result["error"])
    return result


@app.get("/api/polymarket/history/{clob_token_id}")
async def get_polymarket_history(clob_token_id: str, interval: str = "max"):
    """Get price history for a Polymarket outcome token."""
    if interval not in ("1h", "6h", "1d", "max", "all"):
        raise HTTPException(400, f"Invalid interval: {interval}")
    result = await polymarket.get_price_history(clob_token_id, interval)
    if "error" in result:
        raise HTTPException(503, result["error"])
    return result


@app.get("/api/kalshi/history/{ticker}")
async def get_kalshi_history(ticker: str, days: int = 30, series: str = ""):
    """Get candlestick history for a Kalshi market."""
    if not 1 <= days <= 365:
        raise HTTPException(400, "days must be between 1 and 365")
    result = await kalshi.get_candlesticks(ticker, days, series)
    if "error" in result:
        raise HTTPException(503, result["error"])
    return result


@app.get("/api/predictions/analysis")
async def predictions_analysis():
    """AI analysis of trending prediction markets."""
    cached = cache.get("predictions_analysis")
    if cached is not None:
        return cached

    pm_result, kalshi_result = await asyncio.gather(
        polymarket.get_trending_markets(),
        kalshi.get_trending_events(),
    )
    pm_markets = pm_result.get("markets", [])[:10]
    kalshi_events = kalshi_result.get("events", [])[:10]

    summary = {
        "polymarket_top": [
            {"question": m["question"], "yes_pct": round(m["outcome_prices"][0] * 100) if m.get("outcome_prices") else 0, "volume": round(m.get("volume", 0))}
            for m in pm_markets[:5]
        ],
        "kalshi_top": [
            {"title": e["title"], "yes_pct": round(e.get("yes_price", 0) * 100), "category": e.get("category", ""), "volume": round(e.get("volume", 0))}
            for e in kalshi_events[:5]
        ],
    }

    ai_analysis = None
    model_available = await model.health_check()
    if model_available:
        try:
            prompt = _build_predictions_prompt(pm_markets, kalshi_events)
            resp = await model.generate_insight(prompt)
            ai_analysis = resp.get("insight") if resp else None
        except Exception as e:
            logger.warning("Model generation failed: %s", e)
            ai_analysis = None

    result = {"summary": summary, "ai_analysis": ai_analysis, "model_available": model_available}
    cache.set("predictions_analysis", result, ttl_seconds=300)
    return result


@app.get("/api/arbitrage")
async def get_arbitrage():
    """Scan ALL markets on Polymarket and Kalshi for cross-platform arbitrage."""
    cached = cache.get("arbitrage_scan")
    if cached is not None:
        return cached

    pm_markets, kalshi_events = await asyncio.gather(
        polymarket.get_all_markets(max_pages=5),
        kalshi.get_all_events(max_pages=2),
    )

    result = find_arbitrage(pm_markets, kalshi_events)
    cache.set("arbitrage_scan", result, ttl_seconds=300)
    return result


@app.get("/api/calibration")
async def get_calibration():
    """Calibration curve: do X% markets resolve Yes X% of the time?"""
    cached = cache.get("calibration_data")
    if cached is not None:
        return cached

    resolved = await polymarket.get_resolved_markets(5)
    if not resolved:
        raise HTTPException(503, "No resolved markets available")

    buckets = {}
    for i in range(10):
        lo, hi = i * 0.1, (i + 1) * 0.1
        label = f"{int(lo*100)}-{int(hi*100)}%"
        in_bucket = [m for m in resolved if lo <= m["last_trade_price"] < hi]
        if not in_bucket:
            buckets[label] = {"range": label, "predicted_avg": (lo + hi) / 2, "actual_rate": None, "count": 0}
            continue
        actual = sum(1 for m in in_bucket if m["resolved_yes"]) / len(in_bucket)
        pred_avg = sum(m["last_trade_price"] for m in in_bucket) / len(in_bucket)
        buckets[label] = {"range": label, "predicted_avg": round(pred_avg, 3), "actual_rate": round(actual, 3), "count": len(in_bucket)}

    brier_scores = [(m["last_trade_price"] - (1 if m["resolved_yes"] else 0)) ** 2 for m in resolved]
    brier = round(sum(brier_scores) / len(brier_scores), 4) if brier_scores else None

    result = {"buckets": list(buckets.values()), "brier_score": brier, "total_markets": len(resolved)}
    cache.set("calibration_data", result, ttl_seconds=3600)
    return result


@app.get("/api/smart-money")
async def get_smart_money():
    """Detect abnormal volume spikes indicating informed money."""
    cached = cache.get("smart_money")
    if cached is not None:
        return cached

    pm_result = await polymarket.get_trending_markets(100)
    markets = pm_result.get("markets", [])

    alerts = []
    for m in markets:
        vol = m.get("volume", 0)
        vol24 = m.get("volume_24hr", 0)
        if vol <= 0 or vol24 <= 0:
            continue
        avg_daily = vol / 30
        if avg_daily <= 0:
            continue
        spike = vol24 / avg_daily
        if spike >= 2.0:
            yes = m.get("outcome_prices", [0])[0] if m.get("outcome_prices") else 0
            alerts.append({
                "question": m.get("question", ""),
                "slug": m.get("slug", ""),
                "spike_ratio": round(spike, 2),
                "volume_24hr": round(vol24),
                "avg_daily_vol": round(avg_daily),
                "current_yes": round(yes * 100, 1),
                "volume": round(vol),
            })

    alerts.sort(key=lambda x: x["spike_ratio"], reverse=True)
    result = {"alerts": alerts[:20], "total_scanned": len(markets)}
    cache.set("smart_money", result, ttl_seconds=300)
    return result


@app.get("/api/market-correlations")
async def get_market_correlations():
    """Cross-market correlation network from price history."""
    cached = cache.get("market_correlations")
    if cached is not None:
        return cached

    pm_result = await polymarket.get_trending_markets(100)
    markets = sorted(pm_result.get("markets", []), key=lambda m: m.get("volume", 0), reverse=True)[:15]

    histories = {}
    for m in markets:
        token_id = m.get("clob_token_ids", [None])[0]
        if not token_id:
            continue
        hist = await polymarket.get_price_history(token_id, "1d")
        pts = hist.get("history", [])
        if len(pts) >= 10:
            histories[m.get("question", "")[:40]] = {
                "prices": [p["price"] for p in pts],
                "volume": m.get("volume", 0),
                "slug": m.get("slug", ""),
            }

    labels = list(histories.keys())
    if len(labels) < 3:
        return {"nodes": [], "edges": [], "count": 0}

    import numpy as np
    nodes = [{"id": i, "label": l, "volume": histories[l]["volume"], "slug": histories[l]["slug"]} for i, l in enumerate(labels)]

    min_len = min(len(histories[l]["prices"]) for l in labels)
    price_matrix = np.array([histories[l]["prices"][:min_len] for l in labels])
    returns = np.diff(price_matrix, axis=1)

    edges = []
    n = len(labels)
    for i in range(n):
        for j in range(i + 1, n):
            if np.std(returns[i]) > 1e-6 and np.std(returns[j]) > 1e-6:
                try:
                    corr = float(np.corrcoef(returns[i], returns[j])[0, 1])
                except Exception:
                    continue
                if not np.isnan(corr) and abs(corr) > 0.3:
                    edges.append({"source": i, "target": j, "correlation": round(corr, 3)})

    result = {"nodes": nodes, "edges": edges, "count": len(labels)}
    cache.set("market_correlations", result, ttl_seconds=1800)
    return result


@app.get("/api/options/{symbol}")
async def get_options(symbol: str, expiration: str = None):
    """Get options chain for a stock symbol, with Greeks and IV skew.

    The risk free rate passed to Black Scholes is taken from the live 10Y
    treasury if available, otherwise defaults to the Fed Funds rate, and
    finally falls back to 4.35 percent.
    """
    import math, json

    rf = await _current_risk_free_rate()
    result = await yf_client.get_options(symbol.upper(), expiration, risk_free_rate=rf)
    if "error" in result:
        raise HTTPException(404, result["error"])

    # Sanitize NaN/Inf values that break JSON serialization
    def _sanitize(obj):
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize(v) for v in obj]
        return obj

    return _sanitize(result)


async def _current_risk_free_rate() -> float:
    """Live risk free rate. Prefers 10Y treasury, then fed funds, then 4.35%."""
    try:
        macro = await fred.get_macro_snapshot()
    except Exception:
        return 0.0435
    t10 = macro.get("treasury_10y", {})
    if isinstance(t10, dict) and "value" in t10:
        try:
            return float(t10["value"]) / 100.0
        except Exception:
            pass
    ff = macro.get("fed_funds_rate", {})
    if isinstance(ff, dict) and "value" in ff:
        try:
            return float(ff["value"]) / 100.0
        except Exception:
            pass
    return 0.0435


@app.post("/api/portfolio/analyze")
async def analyze(req: PortfolioRequest,
                  portfolio_id: Optional[str] = Query(None, description="DB portfolio ID — auto-saves snapshot if provided"),
                  user_id: Optional[str] = Query(None, description="DB user ID for snapshot audit trail"),
                  db: Session = Depends(get_db)):
    """
    Full portfolio analysis:
    1. Fetch daily prices for all holdings via yfinance
    2. Calculate quantitative metrics
    3. Fetch news + run FinGPT sentiment (if model available)
    4. Fetch macro indicators
    5. Generate AI insight (if model available)
    6. Auto-save snapshot to database (if portfolio_id provided)
    """
    holdings = [h.model_dump() for h in req.holdings]
    # Normalize symbols (handles crypto shorthand like BTC -> BTC-USD)
    for h in holdings:
        h["symbol"] = yf_client.normalize_symbol(h["symbol"])
    symbols = [h["symbol"] for h in holdings]

    warnings = []
    logger.info("Analyzing portfolio with %d holdings: %s", len(holdings), symbols)

    # 1. Fetch daily data for all symbols + SPY benchmark IN PARALLEL
    async def _fetch_daily(sym):
        try:
            return sym, await yf_client.get_daily(sym)
        except Exception as e:
            logger.warning("Failed to fetch daily data for %s: %s", sym, e)
            return sym, []

    fetch_symbols = symbols + (["SPY"] if "SPY" not in symbols else [])
    daily_results = await asyncio.gather(*[_fetch_daily(s) for s in fetch_symbols])
    daily_data = {}
    market_data = None
    price_freshness: dict[str, dict] = {}
    for sym, data in daily_results:
        if sym == "SPY" and "SPY" not in symbols:
            market_data = data
        else:
            daily_data[sym] = data
            if not data:
                warnings.append(f"Could not fetch price data for {sym}")
            else:
                # The freshness metadata is attached to the newest row.
                head = data[0]
                price_freshness[sym] = {
                    "latest_date": head.get("date"),
                    "fetched_at": head.get("fetched_at"),
                    "age_days": head.get("age_days"),
                    "is_stale": head.get("is_stale", False),
                }
                if head.get("is_stale"):
                    warnings.append(f"{sym} price data is {head.get('age_days')} days old, may be stale")

    # 2. Macro + news IN PARALLEL
    macro_task = fred.get_macro_snapshot()
    news_task = yf_client.get_news(symbols, limit=8)
    macro_result, news_result = await asyncio.gather(
        macro_task, news_task, return_exceptions=True
    )

    # Process macro. Risk free rate priority: 10Y treasury (preferred for
    # long horizon portfolio analytics), then Fed Funds, then a 4.35 percent
    # fallback. Spec module 12 calls the 10Y treasury the canonical choice.
    risk_free = 0.0435
    if isinstance(macro_result, Exception):
        logger.warning("Failed to fetch macro data: %s", macro_result)
        warnings.append("Could not fetch macro indicators, using default risk free rate of 4.35 percent")
        macro = {}
    else:
        macro = macro_result
        t10 = macro.get("treasury_10y", {})
        ffr = macro.get("fed_funds_rate", {})
        if isinstance(t10, dict) and "value" in t10:
            try:
                risk_free = float(t10["value"]) / 100.0
            except Exception:
                pass
        elif isinstance(ffr, dict) and "value" in ffr:
            try:
                risk_free = float(ffr["value"]) / 100.0
            except Exception:
                pass

    # Process news
    if isinstance(news_result, Exception):
        logger.warning("Failed to fetch news: %s", news_result)
        warnings.append("Could not fetch news data")
        news = []
    else:
        news = news_result

    # 3. Quantitative analysis (with SPY benchmark for beta/alpha)
    analytics = analyze_portfolio(holdings, daily_data, risk_free, market_data)

    # 4. Advanced analytics IN PARALLEL
    mc_task = asyncio.to_thread(monte_carlo_simulation, daily_data, holdings)
    ef_task = asyncio.to_thread(efficient_frontier, daily_data, holdings, risk_free)
    corr_task = asyncio.to_thread(correlation_matrix, daily_data, symbols)
    stress_task = asyncio.to_thread(stress_test, daily_data, holdings, None, market_data)

    mc_result, ef_result, corr_result, stress_result = await asyncio.gather(
        mc_task, ef_task, corr_task, stress_task, return_exceptions=True
    )

    def _safe(result):
        if isinstance(result, Exception):
            logger.warning("Advanced analytics error: %s", result)
            return {"error": str(result)}
        return result

    # Sentiment analysis — only if Colab is available.
    # Skipped for Ollama/Gemma (too slow, blocks analysis for minutes)
    model_available = await model.health_check()
    if model_available and getattr(model, "_available", False) and news:
        try:
            headlines = [a["title"] for a in news if a.get("title")]
            sentiments = await model.batch_sentiment(headlines)
            for i, article in enumerate(news):
                if i < len(sentiments):
                    article["fingpt_sentiment"] = sentiments[i]
        except Exception as e:
            logger.warning("Sentiment analysis failed: %s", e)
    ai_insight = None

    response = {
        "analytics": analytics,
        "monte_carlo": _safe(mc_result),
        "efficient_frontier": _safe(ef_result),
        "correlation": _safe(corr_result),
        "stress_test": _safe(stress_result),
        "news": news,
        "macro": macro,
        "ai_insight": ai_insight,
        "model_available": model_available,
        "warnings": warnings,
        "price_freshness": price_freshness,
        "risk_free_rate": risk_free,
        "risk_free_source": (
            "treasury_10y" if isinstance(macro.get("treasury_10y"), dict) and "value" in macro.get("treasury_10y", {})
            else "fed_funds_rate" if isinstance(macro.get("fed_funds_rate"), dict) and "value" in macro.get("fed_funds_rate", {})
            else "fallback_4_35_pct"
        ),
    }

    # Auto-save snapshot to database if portfolio_id is provided
    if portfolio_id and user_id:
        try:
            snapshot = crud.save_snapshot(db, portfolio_id, user_id, response, model_available)
            response["snapshot_id"] = snapshot.id
            logger.info("Auto-saved snapshot %s for portfolio %s", snapshot.id[:8], portfolio_id[:8])
        except Exception as e:
            logger.warning("Failed to auto-save snapshot: %s", e)
            warnings.append(f"Snapshot auto-save failed: {e}")

    return response


@app.post("/api/model/analyze")
async def model_analyze(req: AnalyzeTextRequest):
    """Direct access to FinGPT for ad-hoc analysis."""
    ok = await model.health_check()
    if not ok:
        raise HTTPException(503, "Colab model server is not available. Start the notebook first.")

    if req.task == "sentiment":
        return await model.analyze_sentiment(req.text)
    elif req.task == "headline":
        return await model.classify_headline(req.text)
    elif req.task == "insight":
        return await model.generate_insight(req.text)
    else:
        raise HTTPException(400, f"Unknown task: {req.task}")


@app.post("/api/whatif")
async def what_if(req: WhatIfRequest):
    """What-If Trade Simulator: simulate adding or removing a position."""
    holdings = [h.model_dump() for h in req.holdings]
    for h in holdings:
        h["symbol"] = yf_client.normalize_symbol(h["symbol"])
    trade_sym = yf_client.normalize_symbol(req.trade_symbol)
    symbols = list({h["symbol"] for h in holdings} | {trade_sym})

    async def _fetch(sym):
        try:
            return sym, await yf_client.get_daily(sym)
        except Exception:
            return sym, []

    fetch_syms = list(set(symbols + ["SPY"]))
    results = await asyncio.gather(*[_fetch(s) for s in fetch_syms])
    daily_data = {}
    market_data = None
    for sym, data in results:
        if sym == "SPY" and "SPY" not in symbols:
            market_data = data
        else:
            daily_data[sym] = data

    rf = await _current_risk_free_rate()
    result = what_if_simulation(
        daily_data, holdings, trade_sym, req.trade_shares,
        req.trade_action, rf, market_data,
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.post("/api/regime")
async def regime(req: PortfolioRequest):
    """Regime-Aware Risk Engine: rolling volatility regime detection."""
    holdings = [h.model_dump() for h in req.holdings]
    for h in holdings:
        h["symbol"] = yf_client.normalize_symbol(h["symbol"])
    symbols = [h["symbol"] for h in holdings]

    async def _fetch(sym):
        try:
            return sym, await yf_client.get_daily(sym)
        except Exception:
            return sym, []

    fetch_syms = symbols + (["SPY"] if "SPY" not in symbols else [])
    results = await asyncio.gather(*[_fetch(s) for s in fetch_syms])
    daily_data = {}
    market_data = None
    for sym, data in results:
        if sym == "SPY" and "SPY" not in symbols:
            market_data = data
        else:
            daily_data[sym] = data

    result = await asyncio.to_thread(regime_detection, daily_data, holdings, market_data)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.get("/api/earnings")
async def earnings_calendar(tickers: str = "AAPL"):
    """Event-Risk Calendar: upcoming earnings dates and historical earnings-day returns."""
    symbols = [t.strip().upper() for t in tickers.split(",")]
    symbols = [s for s in symbols if s and "-USD" not in s]
    if not symbols:
        return []
    return await yf_client.get_earnings_calendar(symbols)


@app.post("/api/data-quality")
async def data_quality(req: PortfolioRequest):
    """Data Quality Dashboard: per-ticker data freshness, gaps, and quality score."""
    holdings = [h.model_dump() for h in req.holdings]
    for h in holdings:
        h["symbol"] = yf_client.normalize_symbol(h["symbol"])
    symbols = [h["symbol"] for h in holdings]

    async def _fetch(sym):
        try:
            return sym, await yf_client.get_daily(sym, days=365)
        except Exception:
            return sym, []

    results = await asyncio.gather(*[_fetch(s) for s in symbols])
    daily_data = {sym: data for sym, data in results}

    return data_quality_report(daily_data, symbols)


@app.get("/api/holders")
async def institutional_holders(tickers: str = "AAPL"):
    """Legendary Investors: who among the top investors holds the same stocks as you."""
    symbols = [t.strip().upper() for t in tickers.split(",")]
    symbols = [s for s in symbols if s and "-USD" not in s]
    if not symbols:
        return {}
    return await yf_client.get_institutional_holders(symbols)


# ══════════════════════════════════════════════════════════════
#  DATABASE API ENDPOINTS
# ══════════════════════════════════════════════════════════════

# ── Users ────────────────────────────────────────────────────

@app.post("/api/db/users/register", response_model=schemas.UserResponse)
async def register_user(req: schemas.UserCreate, request: Request,
                        db: Session = Depends(get_db)):
    """Register a new user account. Creates a default portfolio automatically."""
    try:
        user = crud.create_user(
            db, req.username, req.email, req.password,
            display_name=req.display_name,
            ip=request.client.host if request.client else None,
        )
        return user
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.post("/api/db/users/login", response_model=schemas.UserResponse)
async def login_user(req: schemas.UserLogin, request: Request,
                     db: Session = Depends(get_db)):
    """Authenticate a user by username and password."""
    user = crud.authenticate_user(
        db, req.username, req.password,
        ip=request.client.host if request.client else None,
    )
    if not user:
        raise HTTPException(401, "Invalid credentials")
    return user


@app.get("/api/db/users/{user_id}", response_model=schemas.UserResponse)
async def get_user(user_id: str, db: Session = Depends(get_db)):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return user


@app.patch("/api/db/users/{user_id}", response_model=schemas.UserResponse)
async def update_user(user_id: str, req: schemas.UserUpdate,
                      db: Session = Depends(get_db)):
    user = crud.update_user(db, user_id, **req.model_dump(exclude_none=True))
    if not user:
        raise HTTPException(404, "User not found")
    return user


@app.get("/api/db/users/{user_id}/dashboard")
async def user_dashboard(user_id: str, db: Session = Depends(get_db)):
    """Aggregated dashboard stats for a user (portfolio count, holdings, latest metrics)."""
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return crud.get_user_dashboard_stats(db, user_id)


# ── Portfolios ───────────────────────────────────────────────

@app.post("/api/db/users/{user_id}/portfolios", response_model=schemas.PortfolioResponse)
async def create_portfolio(user_id: str, req: schemas.PortfolioCreate,
                           db: Session = Depends(get_db)):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    portfolio = crud.create_portfolio(
        db, user_id, req.name, req.description, req.is_default,
    )
    return portfolio


@app.get("/api/db/users/{user_id}/portfolios")
async def list_portfolios(user_id: str, db: Session = Depends(get_db)):
    portfolios = crud.get_portfolios(db, user_id)
    result = []
    for p in portfolios:
        resp = schemas.PortfolioResponse.model_validate(p)
        resp.num_holdings = len(p.holdings)
        result.append(resp)
    return result


@app.get("/api/db/portfolios/{portfolio_id}", response_model=schemas.PortfolioResponse)
async def get_portfolio(portfolio_id: str, db: Session = Depends(get_db)):
    portfolio = crud.get_portfolio(db, portfolio_id)
    if not portfolio:
        raise HTTPException(404, "Portfolio not found")
    return portfolio


@app.patch("/api/db/portfolios/{portfolio_id}")
async def update_portfolio(portfolio_id: str, req: schemas.PortfolioUpdate,
                           user_id: str = Query(...),
                           db: Session = Depends(get_db)):
    portfolio = crud.update_portfolio(
        db, portfolio_id, user_id, **req.model_dump(exclude_none=True),
    )
    if not portfolio:
        raise HTTPException(404, "Portfolio not found")
    return schemas.PortfolioResponse.model_validate(portfolio)


@app.delete("/api/db/portfolios/{portfolio_id}")
async def delete_portfolio(portfolio_id: str, user_id: str = Query(...),
                           db: Session = Depends(get_db)):
    if not crud.delete_portfolio(db, portfolio_id, user_id):
        raise HTTPException(404, "Portfolio not found")
    return {"status": "deleted"}


# ── Holdings ─────────────────────────────────────────────────

@app.post("/api/db/portfolios/{portfolio_id}/holdings", response_model=schemas.HoldingResponse)
async def add_holding(portfolio_id: str, req: schemas.HoldingCreate,
                      user_id: str = Query(...),
                      db: Session = Depends(get_db)):
    try:
        holding = crud.add_holding(
            db, portfolio_id, user_id,
            symbol=req.symbol, shares=req.shares, avg_cost=req.avg_cost,
            dividends_per_share=req.dividends_per_share, sector=req.sector,
            asset_class=req.asset_class, notes=req.notes,
        )
        return holding
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.get("/api/db/portfolios/{portfolio_id}/holdings")
async def list_holdings(portfolio_id: str, db: Session = Depends(get_db)):
    return [schemas.HoldingResponse.model_validate(h)
            for h in crud.get_holdings(db, portfolio_id)]


@app.patch("/api/db/holdings/{holding_id}", response_model=schemas.HoldingResponse)
async def update_holding(holding_id: str, req: schemas.HoldingUpdate,
                         user_id: str = Query(...),
                         db: Session = Depends(get_db)):
    holding = crud.update_holding(db, holding_id, user_id, **req.model_dump(exclude_none=True))
    if not holding:
        raise HTTPException(404, "Holding not found")
    return holding


@app.delete("/api/db/holdings/{holding_id}")
async def remove_holding(holding_id: str, user_id: str = Query(...),
                         db: Session = Depends(get_db)):
    if not crud.remove_holding(db, holding_id, user_id):
        raise HTTPException(404, "Holding not found")
    return {"status": "deleted"}


# ── Snapshots ────────────────────────────────────────────────

@app.get("/api/db/portfolios/{portfolio_id}/snapshots")
async def list_snapshots(portfolio_id: str,
                         page: int = Query(1, ge=1),
                         page_size: int = Query(20, ge=1, le=100),
                         db: Session = Depends(get_db)):
    result = crud.get_snapshots(db, portfolio_id, page, page_size)
    result["items"] = [schemas.SnapshotResponse.model_validate(s) for s in result["items"]]
    return result


@app.get("/api/db/snapshots/{snapshot_id}", response_model=schemas.SnapshotDetailResponse)
async def get_snapshot(snapshot_id: str, db: Session = Depends(get_db)):
    snapshot = crud.get_snapshot(db, snapshot_id)
    if not snapshot:
        raise HTTPException(404, "Snapshot not found")
    return snapshot


@app.get("/api/db/portfolios/{portfolio_id}/snapshots/latest",
         response_model=schemas.SnapshotResponse)
async def latest_snapshot(portfolio_id: str, db: Session = Depends(get_db)):
    snapshot = crud.get_latest_snapshot(db, portfolio_id)
    if not snapshot:
        raise HTTPException(404, "No snapshots found")
    return snapshot


@app.get("/api/db/portfolios/{portfolio_id}/timeseries/{metric}")
async def snapshot_timeseries(portfolio_id: str, metric: str,
                              limit: int = Query(90, ge=1, le=365),
                              db: Session = Depends(get_db)):
    """Time series of a single metric from snapshot history (for charting)."""
    try:
        return crud.get_snapshot_timeseries(db, portfolio_id, metric, limit)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── Trade Journal ────────────────────────────────────────────

@app.post("/api/db/portfolios/{portfolio_id}/trades", response_model=schemas.TradeResponse)
async def record_trade(portfolio_id: str, req: schemas.TradeCreate,
                       user_id: str = Query(...),
                       db: Session = Depends(get_db)):
    try:
        trade = crud.record_trade(
            db, portfolio_id, user_id,
            symbol=req.symbol, action=req.action, shares=req.shares,
            price=req.price, total_cost=req.total_cost,
            trade_type=req.trade_type, simulation_result=req.simulation_result,
            notes=req.notes,
        )
        return trade
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.get("/api/db/portfolios/{portfolio_id}/trades")
async def list_trades(portfolio_id: str,
                      trade_type: Optional[str] = None,
                      page: int = Query(1, ge=1),
                      page_size: int = Query(50, ge=1, le=100),
                      db: Session = Depends(get_db)):
    result = crud.get_trades(db, portfolio_id, page, page_size, trade_type)
    result["items"] = [schemas.TradeResponse.model_validate(t) for t in result["items"]]
    return result


@app.get("/api/db/portfolios/{portfolio_id}/trades/summary")
async def trade_summary(portfolio_id: str, db: Session = Depends(get_db)):
    return crud.get_trade_summary(db, portfolio_id)


# ── Watchlist ────────────────────────────────────────────────

@app.post("/api/db/users/{user_id}/watchlist", response_model=schemas.WatchlistResponse)
async def add_to_watchlist(user_id: str, req: schemas.WatchlistAdd,
                           db: Session = Depends(get_db)):
    return crud.add_to_watchlist(db, user_id, req.symbol, req.target_price, req.notes)


@app.get("/api/db/users/{user_id}/watchlist")
async def get_watchlist(user_id: str, db: Session = Depends(get_db)):
    return [schemas.WatchlistResponse.model_validate(w)
            for w in crud.get_watchlist(db, user_id)]


@app.delete("/api/db/watchlist/{item_id}")
async def remove_from_watchlist(item_id: str, user_id: str = Query(...),
                                db: Session = Depends(get_db)):
    if not crud.remove_from_watchlist(db, item_id, user_id):
        raise HTTPException(404, "Watchlist item not found")
    return {"status": "deleted"}


@app.delete("/api/db/users/{user_id}/watchlist/{symbol}")
async def remove_watchlist_by_symbol(user_id: str, symbol: str,
                                     db: Session = Depends(get_db)):
    if not crud.remove_from_watchlist_by_symbol(db, user_id, symbol):
        raise HTTPException(404, "Symbol not in watchlist")
    return {"status": "deleted"}


# ── Alerts ───────────────────────────────────────────────────

@app.post("/api/db/users/{user_id}/alerts", response_model=schemas.AlertResponse)
async def create_alert(user_id: str, req: schemas.AlertCreate,
                       db: Session = Depends(get_db)):
    return crud.create_alert(
        db, user_id, req.metric, req.condition, req.threshold,
        symbol=req.symbol, portfolio_id=req.portfolio_id,
    )


@app.get("/api/db/users/{user_id}/alerts")
async def list_alerts(user_id: str,
                      active_only: bool = Query(True),
                      db: Session = Depends(get_db)):
    return [schemas.AlertResponse.model_validate(a)
            for a in crud.get_alerts(db, user_id, active_only)]


@app.patch("/api/db/alerts/{alert_id}", response_model=schemas.AlertResponse)
async def update_alert(alert_id: str, req: schemas.AlertUpdate,
                       user_id: str = Query(...),
                       db: Session = Depends(get_db)):
    alert = crud.update_alert(db, alert_id, user_id, **req.model_dump(exclude_none=True))
    if not alert:
        raise HTTPException(404, "Alert not found")
    return alert


@app.delete("/api/db/alerts/{alert_id}")
async def delete_alert(alert_id: str, user_id: str = Query(...),
                       db: Session = Depends(get_db)):
    if not crud.delete_alert(db, alert_id, user_id):
        raise HTTPException(404, "Alert not found")
    return {"status": "deleted"}


# ── Audit Log ────────────────────────────────────────────────

@app.get("/api/db/users/{user_id}/audit")
async def user_audit_log(user_id: str,
                         action: Optional[str] = None,
                         page: int = Query(1, ge=1),
                         page_size: int = Query(50, ge=1, le=100),
                         db: Session = Depends(get_db)):
    result = crud.get_audit_log(db, user_id, action, page, page_size)
    result["items"] = [schemas.AuditLogResponse.model_validate(e) for e in result["items"]]
    return result


@app.get("/api/db/users/{user_id}/activity")
async def user_activity_summary(user_id: str, db: Session = Depends(get_db)):
    """High-level activity breakdown for a user."""
    return crud.get_user_activity_summary(db, user_id)


# ── Admin Dashboard ──────────────────────────────────────────

@app.post("/api/db/admin/login")
async def admin_login(req: schemas.UserLogin, request: Request,
                      db: Session = Depends(get_db)):
    """Authenticate as admin. Returns user if they have admin privileges."""
    user = crud.authenticate_user(
        db, req.username, req.password,
        ip=request.client.host if request.client else None,
    )
    if not user:
        raise HTTPException(401, "Invalid credentials")
    if not user.is_admin:
        raise HTTPException(403, "Access denied: admin privileges required")
    return {"ok": True, "username": user.username, "user_id": user.id}


@app.post("/api/db/admin/promote/{username}")
async def promote_to_admin(username: str, admin_key: str = Query(...),
                           db: Session = Depends(get_db)):
    """Promote a user to admin. Requires ADMIN_KEY env var (must be set in config/.env)."""
    import os
    expected_key = os.getenv("ADMIN_KEY")
    if not expected_key:
        raise HTTPException(503, "ADMIN_KEY not configured in environment")
    if not hmac.compare_digest(admin_key, expected_key):
        raise HTTPException(403, "Invalid admin key")
    user = crud.get_user_by_username(db, username)
    if not user:
        raise HTTPException(404, f"User '{username}' not found")
    user.is_admin = True
    crud.audit_log(db, user.id, "promote_admin", "user", user.id)
    db.commit()
    return {"ok": True, "message": f"User '{username}' is now an admin"}


@app.get("/api/db/admin/overview")
async def admin_overview(user_id: str = Query(..., description="Admin user ID"),
                         db: Session = Depends(get_db)):
    """Full database overview for the admin panel. Requires admin user_id."""
    admin_user = crud.get_user(db, user_id)
    if not admin_user or not admin_user.is_admin:
        raise HTTPException(403, "Access denied: admin privileges required")
    from backend.database.models import (
        User, Portfolio, Holding, AnalysisSnapshot,
        TradeJournal, Watchlist, Alert, AuditLog,
    )
    from sqlalchemy import func, desc

    def _serialize_rows(rows, columns):
        return [dict(zip(columns, r)) for r in rows]

    # Stats
    stats = {
        "users": db.query(func.count(User.id)).scalar(),
        "portfolios": db.query(func.count(Portfolio.id)).scalar(),
        "holdings": db.query(func.count(Holding.id)).scalar(),
        "snapshots": db.query(func.count(AnalysisSnapshot.id)).scalar(),
        "trades": db.query(func.count(TradeJournal.id)).scalar(),
        "watchlist": db.query(func.count(Watchlist.id)).scalar(),
        "alerts": db.query(func.count(Alert.id)).scalar(),
        "audit_events": db.query(func.count(AuditLog.id)).scalar(),
    }

    # Users
    users = db.execute(
        db.query(User.username, User.email, User.is_active, User.created_at, User.last_login)
        .order_by(desc(User.created_at)).statement
    ).fetchall()

    # Portfolios with user
    portfolios = db.execute(
        db.query(User.username, Portfolio.name, Portfolio.is_default, Portfolio.created_at)
        .join(User, User.id == Portfolio.user_id)
        .order_by(desc(Portfolio.created_at)).statement
    ).fetchall()

    # Holdings with user
    holdings_rows = db.execute(
        db.query(User.username, Holding.symbol, Holding.shares, Holding.avg_cost,
                 Holding.asset_class, Holding.added_at)
        .join(Portfolio, Portfolio.id == Holding.portfolio_id)
        .join(User, User.id == Portfolio.user_id)
        .order_by(User.username, Holding.symbol).statement
    ).fetchall()

    # Snapshots
    snapshots = db.execute(
        db.query(User.username, AnalysisSnapshot.total_value, AnalysisSnapshot.sharpe_ratio,
                 AnalysisSnapshot.portfolio_beta, AnalysisSnapshot.var_95,
                 AnalysisSnapshot.num_holdings, AnalysisSnapshot.created_at)
        .join(Portfolio, Portfolio.id == AnalysisSnapshot.portfolio_id)
        .join(User, User.id == Portfolio.user_id)
        .order_by(desc(AnalysisSnapshot.created_at)).limit(50).statement
    ).fetchall()

    # Trades
    trades = db.execute(
        db.query(User.username, TradeJournal.symbol, TradeJournal.action,
                 TradeJournal.shares, TradeJournal.price, TradeJournal.trade_type,
                 TradeJournal.executed_at)
        .join(Portfolio, Portfolio.id == TradeJournal.portfolio_id)
        .join(User, User.id == Portfolio.user_id)
        .order_by(desc(TradeJournal.executed_at)).limit(50).statement
    ).fetchall()

    # Watchlist
    watchlist_rows = db.execute(
        db.query(User.username, Watchlist.symbol, Watchlist.target_price,
                 Watchlist.notes, Watchlist.added_at)
        .join(User, User.id == Watchlist.user_id)
        .order_by(desc(Watchlist.added_at)).statement
    ).fetchall()

    # Alerts
    alerts_rows = db.execute(
        db.query(User.username, Alert.symbol, Alert.metric, Alert.condition,
                 Alert.threshold, Alert.is_active, Alert.trigger_count, Alert.created_at)
        .join(User, User.id == Alert.user_id)
        .order_by(desc(Alert.created_at)).statement
    ).fetchall()

    # Audit log (last 100)
    audit = db.execute(
        db.query(User.username, AuditLog.action, AuditLog.resource_type,
                 AuditLog.resource_id, AuditLog.timestamp)
        .outerjoin(User, User.id == AuditLog.user_id)
        .order_by(desc(AuditLog.timestamp)).limit(100).statement
    ).fetchall()

    return {
        "stats": stats,
        "users": _serialize_rows(users, ["username", "email", "is_active", "created_at", "last_login"]),
        "portfolios": _serialize_rows(portfolios, ["username", "name", "is_default", "created_at"]),
        "holdings": _serialize_rows(holdings_rows, ["username", "symbol", "shares", "avg_cost", "asset_class", "added_at"]),
        "snapshots": _serialize_rows(snapshots, ["username", "total_value", "sharpe_ratio", "portfolio_beta", "var_95", "num_holdings", "created_at"]),
        "trades": _serialize_rows(trades, ["username", "symbol", "action", "shares", "price", "trade_type", "executed_at"]),
        "watchlist": _serialize_rows(watchlist_rows, ["username", "symbol", "target_price", "notes", "added_at"]),
        "alerts": _serialize_rows(alerts_rows, ["username", "symbol", "metric", "condition", "threshold", "is_active", "trigger_count", "created_at"]),
        "audit": _serialize_rows(audit, ["username", "action", "resource_type", "resource_id", "timestamp"]),
    }


# ── Helpers ─────────────────────────────────────────────────

def _build_predictions_prompt(pm_markets: list, kalshi_events: list) -> str:
    lines = ["Analyze these trending prediction markets and provide key insights:\n"]
    lines.append("POLYMARKET (top markets by 24h volume):")
    for m in pm_markets[:7]:
        yes = round(m["outcome_prices"][0] * 100) if m.get("outcome_prices") and len(m.get("outcome_prices",[])) > 0 else 0
        lines.append(f"  {m['question']} => {yes}% Yes (volume ${m.get('volume', 0):,.0f})")
    lines.append("\nKALSHI (top events by volume):")
    for e in kalshi_events[:7]:
        yes = round(e.get("yes_price", 0) * 100)
        lines.append(f"  [{e.get('category', '')}] {e['title']} => {yes}% Yes (volume ${e.get('volume', 0):,.0f})")
    lines.append("\nProvide: 1) Key themes across markets 2) Markets with extreme probabilities as potential catalysts 3) Any implications for financial portfolios")
    return "\n".join(lines)


def _build_insight_prompt(
    analytics: dict,
    macro: dict,
    news: list,
    monte_carlo: dict | None = None,
    efficient_frontier_data: dict | None = None,
    correlation_data: dict | None = None,
    stress_data: dict | None = None,
) -> str:
    """Build a rich prompt for FinGPT to generate a fully AI-native portfolio insight."""
    summary = analytics.get("summary", {})
    weights = analytics.get("weights", {})

    holdings_lines = []
    for h in analytics.get("holdings", []):
        if "error" not in h:
            sym = h["symbol"]
            w = weights.get(sym, 0) * 100
            holdings_lines.append(
                f"  {sym}: {w:.1f}% weight, value ${h.get('position_value', 'NA')}, "
                f"return {h.get('total_return_pct', 'NA')}%, "
                f"volatility {h.get('volatility', 'NA')}, "
                f"sharpe {h.get('sharpe_ratio', 'NA')}, "
                f"beta {h.get('beta', 'NA')}, "
                f"RSI {h.get('rsi_14', 'NA')} ({h.get('rsi_label', 'NA')}), "
                f"max drawdown {h.get('max_drawdown', 'NA')}%"
            )
    holdings_text = "\n".join(holdings_lines) or "  No valid holdings."

    macro_lines = []
    for key, val in macro.items():
        if isinstance(val, dict) and "value" in val:
            macro_lines.append(f"  {key}: {val['value']} {val.get('unit', '')} (as of {val.get('date', 'NA')})")
    macro_text = "\n".join(macro_lines) or "  No macro data."

    headlines = "\n".join(f"  - {a['title']}" for a in news[:5] if a.get("title")) or "  No recent headlines."

    risk_lines = []
    if isinstance(monte_carlo, dict) and not monte_carlo.get("error"):
        risk_lines += [
            f"  30-day VaR 95%: {monte_carlo.get('var_95', 'NA')}% (${monte_carlo.get('var_95_dollar', 'NA')})",
            f"  30-day CVaR 95%: {monte_carlo.get('cvar_95', 'NA')}% (${monte_carlo.get('cvar_95_dollar', 'NA')})",
            f"  Expected 30-day return (simulation): {monte_carlo.get('expected_return', 'NA')}%",
        ]
    if isinstance(stress_data, dict) and not stress_data.get("error"):
        scenarios = stress_data.get("scenarios", [])
        if scenarios:
            worst = min(scenarios, key=lambda s: s.get("portfolio_return_pct", 0))
            risk_lines.append(f"  Worst historical stress scenario: {worst.get('name')} => {worst.get('portfolio_return_pct', 'NA')}% (${worst.get('portfolio_loss_dollar', 'NA')})")
    risk_text = "\n".join(risk_lines) or "  No risk data available."

    frontier_text = ""
    if isinstance(efficient_frontier_data, dict) and not efficient_frontier_data.get("error"):
        ms = efficient_frontier_data.get("max_sharpe", {})
        mv = efficient_frontier_data.get("min_volatility", {})
        cur = efficient_frontier_data.get("current", {})
        opt_weights = ", ".join(f"{s} {w:.0f}%" for s, w in sorted((ms.get("weights") or {}).items(), key=lambda x: x[1], reverse=True)[:3])
        frontier_text = (
            f"\nOptimization (Efficient Frontier):\n"
            f"  Current: return {cur.get('return', 'NA')}%, volatility {cur.get('volatility', 'NA')}%\n"
            f"  Max-Sharpe target: return {ms.get('return', 'NA')}%, volatility {ms.get('volatility', 'NA')}%, sharpe {ms.get('sharpe', 'NA')} — weights: {opt_weights}\n"
            f"  Min-Volatility target: return {mv.get('return', 'NA')}%, volatility {mv.get('volatility', 'NA')}%"
        )

    corr_text = ""
    if isinstance(correlation_data, dict) and not correlation_data.get("error"):
        corr_text = f"\nCorrelation: avg pairwise {correlation_data.get('avg_correlation', 'NA')} — {correlation_data.get('interpretation', '')}"

    tariff = summary.get("tariff_exposure") or {}
    tariff_text = (
        f"\nTariff exposure: {tariff.get('portfolio_impact_pct', 'NA')}% portfolio impact "
        f"(rate {tariff.get('tariff_rate_pct', 'NA')}%, pass-through {tariff.get('pass_through_pct', 'NA')}%)"
        if tariff else ""
    )

    return f"""[INST] You are a senior portfolio analyst at a hedge fund. A client has shared their portfolio data. Write a concise, professional analysis in plain English. Use the numbers. Do not repeat the data back — go straight into your assessment.

Portfolio value: ${summary.get('total_value', 'NA')} | Return: {summary.get('total_return_pct', 'NA')}% | Volatility: {summary.get('portfolio_volatility', 'NA')} | Sharpe: {summary.get('portfolio_sharpe', 'NA')} | Sortino: {summary.get('portfolio_sortino', 'NA')} | Beta: {summary.get('portfolio_beta', 'NA')} | Alpha: {summary.get('portfolio_alpha', 'NA')}% | HHI: {summary.get('hhi', 'NA')} | Effective N: {summary.get('effective_n', 'NA')}

Holdings: {" | ".join(holdings_lines[:5])}

Risk: {" | ".join(risk_lines[:3])}
{frontier_text}{corr_text}

Macro: {" | ".join(macro_lines[:4])}
News: {" | ".join(f'{a["title"]}' for a in news[:3] if a.get("title"))}

Write 3-4 paragraphs: (1) overall verdict on this portfolio, (2) the biggest risk right now and why it matters, (3) which holdings are working and which are dragging, (4) the top 2 actions the investor should take. Be direct. [/INST]

This portfolio"""


def _clean_model_output(text: str) -> str:
    """Strip Llama-2-chat prompt echoes and truncate at a complete sentence."""
    import re

    # Strip the [INST]...[/INST] block if the model echoes it back
    text = re.sub(r'\[INST\].*?\[/INST\]\s*', '', text, flags=re.DOTALL).strip()

    # Remove any remaining prompt-data lines that leaked through
    clean = []
    data_echo = re.compile(
        r'Holdings:|Paragraph \d|^\s*Portfolio:|^\s*Risk:|^\s*Macro:|^\s*News:|^\s*Optimal',
        re.IGNORECASE,
    )
    for line in text.splitlines():
        if data_echo.match(line.strip()):
            continue
        clean.append(line)
    text = "\n".join(clean).strip()

    # Truncate at the last complete sentence to avoid mid-word cutoffs
    for end_char in ('. ', '.\n', '!', '?'):
        pos = text.rfind(end_char)
        if pos > len(text) // 2:
            text = text[:pos + 1].strip()
            break

    return text


def _fmt_money(value, default: str = "NA") -> str:
    try:
        amount = float(value)
        if amount < 0:
            return f"-${abs(amount):,.2f}"
        return f"${amount:,.2f}"
    except Exception:
        return default


def _fmt_pct(value, default: str = "NA", already_pct: bool = False) -> str:
    try:
        pct = float(value) if already_pct else float(value) * 100
        return f"{pct:.2f}%"
    except Exception:
        return default


def _fmt_num(value, digits: int = 2, default: str = "NA") -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return default


def _portfolio_recommendations(analytics: dict, monte_carlo: dict, efficient_frontier_data: dict) -> list[str]:
    summary = analytics.get("summary", {})
    holdings = [h for h in analytics.get("holdings", []) if not h.get("error")]
    weights = analytics.get("weights", {})
    recs: list[str] = []
    total_value = float(summary.get("total_value") or 0)

    if weights:
        largest_symbol, largest_weight = max(weights.items(), key=lambda item: item[1])
        if largest_weight > 0.40:
            target_weight = 0.35
            trim_value = max(0, (largest_weight - target_weight) * total_value)
            recs.append(
                f"Reduce {largest_symbol} from {largest_weight * 100:.1f}% toward a 35% cap (trim ~{_fmt_money(trim_value)}). "
                f"A single stock above 40% means one bad earnings report or regulatory headline can materially damage the whole portfolio — "
                f"concentration risk this high is rarely compensated by extra return."
            )

    hhi = summary.get("hhi")
    effective_n = summary.get("effective_n")
    if hhi is not None and effective_n is not None:
        try:
            if float(hhi) > 0.30 or float(effective_n) < 4:
                recs.append(
                    f"Add new capital to uncorrelated positions rather than existing holdings. "
                    f"HHI is {_fmt_num(hhi, 3)} and effective N is {_fmt_num(effective_n, 2)} — "
                    f"meaning the portfolio behaves like only {_fmt_num(effective_n, 2)} equal-weight stocks. "
                    f"True diversification requires holdings that move independently; adding more of the same names does not help."
                )
        except Exception:
            pass

    beta = summary.get("portfolio_beta")
    if beta is not None:
        try:
            volatility = float(summary.get("portfolio_volatility") or 0)
            if float(beta) > 1.10:
                recs.append(
                    f"Lower market beta by moving part of the highest-beta holding into lower-beta equity, "
                    f"short-duration Treasury, or cash. Portfolio beta is {_fmt_num(beta, 2)}."
                )
            elif float(beta) < 0.80 and volatility > 0.30:
                recs.append(
                    f"Do not mistake low SPY beta for low risk. Portfolio beta is only {_fmt_num(beta, 2)}, "
                    f"but annualized volatility is {_fmt_pct(volatility)}, so the risk is coming from idiosyncratic "
                    f"or non-equity exposure rather than broad-market sensitivity."
                )
            elif float(beta) < 0.80:
                recs.append(
                    f"If growth is the goal, consider adding measured equity exposure. Portfolio beta is "
                    f"{_fmt_num(beta, 2)}, below broad-market sensitivity."
                )
        except Exception:
            pass

    sharpe = summary.get("portfolio_sharpe")
    alpha = summary.get("portfolio_alpha")
    if sharpe is not None:
        try:
            if float(sharpe) < 0:
                negative = [
                    h for h in holdings
                    if h.get("sharpe_ratio") is not None and float(h.get("sharpe_ratio") or 0) < 0
                ]
                names = ", ".join(h.get("symbol") for h in negative[:3]) or "the negative-Sharpe positions"
                recs.append(
                    f"Do not judge this only by the big gain. Risk-adjusted performance is weak: portfolio Sharpe is "
                    f"{_fmt_num(sharpe, 2)} and Jensen alpha is {_fmt_pct(alpha)}. Review {names} first."
                )
        except Exception:
            pass

    overbought = [
        h for h in holdings
        if h.get("rsi_14") is not None and float(h.get("rsi_14") or 0) >= 70
    ]
    if overbought:
        names = ", ".join(f"{h.get('symbol')} RSI {_fmt_num(h.get('rsi_14'), 1)}" for h in overbought[:3])
        recs.append(
            f"Avoid chasing the hottest winner immediately. {names} is overbought, so use staged buys or wait for a pullback."
        )

    if isinstance(monte_carlo, dict):
        cvar_95 = monte_carlo.get("cvar_95")
        if cvar_95 is not None:
            try:
                if float(cvar_95) < -10:
                    recs.append(
                        f"Set a downside-risk rule before adding more exposure. The 30-day 95% CVaR is "
                        f"{_fmt_pct(cvar_95, already_pct=True)}, or about {_fmt_money(monte_carlo.get('cvar_95_dollar'))}, "
                        f"in the simulated bad-tail case."
                    )
            except Exception:
                pass

    if isinstance(efficient_frontier_data, dict):
        max_sharpe = efficient_frontier_data.get("max_sharpe", {})
        opt_weights = max_sharpe.get("weights", {})
        if opt_weights:
            ordered = sorted(opt_weights.items(), key=lambda item: item[1], reverse=True)
            top_weights = ", ".join(f"{symbol} {weight:.0f}%" for symbol, weight in ordered[:3])
            recs.append(
                f"Use the efficient-frontier target as a reference, not an autopilot trade: max-Sharpe weights are "
                f"{top_weights}, with expected return {_fmt_pct(max_sharpe.get('return'), already_pct=True)} "
                f"and volatility {_fmt_pct(max_sharpe.get('volatility'), already_pct=True)}."
            )

    tax_candidates = []
    for h in holdings:
        tax = h.get("tax") or {}
        if tax.get("type") == "loss":
            tax_candidates.append(h.get("symbol"))
    if tax_candidates:
        recs.append(
            f"Review tax-loss harvesting for {', '.join(tax_candidates)} before making replacement trades."
        )

    if not recs:
        recs.append("Keep the current core, but rebalance periodically so no single position drifts far above target weight.")
        recs.append("Add new capital to the most underweight or lowest-correlation holding rather than chasing the recent winner.")
        recs.append("Use a written risk limit for maximum drawdown and 30-day VaR before increasing position sizes.")

    return recs[:6]


def _portfolio_diagnosis(analytics: dict, monte_carlo: dict, efficient_frontier_data: dict) -> list[str]:
    summary = analytics.get("summary", {})
    holdings = [h for h in analytics.get("holdings", []) if not h.get("error")]
    weights = analytics.get("weights", {})
    if not holdings:
        return ["There are no valid holdings to diagnose yet."]

    largest = max(holdings, key=lambda h: weights.get(h.get("symbol"), 0))
    best_return = max(holdings, key=lambda h: h.get("total_return_pct", float("-inf")))
    weakest_sharpe = min(holdings, key=lambda h: h.get("sharpe_ratio", float("inf")))
    highest_beta = max(holdings, key=lambda h: h.get("beta", float("-inf")))
    total_return = float(summary.get("total_return_pct") or 0)
    sharpe = float(summary.get("portfolio_sharpe") or 0)
    beta = float(summary.get("portfolio_beta") or 0)
    effective_n = float(summary.get("effective_n") or 0)

    verdict = "strong absolute gains but weak risk-adjusted quality"
    if total_return < 0:
        verdict = "negative absolute returns — the portfolio lost money in real terms"
    elif sharpe > 1:
        verdict = "strong performance both in raw returns and on a risk-adjusted basis"
    elif sharpe > 0:
        verdict = "positive returns, but you are not being compensated enough for the risk you are taking"

    sharpe_explain = (
        "negative — meaning a savings account would have beaten this portfolio on a risk-adjusted basis" if sharpe < 0
        else "below average — returns exist but not enough reward per unit of risk" if sharpe < 1
        else "good — solid reward per unit of risk" if sharpe < 2
        else "excellent — strong reward per unit of risk"
    )

    beta_explain = (
        f"above 1 — for every 1% the S&P 500 moves, this portfolio typically moves {_fmt_num(beta, 2)}%, amplifying both gains and losses"
        if beta > 1.05
        else f"below 1 — the portfolio moves less than the market ({_fmt_num(beta, 2)}x), which reduces both upside and downside"
        if beta < 0.95
        else "close to 1 — the portfolio tracks the broad market closely"
    )

    eff_n_explain = (
        f"Despite holding {len(holdings)} stock{'s' if len(holdings) != 1 else ''}, the portfolio behaves like only "
        f"{_fmt_num(effective_n, 1)} equally-weighted positions — because concentration in a few names dominates."
        if effective_n < len(holdings) * 0.6
        else f"The portfolio's {len(holdings)} holdings provide reasonably balanced exposure, equivalent to {_fmt_num(effective_n, 1)} equal-weight positions."
    )

    lines = [
        f"**Overall verdict:** {verdict}. Total return is {_fmt_pct(total_return, already_pct=True)}, "
        f"but raw returns alone do not tell the full story — see the risk-adjusted metrics below.",

        f"**Sharpe ratio: {_fmt_num(sharpe, 2)}** — this measures how much return you earn per unit of risk. "
        f"It is currently {sharpe_explain}. The scale: below 0 = worse than cash, 0–1 = below average, 1–2 = good, 2+ = excellent.",

        f"**Concentration: {largest.get('symbol')} is {weights.get(largest.get('symbol'), 0) * 100:.1f}% of the portfolio** "
        f"({_fmt_money(largest.get('position_value'))}). {eff_n_explain} "
        f"High concentration means one bad earnings report can materially hurt the whole portfolio.",

        f"**Market sensitivity (beta): {_fmt_num(beta, 2)}** — {beta_explain}.",

        f"**Best performer: {best_return.get('symbol')}** at {_fmt_pct(best_return.get('total_return_pct'), already_pct=True)} total return. "
        f"**Weakest risk-adjusted holding: {weakest_sharpe.get('symbol')}** with Sharpe {_fmt_num(weakest_sharpe.get('sharpe_ratio'), 2)} "
        f"— this position is taking on risk without delivering proportional returns. "
        f"**Most market-sensitive: {highest_beta.get('symbol')}** (beta {_fmt_num(highest_beta.get('beta'), 2)}) — moves the most when the market swings.",
    ]

    if isinstance(monte_carlo, dict) and not monte_carlo.get("error"):
        cvar = monte_carlo.get("cvar_95")
        cvar_dollar = monte_carlo.get("cvar_95_dollar")
        lines.append(
            f"**Tail risk (CVaR 95%): {_fmt_pct(cvar, already_pct=True)}** — "
            f"in the worst 5% of simulated 30-day periods, the average loss would be {_fmt_money(cvar_dollar)}. "
            f"This is not a hypothetical — it is modeled from your actual holdings' volatility and correlations. "
            f"CVaR goes beyond VaR by averaging the entire bad tail, not just the threshold."
        )

    if isinstance(efficient_frontier_data, dict) and not efficient_frontier_data.get("error"):
        max_sharpe = efficient_frontier_data.get("max_sharpe", {})
        opt_weights = max_sharpe.get("weights") or {}
        if opt_weights:
            top = ", ".join(f"{symbol} {weight:.0f}%" for symbol, weight in sorted(opt_weights.items(), key=lambda x: x[1], reverse=True)[:3])
            ms = max_sharpe.get("sharpe")
            lines.append(
                f"**Efficient frontier gap:** The Markowitz optimizer finds that a mix of {top} would maximize the Sharpe ratio "
                f"(target Sharpe: {_fmt_num(ms, 2)} vs current {_fmt_num(sharpe, 2)}). "
                f"This is a mathematical reference point — use it as a directional signal for rebalancing, not a trade order."
            )

    return lines


def _build_full_portfolio_report(
    analytics: dict,
    monte_carlo: dict,
    efficient_frontier_data: dict,
    correlation_data: dict,
    stress_data: dict,
    ai_note: str | None = None,
) -> str:
    summary = analytics.get("summary", {})
    holdings = [h for h in analytics.get("holdings", []) if not h.get("error")]
    weights = analytics.get("weights", {})

    lines = [
        "## Portfolio Diagnosis",
        "",
    ]
    lines.extend(f"- {line}" for line in _portfolio_diagnosis(analytics, monte_carlo, efficient_frontier_data))
    lines.extend([
        "",
        "### What I Would Do Next",
    ])
    for idx, rec in enumerate(_portfolio_recommendations(analytics, monte_carlo, efficient_frontier_data), start=1):
        lines.append(f"{idx}. {rec}")

    # ── Portfolio Snapshot ──────────────────────────────────
    sharpe_val = float(summary.get("portfolio_sharpe") or 0)
    sortino_val = float(summary.get("portfolio_sortino") or 0)
    beta_val = float(summary.get("portfolio_beta") or 0)
    alpha_val = float(summary.get("portfolio_alpha") or 0)
    vol_val = float(summary.get("portfolio_volatility") or 0)
    hhi_val = float(summary.get("hhi") or 0)
    eff_n_val = float(summary.get("effective_n") or 0)

    sharpe_label = (
        "worse than cash" if sharpe_val < 0
        else "below average" if sharpe_val < 1
        else "good" if sharpe_val < 2
        else "excellent"
    )
    beta_label = (
        f"amplifies market moves by {beta_val:.2f}x — higher risk and higher reward than the index"
        if beta_val > 1.05
        else f"dampens market moves to {beta_val:.2f}x — less volatile than the index"
        if beta_val < 0.95
        else "tracks the market closely"
    )
    alpha_label = (
        f"positive — the portfolio beat a passive SPY strategy by {_fmt_pct(alpha_val)} annually after accounting for market risk"
        if alpha_val > 0
        else f"negative — the portfolio underperformed a passive SPY strategy by {_fmt_pct(abs(alpha_val))} annually"
    )
    hhi_label = (
        "very concentrated — one or two names dominate" if hhi_val > 0.5
        else "moderately concentrated — a few positions drive returns" if hhi_val > 0.25
        else "reasonably diversified" if hhi_val > 0.10
        else "well diversified"
    )

    lines.extend([
        "",
        "### Portfolio Snapshot",
        f"- **Total value:** {_fmt_money(summary.get('total_value'))} (cost basis: {_fmt_money(summary.get('total_cost'))})",
        f"- **Holding-period return:** {_fmt_pct(summary.get('total_return_pct'), already_pct=True)} — "
        f"this is the raw gain/loss since purchase, including dividends. It does not account for risk.",
        f"- **Annualized volatility:** {_fmt_pct(summary.get('portfolio_volatility'))} — "
        f"how much the portfolio's value typically swings in a year. "
        f"{'High — expect large month-to-month swings.' if vol_val > 0.30 else 'Moderate.' if vol_val > 0.15 else 'Low — relatively stable.'}",
        f"- **Beta vs S&P 500:** {_fmt_num(beta_val, 2)} — {beta_label}.",
        f"- **Sharpe ratio:** {_fmt_num(sharpe_val, 2)} ({sharpe_label}) — "
        f"measures return per unit of risk. Scale: <0 = worse than cash, 0–1 = below average, 1–2 = good, 2+ = excellent.",
        f"- **Sortino ratio:** {_fmt_num(sortino_val, 2)} — "
        f"like Sharpe but only penalises downside volatility (bad days). "
        f"{'Sortino is meaningfully higher than Sharpe, meaning most of the volatility is on the upside — that is a good sign.' if sortino_val > sharpe_val * 1.3 else 'Close to the Sharpe ratio, meaning volatility is fairly symmetric.'}",
        f"- **Jensen alpha:** {_fmt_pct(alpha_val)} — {alpha_label}.",
        f"- **HHI concentration index:** {_fmt_num(hhi_val, 3)} ({hhi_label}). "
        f"Scale: 0 = perfectly spread, 1 = single stock. Effective positions: {_fmt_num(eff_n_val, 1)} "
        f"(the number of equal-weight stocks that would produce the same concentration).",
        "",
        "### Holding-Level Read",
        "*Each row: weight in portfolio, return since purchase, how risky (beta & volatility), risk-adjusted quality (Sharpe), and momentum signal (RSI).*",
    ])

    for h in holdings:
        weight = weights.get(h.get("symbol"), 0) * 100
        h_sharpe = float(h.get("sharpe_ratio") or 0)
        h_beta = float(h.get("beta") or 0)
        h_rsi = h.get("rsi_14")
        rsi_note = ""
        if h_rsi is not None:
            try:
                rsi_f = float(h_rsi)
                rsi_note = " — momentum signal: overbought, potential pullback ahead" if rsi_f >= 70 else " — momentum signal: oversold, potential bounce" if rsi_f <= 30 else " — momentum signal: neutral"
            except Exception:
                pass
        sharpe_note = (
            " (drag — taking risk without reward)" if h_sharpe < 0
            else " (below average)" if h_sharpe < 1
            else " (good)" if h_sharpe < 2
            else " (excellent)"
        )
        lines.append(
            f"- **{h.get('symbol')}** — {weight:.1f}% of portfolio ({_fmt_money(h.get('position_value'))}). "
            f"Return: {_fmt_pct(h.get('total_return_pct'), already_pct=True)}. "
            f"Beta: {_fmt_num(h_beta, 2)} ({'more' if h_beta > 1 else 'less'} volatile than market). "
            f"Volatility: {_fmt_pct(h.get('volatility'))}. "
            f"Sharpe: {_fmt_num(h_sharpe, 2)}{sharpe_note}. "
            f"RSI: {h.get('rsi_14', 'NA')}{rsi_note}."
        )

    lines.extend(["", "### Risk Assessment"])
    lines.append(
        "*Risk is measured two ways: VaR (the loss threshold you won't exceed 95% of the time) "
        "and CVaR (the average loss in the worst 5% of scenarios — always worse than VaR).*"
    )
    if isinstance(monte_carlo, dict) and not monte_carlo.get("error"):
        var95 = monte_carlo.get("var_95")
        cvar95 = monte_carlo.get("cvar_95")
        lines.extend([
            f"- **30-day VaR 95%: {_fmt_pct(var95, already_pct=True)}** ({_fmt_money(monte_carlo.get('var_95_dollar'))}) — "
            f"95% of simulated months, the loss stays within this bound.",
            f"- **30-day CVaR 95%: {_fmt_pct(cvar95, already_pct=True)}** ({_fmt_money(monte_carlo.get('cvar_95_dollar'))}) — "
            f"in the worst 5% of months, the *average* loss is this figure. This is the number risk managers care about most.",
            f"- **Expected 30-day return (simulation):** {_fmt_pct(monte_carlo.get('expected_return'), already_pct=True)} — "
            f"the median outcome across 10,000 Monte Carlo paths.",
        ])
    if isinstance(stress_data, dict) and not stress_data.get("error"):
        reverse = stress_data.get("reverse_stress_test", {})
        if reverse:
            lines.append(f"- **Reverse stress test:** {reverse.get('explanation')} — this identifies what market shock would wipe out a target percentage of the portfolio.")
        scenarios = stress_data.get("scenarios", [])
        if scenarios:
            worst = min(scenarios, key=lambda s: s.get("portfolio_return_pct", 0))
            lines.append(
                f"- **Worst historical scenario: {worst.get('name')}** — "
                f"in an equivalent crisis, this portfolio would have lost "
                f"{_fmt_pct(worst.get('portfolio_return_pct'), already_pct=True)} "
                f"({_fmt_money(worst.get('portfolio_loss_dollar'))}) based on current weights and historical drawdowns."
            )

    lines.extend(["", "### Diversification & Correlation"])
    lines.append(
        "*Correlation measures how much your holdings move together. A correlation of +1 means they move in lockstep (no diversification benefit). "
        "A correlation of 0 means they are independent. A correlation of -1 means they are a perfect hedge.*"
    )
    if isinstance(correlation_data, dict) and not correlation_data.get("error"):
        avg_corr = float(correlation_data.get("avg_correlation") or 0)
        corr_label = (
            "high — holdings are moving together, limiting diversification benefit"
            if avg_corr > 0.7
            else "moderate — some diversification benefit, but significant co-movement remains"
            if avg_corr > 0.4
            else "low — holdings are relatively independent, providing genuine diversification"
        )
        lines.append(
            f"- **Average pairwise correlation: {_fmt_num(avg_corr, 3)}** ({corr_label}). "
            f"{correlation_data.get('interpretation', '')}"
        )
    lines.append(
        f"- **HHI: {_fmt_num(hhi_val, 3)}, Effective N: {_fmt_num(eff_n_val, 2)}** — "
        f"lower HHI and higher effective N = better diversification. "
        f"A perfectly equal 10-stock portfolio would have HHI ≈ 0.10 and effective N = 10."
    )

    lines.extend(["", "### Optimization View"])
    lines.append(
        "*The efficient frontier shows the mathematically optimal portfolios — the best return achievable for each level of risk. "
        "Your portfolio likely sits below this curve; the gap shows the cost of current allocation choices.*"
    )
    if isinstance(efficient_frontier_data, dict) and not efficient_frontier_data.get("error"):
        current = efficient_frontier_data.get("current", {})
        max_sharpe = efficient_frontier_data.get("max_sharpe", {})
        min_vol = efficient_frontier_data.get("min_volatility", {})
        lines.extend([
            f"- **Your portfolio today:** expected return {_fmt_pct(current.get('return'), already_pct=True)}, "
            f"volatility {_fmt_pct(current.get('volatility'), already_pct=True)}.",
            f"- **Max-Sharpe portfolio** (best risk-adjusted mix): expected return {_fmt_pct(max_sharpe.get('return'), already_pct=True)}, "
            f"volatility {_fmt_pct(max_sharpe.get('volatility'), already_pct=True)}, Sharpe {_fmt_num(max_sharpe.get('sharpe'), 2)}. "
            f"This is the target allocation the optimizer recommends — treat it as directional, not prescriptive.",
            f"- **Minimum-volatility portfolio** (lowest-risk mix): expected return {_fmt_pct(min_vol.get('return'), already_pct=True)}, "
            f"volatility {_fmt_pct(min_vol.get('volatility'), already_pct=True)}. "
            f"Consider this if preserving capital is the priority over maximising returns.",
        ])

    tariff = summary.get("tariff_exposure") or {}
    if tariff:
        lines.extend([
            "",
            "### Special Exposure Notes",
            f"- AAPL tariff scenario impact: {_fmt_pct(tariff.get('portfolio_impact_pct'), already_pct=True)} "
            f"portfolio impact under the configured assumptions.",
        ])

    if ai_note:
        clean_note = ai_note.strip()
        if clean_note and "Unable to generate" not in clean_note:
            lines.extend(["", "### Veris AI Analyst Note", clean_note])

    return "\n".join(lines)


@app.post("/api/cache/clear")
async def clear_cache(admin_key: str = Query(..., description="ADMIN_KEY required")):
    """Clear the in-memory data cache. Requires ADMIN_KEY to prevent low-grade DoS."""
    expected = os.getenv("ADMIN_KEY")
    if not expected:
        raise HTTPException(503, "ADMIN_KEY not configured")
    if not hmac.compare_digest(admin_key, expected):
        raise HTTPException(403, "Invalid admin key")
    cache.clear()
    logger.info("Cache cleared by admin")
    return {"status": "ok", "message": "Cache cleared"}



# ── On-Demand AI Insight ────────────────────────────────

@app.post("/api/ai-insight")
async def ai_insight_endpoint(req: PortfolioRequest):
    """Fully AI-native portfolio insight — the model reads all data and writes the entire report."""
    model_available = await model.health_check()

    holdings = [h.model_dump() for h in req.holdings]
    for h in holdings:
        h["symbol"] = yf_client.normalize_symbol(h["symbol"])
    symbols = [h["symbol"] for h in holdings]

    async def _fetch(sym):
        try:
            return sym, await yf_client.get_daily(sym)
        except Exception:
            return sym, []

    fetch_syms = symbols + (["SPY"] if "SPY" not in symbols else [])
    price_results, news, macro = await asyncio.gather(
        asyncio.gather(*[_fetch(s) for s in fetch_syms]),
        yf_client.get_news(symbols, limit=8),
        fred.get_macro_snapshot(),
        return_exceptions=False,
    )

    daily_data = {sym: data for sym, data in price_results}
    market_data = daily_data.pop("SPY", []) if "SPY" not in symbols else None

    rf = await _current_risk_free_rate()
    analytics = analyze_portfolio(holdings, daily_data, rf, market_data)

    def _safe(r):
        return {} if isinstance(r, Exception) else r

    mc_result, ef_result, corr_result, stress_result = map(_safe, await asyncio.gather(
        asyncio.to_thread(monte_carlo_simulation, daily_data, holdings),
        asyncio.to_thread(efficient_frontier, daily_data, holdings, rf),
        asyncio.to_thread(correlation_matrix, daily_data, symbols),
        asyncio.to_thread(stress_test, daily_data, holdings, None, market_data),
        return_exceptions=True,
    ))

    # Build a compact prompt — Llama-2-7B has a 700-token output cap,
    # so keeping the input short leaves maximum room for real analysis.
    summary = analytics.get("summary", {})
    weights_map = analytics.get("weights", {})
    holdings_compact = " | ".join(
        f"{h.get('symbol')} {weights_map.get(h.get('symbol'), 0)*100:.0f}% "
        f"(ret {h.get('total_return_pct','NA')}% sharpe {h.get('sharpe_ratio','NA')} beta {h.get('beta','NA')} RSI {h.get('rsi_14','NA')})"
        for h in analytics.get("holdings", [])[:5] if not h.get("error")
    )
    cvar = mc_result.get("cvar_95", "NA") if isinstance(mc_result, dict) else "NA"
    var95 = mc_result.get("var_95", "NA") if isinstance(mc_result, dict) else "NA"
    ms = (ef_result.get("max_sharpe", {}) if isinstance(ef_result, dict) else {})
    ms_weights = ", ".join(f"{s} {w:.0f}%" for s, w in sorted((ms.get("weights") or {}).items(), key=lambda x: x[1], reverse=True)[:3])

    macro_lines = []
    if isinstance(macro, dict):
        for k, v in list(macro.items())[:4]:
            if isinstance(v, dict) and "value" in v:
                macro_lines.append(f"{k}: {v['value']}{v.get('unit','')}")
    macro_compact = " | ".join(macro_lines)

    news_compact = " | ".join(a["title"] for a in (news or [])[:3] if a.get("title"))

    prompt = (
        f"[INST] You are a senior portfolio analyst. Write a 3-paragraph analysis.\n\n"
        f"Holdings: {holdings_compact}\n"
        f"Portfolio: return {summary.get('total_return_pct','NA')}% | vol {summary.get('portfolio_volatility','NA')} | "
        f"sharpe {summary.get('portfolio_sharpe','NA')} | sortino {summary.get('portfolio_sortino','NA')} | "
        f"beta {summary.get('portfolio_beta','NA')} | alpha {summary.get('portfolio_alpha','NA')}% | "
        f"HHI {summary.get('hhi','NA')} | EffN {summary.get('effective_n','NA')}\n"
        f"Risk: VaR95 {var95}% | CVaR95 {cvar}%\n"
        f"Optimal mix: {ms_weights}\n"
        f"Macro: {macro_compact}\n"
        f"News: {news_compact}\n\n"
        f"Paragraph 1: Overall performance verdict — use the actual numbers.\n"
        f"Paragraph 2: Biggest risk right now and why it matters.\n"
        f"Paragraph 3: Two specific actions the investor should take.\n"
        f"[/INST]"
    )

    if not model_available:
        return {
            "insight": "Veris AI is offline. Start the Colab notebook to generate an AI insight.",
            "model_available": False,
            "model_name": model.model_name,
        }

    try:
        resp = await model.generate_insight(prompt)
        raw = resp.get("insight", "") or ""
        insight = _clean_model_output(raw) if len(raw.strip()) > 20 else "The model returned an empty response. Try again."
    except Exception as e:
        logger.warning("FinGPT insight failed: %s", e)
        insight = "Failed to generate insight. Check that the Colab notebook is running."

    return {"insight": insight, "model_available": model_available, "model_name": model.model_name}


# ── AI News Summarization (AlphaSense-inspired) ────────

@app.post("/api/news-digest")
async def news_digest(req: PortfolioRequest):
    """AI-powered news digest for portfolio holdings."""
    holdings = [h.model_dump() for h in req.holdings]
    symbols = [yf_client.normalize_symbol(h["symbol"]) for h in holdings]

    news = await yf_client.get_news(symbols, limit=15)
    if not news:
        return {"digest": [], "summary": "No recent news found for your holdings."}

    digest = []
    for article in news[:10]:
        digest.append({
            "title": article.get("title", ""),
            "source": article.get("source", ""),
            "url": article.get("url", ""),
            "tickers": article.get("tickers", []),
            "sentiment": article.get("fingpt_sentiment", "neutral"),
        })

    model_available = await model.health_check()
    ai_summary = None
    if model_available and digest:
        headlines = "\n".join([f"- {d['title']}" for d in digest[:8]])
        prompt = f"Summarize these news headlines for portfolio with {', '.join(symbols[:5])}. Focus on investor impact. 3-4 bullet points:\n\n{headlines}"
        try:
            resp = await model.generate_insight(prompt)
            ai_summary = resp.get("insight") if resp else None
        except Exception:
            pass

    return {"digest": digest, "ai_summary": ai_summary, "model_available": model_available}

# ── Portfolio Rebalancing (Wealthfront-inspired) ────────

@app.post("/api/rebalance")
async def rebalance_suggestions(req: PortfolioRequest):
    """Suggest rebalancing trades to optimize portfolio allocation."""
    holdings = [h.model_dump() for h in req.holdings]
    for h in holdings:
        h["symbol"] = yf_client.normalize_symbol(h["symbol"])
    symbols = [h["symbol"] for h in holdings]

    async def _fetch(sym):
        try:
            return sym, await yf_client.get_daily(sym)
        except Exception:
            return sym, []

    results = await asyncio.gather(*[_fetch(s) for s in symbols])
    daily_data = {sym: data for sym, data in results}

    positions = []
    total_value = 0
    for h in holdings:
        data = daily_data.get(h["symbol"], [])
        price = float(data[0]["close"]) if data else h["avg_cost"]
        value = h["shares"] * price
        total_value += value
        positions.append({"symbol": h["symbol"], "shares": h["shares"], "price": round(price, 2), "value": round(value, 2)})

    if total_value <= 0:
        return {"suggestions": [], "error": "Portfolio value is zero"}

    for p in positions:
        p["weight"] = round(p["value"] / total_value * 100, 2)

    equal_weight = round(100 / len(positions), 2)
    suggestions = []
    for p in positions:
        drift = p["weight"] - equal_weight
        if abs(drift) > 5:
            action = "REDUCE" if drift > 0 else "ADD"
            trade_value = abs(drift) / 100 * total_value
            trade_shares = round(trade_value / p["price"], 2) if p["price"] > 0 else 0
            suggestions.append({
                "symbol": p["symbol"], "action": action,
                "reason": f"{'Over' if drift > 0 else 'Under'}weight by {abs(drift):.1f}pp ({p['weight']:.1f}% vs {equal_weight:.1f}% target)",
                "current_weight": p["weight"], "target_weight": equal_weight,
                "drift": round(drift, 2), "suggested_shares": trade_shares,
                "suggested_value": round(trade_value, 2),
            })

    suggestions.sort(key=lambda x: abs(x["drift"]), reverse=True)
    hhi = sum((p["weight"]/100)**2 for p in positions)
    effective_n = round(1/hhi, 2) if hhi > 0 else len(positions)

    return {
        "positions": positions, "suggestions": suggestions,
        "total_value": round(total_value, 2), "hhi": round(hhi, 4),
        "effective_n": effective_n, "target": "equal_weight",
    }


# ── Serve Frontend ──────────��────────────────────────���──────

# ── AI Chat (Gemini Flash) ─────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" | "model"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    portfolio_context: Optional[dict] = None
    learning_context: Optional[dict] = None


_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip().strip('"').strip("'")
_gemini_client = None
if _GEMINI_KEY:
    try:
        from google import genai
        _gemini_client = genai.Client(api_key=_GEMINI_KEY)
        logger.info(
            "Gemini chat enabled (key loaded: %s***%s, len=%d)",
            _GEMINI_KEY[:4], _GEMINI_KEY[-3:], len(_GEMINI_KEY),
        )
    except Exception as _e:
        logger.warning("Gemini client init failed: %s", _e)
else:
    logger.info("Gemini chat disabled — GEMINI_API_KEY not set in config/.env")


def _summarize_portfolio_context(ctx: Optional[dict]) -> str:
    if not ctx:
        return "No portfolio loaded yet."
    lines = []
    a = ctx.get("analytics") or {}
    if a:
        lines.append(
            f"Total value: {a.get('total_value')}, Sharpe: {a.get('sharpe')}, "
            f"Vol: {a.get('volatility')}, Beta: {a.get('beta')}, "
            f"Max DD: {a.get('max_drawdown')}"
        )
    holdings = (a.get("holdings") or [])[:20]
    if holdings:
        rows = []
        for h in holdings:
            rows.append(
                f"  - {h.get('symbol')}: {h.get('shares')} sh @ "
                f"${h.get('price')}, weight {h.get('weight')}%, "
                f"vol {h.get('volatility')}, sharpe {h.get('sharpe')}"
            )
        lines.append("Holdings:\n" + "\n".join(rows))
    mc = ctx.get("monte_carlo")
    if mc:
        lines.append(
            f"VaR 95%: {mc.get('var_95')}, CVaR 95%: {mc.get('cvar_95')}"
        )
    return "\n".join(lines) if lines else "Portfolio snapshot unavailable."


def _summarize_learning_context(ctx: Optional[dict]) -> str:
    """Compact learning-mode snapshot: progress + curriculum index."""
    if not ctx:
        return "Learning mode: not active."
    learner = ctx.get("learner") or {}
    stages = ctx.get("stages") or []
    completed = learner.get("completedStages") or []
    xp = learner.get("xp", 0)
    learning_on = learner.get("learningMode", False)
    next_stage = next(
        (s for s in stages if s.get("id") not in completed), None
    )

    lines = [
        f"Learning mode: {'ON' if learning_on else 'OFF'}",
        f"XP: {xp}",
        f"Completed stages: {completed or 'none'}",
        f"Next stage: {next_stage.get('id')} — {next_stage.get('name')}"
        if next_stage else "All stages complete.",
    ]
    if next_stage and next_stage.get("unlockPreview"):
        lines.append(f"Next unlocks: {next_stage['unlockPreview']}")

    if stages:
        lines.append("\nCurriculum:")
        for s in stages:
            status = "✓" if s.get("id") in completed else (
                "▶ in progress" if next_stage and s.get("id") == next_stage.get("id")
                else "🔒 locked"
            )
            lessons = s.get("lessons") or []
            lesson_titles = [l.get("title", "") for l in lessons if l.get("title")]
            lessons_str = (
                "; ".join(lesson_titles[:6])
                + (f" (+{len(lesson_titles) - 6} more)" if len(lesson_titles) > 6 else "")
            )
            lines.append(
                f"  Stage {s.get('id')} {status} — {s.get('name')}: "
                f"{s.get('desc', '')}"
            )
            if lessons_str:
                lines.append(f"      Lessons: {lessons_str}")
    return "\n".join(lines)


# Build Gemini function declarations from the shared MCP tool registry, so
# the in-app chat and the standalone MCP server expose the exact same tools.
try:
    from backend.mcp_tools import TOOLS as _MCP_TOOLS, call_tool as _mcp_call_tool
    _LOCAL_FUNCTION_DECLS = [
        {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}
        for t in _MCP_TOOLS
    ]
    _LOCAL_TOOL_NAMES = {t["name"] for t in _MCP_TOOLS}
    logger.info("Loaded %d local MCP tools for chat function-calling", len(_MCP_TOOLS))
except Exception as _e:
    logger.warning("Local MCP tools failed to load: %s", _e)
    _MCP_TOOLS, _mcp_call_tool, _LOCAL_FUNCTION_DECLS, _LOCAL_TOOL_NAMES = [], None, [], set()

try:
    from backend import vlab_client as _vlab
    _VLAB_AVAILABLE = True
    logger.info("V-Lab MCP client loaded — tools will be discovered on first chat")
except Exception as _e:
    logger.warning("V-Lab MCP client failed to load: %s", _e)
    _vlab = None
    _VLAB_AVAILABLE = False


def _vlab_proxy_name(real_name: str) -> str:
    """Prefix V-Lab tool names so they don't collide with local tool names."""
    return f"vlab_{real_name}" if not real_name.startswith("vlab_") else real_name


def _vlab_real_name(proxied: str) -> str:
    return proxied[len("vlab_"):] if proxied.startswith("vlab_") else proxied


def _sanitize_schema_for_gemini(schema):
    """
    Walk a JSON Schema and strip features Gemini's pydantic validator rejects.

    The newer google-genai SDK requires `enum` values to be strings. V-Lab
    schemas use integer enums (e.g. horizon: [30, 365]) which fail validation.
    We drop those enum constraints — Gemini can still pass any integer per the
    `type: integer` declaration.
    """
    if isinstance(schema, dict):
        cleaned = {}
        for k, v in schema.items():
            if k == "enum" and isinstance(v, list):
                # Keep the enum only if all values are already strings
                if all(isinstance(x, str) for x in v):
                    cleaned[k] = v
                # else drop it
                continue
            cleaned[k] = _sanitize_schema_for_gemini(v)
        return cleaned
    if isinstance(schema, list):
        return [_sanitize_schema_for_gemini(x) for x in schema]
    return schema


async def _build_function_declarations() -> tuple[list[dict], dict[str, str]]:
    """
    Combine local MCP tool declarations with V-Lab's. Returns (declarations,
    routing_map) where routing_map[gemini_name] is either "local" or "vlab".
    """
    decls = list(_LOCAL_FUNCTION_DECLS)
    routing: dict[str, str] = {name: "local" for name in _LOCAL_TOOL_NAMES}

    if _VLAB_AVAILABLE and _vlab is not None:
        try:
            vlab_tools = await _vlab.list_tools()
            for t in vlab_tools:
                gemini_name = _vlab_proxy_name(t["name"])
                if gemini_name in routing:
                    continue  # avoid duplicates if V-Lab and local share a name
                params = t["inputSchema"] or {"type": "object", "properties": {}}
                params = _sanitize_schema_for_gemini(params)
                decls.append({
                    "name": gemini_name,
                    "description": (
                        f"[NYU V-Lab] {t['description']}"
                        if t["description"]
                        else f"[NYU V-Lab] Tool {t['name']} from vlab.stern.nyu.edu"
                    ),
                    "parameters": params,
                })
                routing[gemini_name] = "vlab"
        except Exception as e:
            logger.warning("V-Lab tool discovery skipped: %s", e)

    return decls, routing


async def _dispatch_tool_call(name: str, args: dict, routing: dict[str, str]) -> dict:
    """Route a Gemini function call to the right backend (local or V-Lab)."""
    target = routing.get(name)
    if target == "vlab" and _vlab is not None:
        return await _vlab.call_tool(_vlab_real_name(name), args)
    if target == "local" and _mcp_call_tool is not None:
        return await asyncio.to_thread(_mcp_call_tool, name, args)
    return {"error": f"unknown tool: {name}"}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not _gemini_client:
        raise HTTPException(
            503,
            "Chat unavailable. Set GEMINI_API_KEY in config/.env "
            "(free key: https://aistudio.google.com/apikey)",
        )

    system_instruction = (
        "You are Veris, a financial analyst and tutor built into a portfolio "
        "dashboard. You have two jobs:\n"
        "  1. Answer questions about the user's portfolio — cite specific "
        "     numbers, and CALL tools (don't guess) when fresh data is needed. "
        "     Tools are the authoritative source for volatility numbers.\n"
        "  2. Act as a tutor for the dashboard's learning curriculum — explain "
        "     concepts, summarize lessons, recommend the next stage, and quiz "
        "     the user when asked. When a concept appears in the curriculum, "
        "     explain it in the same spirit as the matching lesson title.\n\n"
        "Tool selection guide:\n"
        "  - For volatility, you have BOTH local tools (computed from yfinance) "
        "    and V-Lab tools (prefixed `vlab_`, sourced from NYU Stern's "
        "    Volatility Lab — Robert Engle's research group, the academic "
        "    gold standard for GARCH-family estimates).\n"
        "  - PREFER V-Lab tools when the user asks for the 'best', "
        "    'authoritative', 'institutional' volatility, or specifically "
        "    mentions V-Lab, NYU, Engle, or research-grade estimates.\n"
        "  - Use the local tools for portfolio-level metrics, when V-Lab "
        "    doesn't cover the asset, or for quick comparisons.\n"
        "  - Cite the source ('V-Lab' vs 'computed locally') in your reply.\n\n"
        "Always cite which lesson/stage you're drawing from when teaching. "
        "After calling tools, summarize results in plain language. Never give "
        "personalized buy/sell advice — frame ideas as trade-offs.\n\n"
        "User's portfolio snapshot:\n"
        + _summarize_portfolio_context(req.portfolio_context)
        + "\n\n"
        + _summarize_learning_context(req.learning_context)
    )

    contents: list[dict] = []
    for m in req.history[-12:]:
        role = "user" if m.role == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m.content}]})
    contents.append({"role": "user", "parts": [{"text": req.message}]})

    decls, routing = await _build_function_declarations()
    config: dict = {
        "system_instruction": system_instruction,
        "temperature": 0.4,
        "max_output_tokens": 1200,
    }
    if decls:
        config["tools"] = [{"function_declarations": decls}]

    tool_calls_made: list[dict] = []
    MAX_HOPS = 5  # cap multi-step tool use to avoid runaway loops

    try:
        for hop in range(MAX_HOPS):
            resp = await asyncio.to_thread(
                _gemini_client.models.generate_content,
                model="gemini-2.5-flash",
                contents=contents,
                config=config,
            )

            # Look for function calls in the response
            fn_calls = []
            candidates = getattr(resp, "candidates", None) or []
            if candidates:
                parts = getattr(candidates[0].content, "parts", []) or []
                for p in parts:
                    fc = getattr(p, "function_call", None)
                    if fc and getattr(fc, "name", None):
                        fn_calls.append(fc)

            if not fn_calls:
                # No more tool calls — return the text reply
                reply = (resp.text or "").strip()
                if not reply:
                    reply = "I couldn't generate a response. Try rephrasing."
                return {
                    "reply": reply,
                    "tool_calls": tool_calls_made,
                }

            # Append the model's tool-calling turn to the conversation
            contents.append({
                "role": "model",
                "parts": [{"function_call": {"name": fc.name, "args": dict(fc.args or {})}} for fc in fn_calls],
            })

            # Execute each tool call (routed to local or V-Lab MCP)
            response_parts = []
            for fc in fn_calls:
                args = dict(fc.args or {})
                target = routing.get(fc.name, "?")
                logger.info("[%s] tool call: %s(%s)", target, fc.name, args)
                result = await _dispatch_tool_call(fc.name, args, routing)
                tool_calls_made.append({
                    "name": fc.name, "target": target,
                    "args": args, "result": result,
                })
                response_parts.append({
                    "function_response": {
                        "name": fc.name,
                        "response": {"result": result},
                    }
                })
            contents.append({"role": "user", "parts": response_parts})

        # Hit hop limit without a final reply
        return {
            "reply": "I called several tools but couldn't summarize them. Try a more focused question.",
            "tool_calls": tool_calls_made,
        }
    except Exception as e:
        logger.exception("Gemini chat failed")
        raise HTTPException(502, f"Chat provider error: {e}")


frontend_dir = Path(__file__).parent.parent / "frontend" / "static"
app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.get("/")
async def serve_frontend():
    return FileResponse(str(frontend_dir / "index.html"))


# ── Run ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("\n  Starting Veris — Portfolio Intelligence...")
    print("   Frontend: http://localhost:8000")
    print("   API docs: http://localhost:8000/docs\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1, limit_concurrency=50, timeout_keep_alive=30)
