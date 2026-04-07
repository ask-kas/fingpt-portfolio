"""
data_fetcher.py — Clients for Yahoo Finance (yfinance), FRED, and SEC EDGAR APIs.

yfinance: Free, no API key, no rate limits for reasonable usage.
FRED: Free API key required.
SEC EDGAR: No key, just a User-Agent string.
"""

import asyncio
import httpx
import logging
import os
import yfinance as yf
from datetime import datetime, timedelta
from functools import partial

from backend.cache import cache

logger = logging.getLogger("fingpt.data")


async def _run_sync(func, *args, **kwargs):
    """Run a blocking function in the default thread pool executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))


class YFinanceClient:
    """Fetches stock quotes, daily prices, and news from Yahoo Finance via yfinance."""

    # Crypto shorthand -> yfinance ticker mapping
    CRYPTO_MAP = {
        "BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD",
        "ADA": "ADA-USD", "DOT": "DOT-USD", "MATIC": "MATIC-USD",
        "AVAX": "AVAX-USD", "LINK": "LINK-USD", "XRP": "XRP-USD",
        "DOGE": "DOGE-USD", "BNB": "BNB-USD", "LTC": "LTC-USD",
    }

    def normalize_symbol(self, symbol: str) -> str:
        """Convert shorthand crypto symbols to yfinance format."""
        upper = symbol.upper().strip()
        return self.CRYPTO_MAP.get(upper, upper)

    # ── Sync internals (run in thread pool) ──────────────────

    def _get_quote_sync(self, symbol: str) -> dict:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        hist = ticker.history(period="2d")

        if hist.empty:
            return {"symbol": symbol, "error": "No data found"}

        current = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
        change = current - prev
        change_pct = (change / prev * 100) if prev else 0

        return {
            "symbol": symbol,
            "price": round(current, 2),
            "change": round(change, 2),
            "change_pct": f"{change_pct:.2f}%",
            "volume": int(hist["Volume"].iloc[-1]),
            "latest_day": str(hist.index[-1].date()),
            "name": info.get("shortName", symbol),
        }

    def _get_daily_sync(self, symbol: str, days: int = 100) -> list[dict]:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=f"{days}d")

        if hist.empty:
            return []

        rows = []
        for date, row in hist.iterrows():
            rows.append({
                "date": str(date.date()),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })

        rows.reverse()  # newest first
        return rows

    def _get_news_sync(self, symbols: list[str], limit: int = 10) -> list[dict]:
        articles = []
        seen_titles = set()

        for sym in symbols:
            try:
                ticker = yf.Ticker(sym)
                news = ticker.news
                if not news:
                    continue

                for item in news:
                    # yfinance 1.2.0 nests data under "content"
                    content = item.get("content", item)

                    title = content.get("title", "") or item.get("title", "")
                    if not title or title in seen_titles:
                        continue
                    seen_titles.add(title)

                    # Extract publish date
                    published = content.get("pubDate", "") or item.get("providerPublishTime", "")
                    if isinstance(published, (int, float)):
                        published = datetime.fromtimestamp(published).strftime("%Y-%m-%d")
                    elif isinstance(published, str) and "T" in published:
                        published = published[:10]  # "2026-04-06T14:30:00Z" -> "2026-04-06"

                    # Extract URL
                    canonical = content.get("canonicalUrl", {})
                    url = canonical.get("url", "") if isinstance(canonical, dict) else str(canonical)
                    if not url:
                        url = item.get("link", "")

                    # Extract source
                    provider = content.get("provider", {})
                    source = provider.get("displayName", "") if isinstance(provider, dict) else item.get("publisher", "")

                    # Extract summary
                    summary = content.get("summary", "") or item.get("summary", "")

                    articles.append({
                        "title": title,
                        "url": url,
                        "summary": summary[:200] if summary else "",
                        "source": source,
                        "published": str(published),
                        "overall_sentiment": "",
                        "ticker_sentiments": [{"ticker": sym, "score": "", "label": ""}],
                    })

                    if len(articles) >= limit:
                        break
            except Exception as e:
                logger.warning("Failed to fetch news for %s: %s", sym, e)
                continue

            if len(articles) >= limit:
                break

        return articles[:limit]

    # ── Async public API (with caching) ──────────────────────

    async def get_quote(self, symbol: str) -> dict:
        """Get real-time quote for a symbol."""
        cache_key = f"quote:{symbol}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            result = await _run_sync(self._get_quote_sync, symbol)
            if "error" not in result:
                cache.set(cache_key, result, ttl_seconds=300)  # 5 min
            return result
        except Exception as e:
            logger.error("Failed to fetch quote for %s: %s", symbol, e)
            return {"symbol": symbol, "error": str(e)}

    async def get_daily(self, symbol: str, days: int = 100) -> list[dict]:
        """Get daily OHLCV data."""
        cache_key = f"daily:{symbol}:{days}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            result = await _run_sync(self._get_daily_sync, symbol, days)
            if result:
                cache.set(cache_key, result, ttl_seconds=3600)  # 1 hour
            return result
        except Exception as e:
            logger.error("Failed to fetch daily data for %s: %s", symbol, e)
            return []

    async def get_news(self, symbols: list[str], limit: int = 10) -> list[dict]:
        """Get news for given symbols."""
        cache_key = f"news:{','.join(sorted(symbols))}:{limit}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            result = await _run_sync(self._get_news_sync, symbols, limit)
            if result:
                cache.set(cache_key, result, ttl_seconds=900)  # 15 min
            return result
        except Exception as e:
            logger.error("Failed to fetch news: %s", e)
            return []

    # ── Options chain ────────────────────────────────────────

    def _get_options_sync(self, symbol: str, expiration: str = None) -> dict:
        import numpy as np
        ticker = yf.Ticker(symbol)
        expirations = ticker.options
        if not expirations:
            return {"symbol": symbol, "error": "No options data available"}

        exp = expiration if expiration and expiration in expirations else expirations[0]
        chain = ticker.option_chain(exp)

        def format_chain(df):
            rows = []
            for _, row in df.iterrows():
                rows.append({
                    "strike": float(row["strike"]),
                    "lastPrice": float(row["lastPrice"]),
                    "bid": float(row["bid"]),
                    "ask": float(row["ask"]),
                    "volume": int(row["volume"]) if not np.isnan(row["volume"]) else 0,
                    "openInterest": int(row["openInterest"]) if not np.isnan(row["openInterest"]) else 0,
                    "impliedVolatility": round(float(row["impliedVolatility"]), 4),
                })
            return rows

        return {
            "symbol": symbol,
            "expiration": exp,
            "expirations": list(expirations),
            "calls": format_chain(chain.calls),
            "puts": format_chain(chain.puts),
        }

    async def get_options(self, symbol: str, expiration: str = None) -> dict:
        """Get options chain for a symbol."""
        cache_key = f"options:{symbol}:{expiration or 'nearest'}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            result = await _run_sync(self._get_options_sync, symbol, expiration)
            if "error" not in result:
                cache.set(cache_key, result, ttl_seconds=900)  # 15 min
            return result
        except Exception as e:
            logger.error("Failed to fetch options for %s: %s", symbol, e)
            return {"symbol": symbol, "error": str(e)}


class FREDClient:
    """Fetches macro indicators from the Federal Reserve Economic Data API."""

    BASE = "https://api.stlouisfed.org/fred/series/observations"

    SERIES = {
        "fed_funds_rate": "FEDFUNDS",
        "cpi_yoy": "CPIAUCSL",
        "unemployment": "UNRATE",
        "treasury_10y": "DGS10",
        "sp500": "SP500",
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def get_indicator(self, series_id: str, limit: int = 12) -> list[dict]:
        """Get recent observations for a FRED series."""
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(self.BASE, params={
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": limit,
            })
            data = r.json()
            obs = data.get("observations", [])
            return [
                {"date": o["date"], "value": o["value"]}
                for o in obs
                if o["value"] != "."
            ]

    async def get_macro_snapshot(self) -> dict:
        """Get latest value of all key macro indicators (fetched in parallel)."""
        cached = cache.get("macro_snapshot")
        if cached is not None:
            return cached

        async def _fetch_one(name, series_id):
            try:
                obs = await self.get_indicator(series_id, limit=1)
                if obs:
                    return name, {
                        "value": obs[0]["value"],
                        "date": obs[0]["date"],
                        "series_id": series_id,
                    }
                return name, {"error": "No observations"}
            except Exception as e:
                logger.error("Failed to fetch FRED indicator %s (%s): %s", name, series_id, e)
                return name, {"error": str(e)}

        results = await asyncio.gather(*[_fetch_one(n, s) for n, s in self.SERIES.items()])
        snapshot = dict(results)
        cache.set("macro_snapshot", snapshot, ttl_seconds=14400)  # 4 hours
        return snapshot


class SECEdgarClient:
    """Fetches company filings from SEC EDGAR."""

    def __init__(self, user_agent: str):
        self.user_agent = user_agent
        self.headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
        }

    async def get_company_filings(self, ticker: str, filing_type: str = "10-K", count: int = 5) -> list[dict]:
        """Get recent filings for a company by ticker."""
        async with httpx.AsyncClient(timeout=30) as client:
            # Resolve ticker to CIK
            r2 = await client.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers=self.headers,
            )
            tickers_data = r2.json()
            cik = None
            for entry in tickers_data.values():
                if entry.get("ticker", "").upper() == ticker.upper():
                    cik = str(entry["cik_str"]).zfill(10)
                    break

            if not cik:
                return [{"error": f"Ticker {ticker} not found in SEC"}]

            # Fetch filings
            r3 = await client.get(
                f"https://data.sec.gov/submissions/CIK{cik}.json",
                headers=self.headers,
            )
            data = r3.json()
            recent = data.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            accessions = recent.get("accessionNumber", [])
            descriptions = recent.get("primaryDocDescription", [])

            results = []
            for i, form in enumerate(forms):
                if form == filing_type and len(results) < count:
                    results.append({
                        "form": form,
                        "date": dates[i] if i < len(dates) else "",
                        "accession": accessions[i] if i < len(accessions) else "",
                        "description": descriptions[i] if i < len(descriptions) else "",
                        "url": f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accessions[i].replace('-', '')}/",
                    })
            return results


def create_clients() -> dict:
    """Factory: create all API clients from environment variables."""
    from dotenv import load_dotenv
    load_dotenv("config/.env")

    return {
        "yfinance": YFinanceClient(),
        "fred": FREDClient(os.getenv("FRED_API_KEY", "")),
        "sec": SECEdgarClient(os.getenv("SEC_USER_AGENT", "Anonymous anon@example.com")),
    }
