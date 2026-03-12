"""
data_fetcher.py — Clients for Alpha Vantage, FRED, and SEC EDGAR APIs.
"""

import httpx
import os
import asyncio
from datetime import datetime, timedelta


class AlphaVantageClient:
    """Fetches stock quotes, daily prices, and news from Alpha Vantage."""

    BASE = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def get_quote(self, symbol: str) -> dict:
        """Get real-time quote for a symbol."""
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(self.BASE, params={
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": self.api_key,
            })
            data = r.json()
            gq = data.get("Global Quote", {})
            if not gq:
                return {"symbol": symbol, "error": "No data (rate limit or bad symbol)"}
            return {
                "symbol": gq.get("01. symbol", symbol),
                "price": float(gq.get("05. price", 0)),
                "change": float(gq.get("09. change", 0)),
                "change_pct": gq.get("10. change percent", "0%"),
                "volume": int(gq.get("06. volume", 0)),
                "latest_day": gq.get("07. latest trading day", ""),
            }

    async def get_daily(self, symbol: str, days: int = 100) -> list[dict]:
        """Get daily OHLCV data (compact = last 100 trading days)."""
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(self.BASE, params={
                "function": "TIME_SERIES_DAILY",
                "symbol": symbol,
                "outputsize": "compact",
                "apikey": self.api_key,
            })
            data = r.json()
            ts = data.get("Time Series (Daily)", {})
            rows = []
            for date_str, vals in sorted(ts.items(), reverse=True)[:days]:
                rows.append({
                    "date": date_str,
                    "open": float(vals["1. open"]),
                    "high": float(vals["2. high"]),
                    "low": float(vals["3. low"]),
                    "close": float(vals["4. close"]),
                    "volume": int(vals["5. volume"]),
                })
            return rows

    async def get_news(self, tickers: str, limit: int = 10) -> list[dict]:
        """
        Get news sentiment from Alpha Vantage News API.
        tickers: comma-separated like "AAPL,MSFT"
        """
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(self.BASE, params={
                "function": "NEWS_SENTIMENT",
                "tickers": tickers,
                "limit": limit,
                "apikey": self.api_key,
            })
            data = r.json()
            feed = data.get("feed", [])
            articles = []
            for item in feed[:limit]:
                articles.append({
                    "title": item.get("title", ""),
                    "summary": item.get("summary", "")[:200],
                    "source": item.get("source", ""),
                    "published": item.get("time_published", ""),
                    "overall_sentiment": item.get("overall_sentiment_label", ""),
                    "ticker_sentiments": [
                        {
                            "ticker": ts.get("ticker", ""),
                            "score": ts.get("ticker_sentiment_score", ""),
                            "label": ts.get("ticker_sentiment_label", ""),
                        }
                        for ts in item.get("ticker_sentiment", [])
                    ],
                })
            return articles


class FREDClient:
    """Fetches macro indicators from the Federal Reserve Economic Data API."""

    BASE = "https://api.stlouisfed.org/fred/series/observations"

    # Key macro series
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
        """Get latest value of all key macro indicators."""
        snapshot = {}
        for name, series_id in self.SERIES.items():
            try:
                obs = await self.get_indicator(series_id, limit=1)
                if obs:
                    snapshot[name] = {
                        "value": obs[0]["value"],
                        "date": obs[0]["date"],
                        "series_id": series_id,
                    }
            except Exception as e:
                snapshot[name] = {"error": str(e)}
        return snapshot


class SECEdgarClient:
    """Fetches company filings from SEC EDGAR."""

    BASE = "https://efts.sec.gov/LATEST/search-index?q="
    FILINGS_BASE = "https://data.sec.gov/submissions/CIK{cik}.json"

    def __init__(self, user_agent: str):
        self.user_agent = user_agent
        self.headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
        }

    async def get_company_filings(self, ticker: str, filing_type: str = "10-K", count: int = 5) -> list[dict]:
        """Get recent filings for a company by ticker."""
        async with httpx.AsyncClient(timeout=30) as client:
            # First, resolve ticker to CIK
            r = await client.get(
                f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt=2024-01-01&forms={filing_type}",
                headers=self.headers,
            )
            # Fallback: use the company tickers endpoint
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
        "alpha_vantage": AlphaVantageClient(os.getenv("ALPHA_VANTAGE_API_KEY", "")),
        "fred": FREDClient(os.getenv("FRED_API_KEY", "")),
        "sec": SECEdgarClient(os.getenv("SEC_USER_AGENT", "Anonymous anon@example.com")),
    }
