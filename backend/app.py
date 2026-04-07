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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

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
)

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("fingpt")

# ── Init ────────────────────────────────────────────────────
app = FastAPI(title="FinGPT Portfolio Analyzer")

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


class PortfolioRequest(BaseModel):
    holdings: list[Holding]


class AnalyzeTextRequest(BaseModel):
    text: str
    task: str = "sentiment"  # sentiment | headline | insight


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
    """Get options chain for a stock symbol."""
    result = await yf_client.get_options(symbol.upper(), expiration)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.post("/api/portfolio/analyze")
async def analyze(req: PortfolioRequest):
    """
    Full portfolio analysis:
    1. Fetch daily prices for all holdings via yfinance
    2. Calculate quantitative metrics
    3. Fetch news + run FinGPT sentiment (if model available)
    4. Fetch macro indicators
    5. Generate AI insight (if model available)
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
    for sym, data in daily_results:
        if sym == "SPY" and "SPY" not in symbols:
            market_data = data
        else:
            daily_data[sym] = data
            if not data:
                warnings.append(f"Could not fetch price data for {sym}")

    # 2. Macro + news IN PARALLEL
    macro_task = fred.get_macro_snapshot()
    news_task = yf_client.get_news(symbols, limit=8)
    macro_result, news_result = await asyncio.gather(
        macro_task, news_task, return_exceptions=True
    )

    # Process macro
    risk_free = 0.05
    if isinstance(macro_result, Exception):
        logger.warning("Failed to fetch macro data: %s", macro_result)
        warnings.append("Could not fetch macro indicators; using default risk-free rate (5%)")
        macro = {}
    else:
        macro = macro_result
        ffr = macro.get("fed_funds_rate", {})
        if "value" in ffr:
            risk_free = float(ffr["value"]) / 100

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
    stress_task = asyncio.to_thread(stress_test, daily_data, holdings)

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

    return {
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
    }


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


# ── Helper ──────────────────────────────────────────────────

def _build_insight_prompt(analytics: dict, macro: dict, news: list) -> str:
    """Build a context string for FinGPT to generate portfolio insight."""
    summary = analytics.get("summary", {})
    holdings_text = ""
    for h in analytics.get("holdings", []):
        if "error" not in h:
            holdings_text += (
                f"- {h['symbol']}: ${h['position_value']} "
                f"(gain/loss: {h['gain_loss_pct']}%, vol: {h['volatility']}, "
                f"sharpe: {h['sharpe_ratio']})\n"
            )

    macro_text = ""
    for key, val in macro.items():
        if isinstance(val, dict) and "value" in val:
            macro_text += f"- {key}: {val['value']} (as of {val['date']})\n"

    headlines = "\n".join(f"- {a['title']}" for a in news[:5] if a.get("title"))

    return f"""Portfolio Summary:
Total Value: ${summary.get('total_value', 'N/A')}
Total Gain/Loss: {summary.get('total_gain_loss_pct', 'N/A')}%
Portfolio Volatility: {summary.get('portfolio_volatility', 'N/A')}
Sharpe Ratio: {summary.get('portfolio_sharpe', 'N/A')}
Diversification: {summary.get('diversification_score', 'N/A')}

Holdings:
{holdings_text}
Macro Indicators:
{macro_text}
Recent Headlines:
{headlines}

Based on the above data, provide a brief investment insight and risk assessment."""


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