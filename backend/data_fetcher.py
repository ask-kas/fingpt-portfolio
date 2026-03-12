"""
data_fetcher.py — Clients for Yahoo Finance (yfinance), FRED, and SEC EDGAR APIs.

yfinance: Free, no API key, no rate limits for reasonable usage.
FRED: Free API key required.
SEC EDGAR: No key, just a User-Agent string.
"""

import httpx
import os
import yfinance as yf
from datetime import datetime, timedelta


class YFinanceClient:
    """Fetches stock quotes, daily prices, and news from Yahoo Finance via yfinance."""

    async def get_quote(self, symbol: str) -> dict:
        """Get real-time quote for a symbol."""
        try:
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
        except Exception as e:
            return {"symbol": symbol, "error": str(e)}

    async def get_daily(self, symbol: str, days: int = 100) -> list[dict]:
        """Get daily OHLCV data."""
        try:
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

            # Return newest first
            rows.reverse()
            return rows
        except Exception as e:
            return []

    async def get_news(self, symbols: list[str], limit: int = 10) -> list[dict]:
        """Get news for given symbols."""
        articles = []
        seen_titles = set()

        for sym in symbols:
            try:
                ticker = yf.Ticker(sym)
                news = ticker.news
                if not news:
                    continue

                for item in news:
                    title = item.get("title", "")
                    if title in seen_titles:
                        continue
                    seen_titles.add(title)

                    published = item.get("providerPublishTime", "")
                    if isinstance(published, (int, float)):
                        published = datetime.fromtimestamp(published).strftime("%Y%m%d")

                    articles.append({
                        "title": title,
                        "summary": item.get("summary", "")[:200] if item.get("summary") else "",
                        "source": item.get("publisher", ""),
                        "published": str(published),
                        "overall_sentiment": "",
                        "ticker_sentiments": [{"ticker": sym, "score": "", "label": ""}],
                    })

                    if len(articles) >= limit:
                        break
            except Exception:
                continue

            if len(articles) >= limit:
                break

        return articles[:limit]


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