"""
app.py — FastAPI backend for FinGPT Portfolio Analyzer.

Run with:  python backend/app.py
Serves API at :8000 and frontend at http://localhost:8000
"""

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
)
from backend.database import init_db, get_db, close_db, crud, schemas

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("fingpt")

# ── Init ────────────────────────────────────────────────────
app = FastAPI(title="FinGPT Portfolio Analyzer")

# Initialize database on startup
@app.on_event("startup")
def startup_db():
    init_db()
    logger.info("Database layer initialized")

@app.on_event("shutdown")
def shutdown_db():
    close_db()
    logger.info("Database connections closed")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:8000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
clients = create_clients()
model = create_model_client()

yf_client = clients["yfinance"]
fred = clients["fred"]
sec = clients["sec"]


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
    """Check backend health and Colab model availability."""
    model_ok = await model.health_check()
    return {
        "backend": "ok",
        "model_server": "connected" if model_ok else "unavailable",
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


@app.get("/api/options/{symbol}")
async def get_options(symbol: str, expiration: str = None):
    """Get options chain for a stock symbol, with Greeks and IV skew.

    The risk free rate passed to Black Scholes is taken from the live 10Y
    treasury if available, otherwise defaults to the Fed Funds rate, and
    finally falls back to 4.35 percent.
    """
    rf = await _current_risk_free_rate()
    result = await yf_client.get_options(symbol.upper(), expiration, risk_free_rate=rf)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


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

    # Run FinGPT sentiment on headlines if model is available
    model_available = await model.health_check()
    if model_available and news:
        headlines = [a["title"] for a in news if a.get("title")]
        sentiments = await model.batch_sentiment(headlines)
        for i, article in enumerate(news):
            if i < len(sentiments):
                article["fingpt_sentiment"] = sentiments[i]

    # 5. AI insight
    ai_insight = None
    if model_available:
        context = _build_insight_prompt(analytics, macro, news)
        insight_resp = await model.generate_insight(context)
        ai_insight = insight_resp.get("insight") or insight_resp.get("error")

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
            return sym, await yf_client.get_daily(sym)
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


# ── Helper ──────────────────────────────────────────────────

def _build_insight_prompt(analytics: dict, macro: dict, news: list) -> str:
    """Build a context string for FinGPT to generate portfolio insight.

    Uses the v5 institutional metrics (HHI, Effective N, Diversification
    Ratio, Treynor, Information Ratio) rather than the old diversification
    score. Avoids hyphens in the plain text so the output is clean.
    """
    summary = analytics.get("summary", {})
    holdings_text = ""
    for h in analytics.get("holdings", []):
        if "error" not in h:
            holdings_text += (
                f"* {h['symbol']}: ${h['position_value']} "
                f"(total return: {h.get('total_return_pct', 'NA')}%, "
                f"vol: {h.get('volatility', 'NA')}, "
                f"sharpe: {h.get('sharpe_ratio', 'NA')}, "
                f"beta: {h.get('beta', 'NA')})\n"
            )

    macro_text = ""
    for key, val in macro.items():
        if isinstance(val, dict) and "value" in val:
            unit = val.get("unit", "")
            macro_text += f"* {key}: {val['value']} {unit} (as of {val['date']})\n"

    headlines = "\n".join(f"* {a['title']}" for a in news[:5] if a.get("title"))

    tariff = summary.get("tariff_exposure") or {}
    tariff_line = (
        f"AAPL tariff drag: {tariff.get('portfolio_impact_pct')} percent "
        f"(rate {tariff.get('tariff_rate_pct')}, pass through {tariff.get('pass_through_pct')})"
    ) if tariff else "AAPL tariff drag: not applicable"

    return f"""Portfolio Summary:
Total Value: ${summary.get('total_value', 'NA')}
Total Return: {summary.get('total_return_pct', 'NA')} percent (dividend adjusted)
Annualized Volatility: {summary.get('portfolio_volatility', 'NA')}
Sharpe Ratio: {summary.get('portfolio_sharpe', 'NA')}
Sortino Ratio: {summary.get('portfolio_sortino', 'NA')}
Treynor Ratio: {summary.get('portfolio_treynor', 'NA')}
Information Ratio: {summary.get('portfolio_information_ratio', 'NA')}
Portfolio Beta vs SPY: {summary.get('portfolio_beta', 'NA')}
Jensen Alpha: {summary.get('portfolio_alpha', 'NA')}
HHI Concentration: {summary.get('hhi', 'NA')}
Effective N Holdings: {summary.get('effective_n', 'NA')}
Diversification Ratio: {summary.get('diversification_ratio', 'NA')}
{tariff_line}

Holdings:
{holdings_text}
Macro Indicators:
{macro_text}
Recent Headlines:
{headlines}

Based on the above data, provide a brief investment insight and risk assessment focused on the concentration, beta exposure, and tail risk."""


@app.post("/api/cache/clear")
async def clear_cache():
    """Clear the in-memory data cache."""
    cache.clear()
    logger.info("Cache cleared")
    return {"status": "ok", "message": "Cache cleared"}


# ── Serve Frontend ──────────��────────────────────────���──────

frontend_dir = Path(__file__).parent.parent / "frontend" / "static"
app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.get("/")
async def serve_frontend():
    return FileResponse(str(frontend_dir / "index.html"))


# ── Run ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("\n🚀 Starting FinGPT Portfolio Analyzer...")
    print("   Frontend: http://localhost:8000")
    print("   API docs: http://localhost:8000/docs\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)