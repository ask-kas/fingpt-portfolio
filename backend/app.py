"""
app.py — FastAPI backend for FinGPT Portfolio Analyzer.

Run with:  python backend/app.py
Serves API at :8000 and frontend at http://localhost:8000
"""

import os
import sys
import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Add project root to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.data_fetcher import create_clients
from backend.model_client import create_model_client
from backend.portfolio import analyze_portfolio

# ── Init ────────────────────────────────────────────────────
app = FastAPI(title="FinGPT Portfolio Analyzer")
clients = create_clients()
model = create_model_client()

av = clients["alpha_vantage"]
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
    return await av.get_quote(symbol.upper())


@app.get("/api/daily/{symbol}")
async def get_daily(symbol: str, days: int = 100):
    """Get daily OHLCV data."""
    return await av.get_daily(symbol.upper(), days)


@app.get("/api/news")
async def get_news(tickers: str = "AAPL", limit: int = 10):
    """Get financial news for given tickers (comma-separated)."""
    return await av.get_news(tickers.upper(), limit)


@app.get("/api/macro")
async def get_macro():
    """Get macroeconomic indicators snapshot from FRED."""
    return await fred.get_macro_snapshot()


@app.get("/api/filings/{ticker}")
async def get_filings(ticker: str, filing_type: str = "10-K", count: int = 5):
    """Get SEC filings for a company."""
    return await sec.get_company_filings(ticker.upper(), filing_type, count)


@app.post("/api/portfolio/analyze")
async def analyze(req: PortfolioRequest):
    """
    Full portfolio analysis:
    1. Fetch daily prices for all holdings
    2. Calculate quantitative metrics
    3. Fetch news + run FinGPT sentiment (if model available)
    4. Fetch macro indicators
    5. Generate AI insight (if model available)
    """
    holdings = [h.model_dump() for h in req.holdings]
    symbols = [h["symbol"].upper() for h in holdings]
    for h in holdings:
        h["symbol"] = h["symbol"].upper()

    # 1. Fetch daily data for all symbols (with rate-limit spacing)
    daily_data = {}
    for sym in symbols:
        try:
            daily_data[sym] = await av.get_daily(sym)
        except Exception as e:
            daily_data[sym] = []
        # Alpha Vantage free tier: 5 calls/min
        await asyncio.sleep(0.5)

    # 2. Quantitative analysis
    # Try to get current risk-free rate from FRED
    risk_free = 0.05
    try:
        macro = await fred.get_macro_snapshot()
        ffr = macro.get("fed_funds_rate", {})
        if "value" in ffr:
            risk_free = float(ffr["value"]) / 100
    except Exception:
        pass

    analytics = analyze_portfolio(holdings, daily_data, risk_free)

    # 3. News + sentiment
    tickers_str = ",".join(symbols)
    news = []
    sentiments = []
    try:
        news = await av.get_news(tickers_str, limit=8)
    except Exception:
        pass

    # Run FinGPT sentiment on headlines if model is available
    model_available = await model.health_check()
    if model_available and news:
        headlines = [a["title"] for a in news if a.get("title")]
        sentiments = await model.batch_sentiment(headlines)
        # Attach FinGPT sentiment back to news
        for i, article in enumerate(news):
            if i < len(sentiments):
                article["fingpt_sentiment"] = sentiments[i]

    # 4. Macro snapshot (already fetched above for risk-free rate, reuse)
    if "macro" not in locals() or macro is None:
        try:
            macro = await fred.get_macro_snapshot()
        except Exception:
            macro = {}

    # 5. AI insight
    ai_insight = None
    if model_available:
        context = _build_insight_prompt(analytics, macro, news)
        insight_resp = await model.generate_insight(context)
        ai_insight = insight_resp.get("insight") or insight_resp.get("error")

    return {
        "analytics": analytics,
        "news": news,
        "macro": macro,
        "ai_insight": ai_insight,
        "model_available": model_available,
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


# ── Serve Frontend ──────────────────────────────────────────

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
