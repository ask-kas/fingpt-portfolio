"""
data_fetcher.py — Clients for Yahoo Finance (yfinance), FRED, and SEC EDGAR APIs.

yfinance: Free, no API key, no rate limits for reasonable usage.
FRED: Free API key required.
SEC EDGAR: No key, just a User-Agent string.
"""

import asyncio
import hashlib
import httpx
import logging
import math
import os
import yfinance as yf
from datetime import datetime, timedelta, timezone
from functools import partial
from urllib.parse import urlsplit, urlunsplit

from backend.cache import cache
from backend.options_math import black_scholes_call, black_scholes_put, greeks
from backend.advanced_analytics import cpi_yoy_pct

logger = logging.getLogger("fingpt.data")


def _url_fingerprint(url: str) -> str:
    """Normalize a URL and return a short hash fingerprint.

    Strips query parameters and fragments so tracking parameters like
    utm_source do not leak into the dedup key. Returns an empty string
    for empty or invalid input.
    """
    if not url:
        return ""
    try:
        parts = urlsplit(url.strip().lower())
        cleaned = urlunsplit((parts.scheme or "https", parts.netloc, parts.path.rstrip("/"), "", ""))
        return hashlib.sha1(cleaned.encode("utf-8")).hexdigest()[:16]
    except Exception:
        return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


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
        """Fetch daily OHLCV bars from yfinance.

        Returns a list of rows, newest first. Each row carries the trading
        date. Freshness metadata (fetched_at, age_days, is_stale) is added
        to the first row only so callers can surface staleness in the UI
        without bloating every bar. Spec item P1.2.
        """
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

        # Attach freshness metadata to the newest row.
        if rows:
            fetched_at = datetime.now(timezone.utc)
            try:
                latest_trading_date = datetime.strptime(rows[0]["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                age_days = (fetched_at - latest_trading_date).days
            except Exception:
                age_days = 0
            rows[0]["fetched_at"] = fetched_at.strftime("%Y-%m-%d %H:%M UTC")
            rows[0]["age_days"] = age_days
            # Crypto trades 7 days a week; stocks can be 3+ days old over weekends.
            is_crypto = "-USD" in symbol.upper()
            threshold = 1 if is_crypto else 4
            rows[0]["is_stale"] = bool(age_days > threshold)

        return rows

    # ── Intraday / minute bars ───────────────────────────────
    #
    # yfinance intraday interval limits (Yahoo enforces these):
    #   1m   → max 7 days of history, 7d per request
    #   2m   → max 60 days, 60d per request
    #   5m   → max 60 days, 60d per request
    #   15m  → max 60 days, 60d per request
    #   30m  → max 60 days, 60d per request
    #   60m  → max 730 days, 60d per request
    #   90m  → max 60 days
    #   1h   → max 730 days, 60d per request
    #
    # We pick a sensible default period per interval so callers can just
    # say "give me 1-minute bars" without hitting Yahoo's constraints.
    _INTRADAY_VALID_INTERVALS = {
        "1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"
    }
    _INTRADAY_DEFAULT_PERIOD = {
        "1m": "1d",
        "2m": "5d",
        "5m": "5d",
        "15m": "5d",
        "30m": "1mo",
        "60m": "3mo",
        "90m": "60d",
        "1h": "3mo",
    }
    _INTRADAY_MAX_PERIOD = {
        "1m": "7d",
        "2m": "60d",
        "5m": "60d",
        "15m": "60d",
        "30m": "60d",
        "60m": "2y",
        "90m": "60d",
        "1h": "2y",
    }

    def _get_intraday_sync(
        self,
        symbol: str,
        interval: str = "1m",
        period: str | None = None,
        prepost: bool = False,
    ) -> list[dict]:
        """Fetch intraday OHLCV bars from yfinance.

        Returns a list of rows, newest first. Each row carries a UTC
        ISO-8601 timestamp plus OHLCV. Freshness metadata (fetched_at,
        age_seconds, is_stale) is attached to the first row.

        The staleness threshold scales with interval: a 1-minute bar is
        stale after ~5 min for stocks; crypto trades 24/7 so we tolerate
        slightly longer gaps. Outside of market hours stocks will always
        be "stale" relative to wall-clock, which is the correct signal.
        """
        interval = (interval or "1m").lower()
        if interval not in self._INTRADAY_VALID_INTERVALS:
            raise ValueError(
                f"Invalid interval '{interval}'. Valid: "
                f"{sorted(self._INTRADAY_VALID_INTERVALS)}"
            )

        if period is None:
            period = self._INTRADAY_DEFAULT_PERIOD[interval]

        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval, prepost=prepost)

        if hist.empty:
            return []

        rows = []
        for ts, row in hist.iterrows():
            # yfinance returns tz-aware timestamps; normalise to UTC.
            try:
                if ts.tzinfo is None:
                    ts_utc = ts.tz_localize("UTC")
                else:
                    ts_utc = ts.tz_convert("UTC")
            except Exception:
                ts_utc = ts
            rows.append({
                "timestamp": ts_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
                "volume": int(row["Volume"]) if not math.isnan(row["Volume"]) else 0,
            })

        rows.reverse()  # newest first

        # Freshness metadata on the newest bar.
        if rows:
            fetched_at = datetime.now(timezone.utc)
            try:
                latest = datetime.strptime(rows[0]["timestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                age_seconds = int((fetched_at - latest).total_seconds())
            except Exception:
                age_seconds = 0
            rows[0]["fetched_at"] = fetched_at.strftime("%Y-%m-%dT%H:%M:%SZ")
            rows[0]["age_seconds"] = age_seconds
            # Stale threshold: 3× the interval length for stocks,
            # 2× for crypto (trades continuously). Baseline interval in sec:
            interval_seconds = {
                "1m": 60, "2m": 120, "5m": 300, "15m": 900, "30m": 1800,
                "60m": 3600, "90m": 5400, "1h": 3600,
            }.get(interval, 60)
            is_crypto = "-USD" in symbol.upper()
            threshold = interval_seconds * (2 if is_crypto else 3)
            rows[0]["is_stale"] = bool(age_seconds > threshold)
            rows[0]["interval"] = interval

        return rows

    def _get_news_sync(self, symbols: list[str], limit: int = 10) -> list[dict]:
        """Fetch news for a set of tickers and deduplicate by URL fingerprint.

        Step 1: For each symbol, pull the yfinance news list.
        Step 2: Normalise the URL, strip tracking params, hash the path.
        Step 3: Skip any article whose URL hash has already been seen.
        Step 4: Also skip exact title duplicates as a second line of defence
                (some syndicated wire stories reuse URLs inconsistently).

        Spec item P2.10.
        """
        articles = []
        seen_url_hashes: set[str] = set()
        seen_titles: set[str] = set()

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
                    if not title:
                        continue

                    # Extract URL first so we can dedup on it.
                    canonical = content.get("canonicalUrl", {})
                    url = canonical.get("url", "") if isinstance(canonical, dict) else str(canonical)
                    if not url:
                        url = item.get("link", "")

                    url_hash = _url_fingerprint(url)
                    norm_title = title.strip().lower()

                    if url_hash and url_hash in seen_url_hashes:
                        continue
                    if norm_title in seen_titles:
                        continue

                    if url_hash:
                        seen_url_hashes.add(url_hash)
                    seen_titles.add(norm_title)

                    # Extract publish date
                    published = content.get("pubDate", "") or item.get("providerPublishTime", "")
                    if isinstance(published, (int, float)):
                        published = datetime.fromtimestamp(published).strftime("%Y-%m-%d")
                    elif isinstance(published, str) and "T" in published:
                        published = published[:10]  # "2026 04 06T14:30:00Z" becomes "2026 04 06"

                    # Extract source
                    provider = content.get("provider", {})
                    source = provider.get("displayName", "") if isinstance(provider, dict) else item.get("publisher", "")

                    # Extract summary
                    summary = content.get("summary", "") or item.get("summary", "")

                    articles.append({
                        "title": title,
                        "url": url,
                        "url_hash": url_hash,
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

    async def get_intraday(
        self,
        symbol: str,
        interval: str = "1m",
        period: str | None = None,
        prepost: bool = False,
    ) -> list[dict]:
        """Get intraday OHLCV bars at the requested interval.

        TTL scales with the bar interval — no point caching a 1-minute
        bar for an hour. 1m → 30s, 5m → 2min, anything larger → 5min.
        """
        interval = (interval or "1m").lower()
        period_key = period or "default"
        cache_key = f"intraday:{symbol}:{interval}:{period_key}:{int(bool(prepost))}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            result = await _run_sync(
                self._get_intraday_sync, symbol, interval, period, prepost
            )
            if result:
                ttl = 30 if interval == "1m" else 120 if interval in ("2m", "5m") else 300
                cache.set(cache_key, result, ttl_seconds=ttl)
            return result
        except ValueError:
            raise
        except Exception as e:
            logger.error("Failed to fetch intraday data for %s (%s): %s", symbol, interval, e)
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

    def _get_options_sync(self, symbol: str, expiration: str = None, risk_free_rate: float = 0.0435) -> dict:
        """Fetch the options chain for a symbol and enrich it with analytics.

        Each contract is augmented with Black Scholes Greeks computed from
        the market implied volatility. The response also carries the put
        call ratio (open interest weighted) and an implied volatility skew
        summary (25 delta proxy). Spec items P2.9 and P3.15.
        """
        import numpy as np
        ticker = yf.Ticker(symbol)
        expirations = ticker.options
        if not expirations:
            return {"symbol": symbol, "error": "No options data available"}

        exp = expiration if expiration and expiration in expirations else expirations[0]
        chain = ticker.option_chain(exp)

        # Need current underlying price to compute Greeks.
        spot = None
        try:
            hist = ticker.history(period="2d")
            if not hist.empty:
                spot = float(hist["Close"].iloc[-1])
        except Exception:
            spot = None

        # Time to expiry in years.
        try:
            exp_date = datetime.strptime(exp, "%Y-%m-%d")
            days_to_exp = max((exp_date - datetime.utcnow()).days, 1)
        except Exception:
            days_to_exp = 30
        T = days_to_exp / 365.0

        def format_chain(df, option_type: str):
            rows = []
            for _, row in df.iterrows():
                strike = float(row["strike"])
                iv = float(row["impliedVolatility"]) if not np.isnan(row["impliedVolatility"]) else 0.0
                contract = {
                    "strike": strike,
                    "lastPrice": float(row["lastPrice"]),
                    "bid": float(row["bid"]),
                    "ask": float(row["ask"]),
                    "volume": int(row["volume"]) if not np.isnan(row["volume"]) else 0,
                    "openInterest": int(row["openInterest"]) if not np.isnan(row["openInterest"]) else 0,
                    "impliedVolatility": round(iv, 4),
                }
                if spot is not None and iv > 1e-4 and T > 0 and strike > 0:
                    try:
                        g = greeks(spot, strike, risk_free_rate, T, iv, option_type)
                        contract["greeks"] = g.to_dict()
                        contract["theoretical_price"] = round(
                            black_scholes_call(spot, strike, risk_free_rate, T, iv)
                            if option_type == "call"
                            else black_scholes_put(spot, strike, risk_free_rate, T, iv),
                            2,
                        )
                        contract["moneyness"] = round((spot - strike) / spot, 4) if option_type == "call" else round((strike - spot) / spot, 4)
                    except Exception:
                        contract["greeks"] = None
                        contract["theoretical_price"] = None
                        contract["moneyness"] = None
                else:
                    contract["greeks"] = None
                    contract["theoretical_price"] = None
                    contract["moneyness"] = None
                rows.append(contract)
            return rows

        calls = format_chain(chain.calls, "call")
        puts = format_chain(chain.puts, "put")

        # Put call ratio, weighted by open interest (the standard convention).
        total_call_oi = sum(c["openInterest"] for c in calls)
        total_put_oi = sum(p["openInterest"] for p in puts)
        total_call_vol = sum(c["volume"] for c in calls)
        total_put_vol = sum(p["volume"] for p in puts)
        pc_ratio_oi = round(total_put_oi / total_call_oi, 3) if total_call_oi else None
        pc_ratio_vol = round(total_put_vol / total_call_vol, 3) if total_call_vol else None

        # IV skew: compare the IV of an out of the money put to an equally
        # out of the money call. We use the 10 percent OTM proxy which is a
        # decent stand in for 25 delta when the surface is not too extreme.
        skew = None
        if spot is not None and calls and puts:
            target_otm = 0.10
            otm_put_strike = spot * (1 - target_otm)
            otm_call_strike = spot * (1 + target_otm)
            def _nearest(chain_list, target_strike):
                valid = [c for c in chain_list if c["impliedVolatility"] > 1e-4]
                if not valid:
                    return None
                return min(valid, key=lambda c: abs(c["strike"] - target_strike))
            put_anchor = _nearest(puts, otm_put_strike)
            call_anchor = _nearest(calls, otm_call_strike)
            if put_anchor and call_anchor:
                skew_value = put_anchor["impliedVolatility"] - call_anchor["impliedVolatility"]
                skew = {
                    "put_iv": round(put_anchor["impliedVolatility"], 4),
                    "put_strike": put_anchor["strike"],
                    "call_iv": round(call_anchor["impliedVolatility"], 4),
                    "call_strike": call_anchor["strike"],
                    "skew_points": round(skew_value * 100, 2),  # percentage points
                    "method": "10 percent OTM proxy",
                    "interpretation": (
                        "Put skew: downside is pricier than upside. Markets are paying up for protection."
                        if skew_value > 0.01
                        else "Flat skew: upside and downside are roughly equally priced."
                        if abs(skew_value) <= 0.01
                        else "Call skew: upside calls are pricier. Speculative euphoria, rare in equities."
                    ),
                }

        return {
            "symbol": symbol,
            "expiration": exp,
            "expirations": list(expirations),
            "underlying_price": round(spot, 2) if spot is not None else None,
            "days_to_expiry": days_to_exp,
            "risk_free_rate": risk_free_rate,
            "calls": calls,
            "puts": puts,
            "put_call_ratio_oi": pc_ratio_oi,
            "put_call_ratio_volume": pc_ratio_vol,
            "iv_skew": skew,
            "greeks_method": "black_scholes_with_market_iv",
        }

    def _get_earnings_calendar_sync(self, symbols: list[str]) -> list[dict]:
        """Fetch upcoming earnings dates and historical earnings-day returns."""
        events = []
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                cal = ticker.calendar
                hist = ticker.history(period="1y")

                next_earnings = None
                if cal is not None:
                    if isinstance(cal, dict):
                        ed = cal.get("Earnings Date")
                        if ed:
                            next_earnings = str(ed[0])[:10] if isinstance(ed, list) else str(ed)[:10]
                    elif hasattr(cal, "iloc"):
                        try:
                            ed = cal.iloc[0] if len(cal) > 0 else None
                            if ed is not None:
                                next_earnings = str(ed.name)[:10] if hasattr(ed, "name") else None
                        except Exception:
                            pass

                # Historical earnings dates from earnings_dates attribute
                earnings_returns = []
                try:
                    ed_df = ticker.earnings_dates
                    if ed_df is not None and not ed_df.empty and not hist.empty:
                        for dt in ed_df.index:
                            dt_date = dt.date() if hasattr(dt, "date") else dt
                            mask = hist.index.date == dt_date
                            if mask.any():
                                idx = hist.index.get_loc(hist.index[mask][0])
                                if idx > 0:
                                    prev_close = float(hist["Close"].iloc[idx - 1])
                                    curr_close = float(hist["Close"].iloc[idx])
                                    ret = (curr_close / prev_close - 1) * 100
                                    earnings_returns.append(round(ret, 2))
                except Exception:
                    pass

                avg_ret = round(sum(earnings_returns) / len(earnings_returns), 2) if earnings_returns else None
                std_ret = None
                if len(earnings_returns) >= 2:
                    import statistics
                    std_ret = round(statistics.stdev(earnings_returns), 2)

                events.append({
                    "symbol": symbol,
                    "next_earnings": next_earnings,
                    "historical_earnings_returns": earnings_returns[:8],
                    "avg_earnings_day_return": avg_ret,
                    "std_earnings_day_return": std_ret,
                    "n_events": len(earnings_returns),
                })
            except Exception as e:
                logger.warning("Failed to get earnings for %s: %s", symbol, e)
                events.append({
                    "symbol": symbol,
                    "next_earnings": None,
                    "historical_earnings_returns": [],
                    "avg_earnings_day_return": None,
                    "std_earnings_day_return": None,
                    "n_events": 0,
                })
        return events

    async def get_earnings_calendar(self, symbols: list[str]) -> list[dict]:
        """Get earnings calendar for given stock symbols."""
        cache_key = f"earnings:{','.join(sorted(symbols))}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            result = await _run_sync(self._get_earnings_calendar_sync, symbols)
            cache.set(cache_key, result, ttl_seconds=3600)
            return result
        except Exception as e:
            logger.error("Failed to fetch earnings calendar: %s", e)
            return []

    # ── Legendary investors / institutional holders ────────────

    # Curated map: lowercased substring -> investor display name + bio
    LEGENDARY_INVESTORS = {
        "berkshire hathaway": {"name": "Warren Buffett", "fund": "Berkshire Hathaway", "style": "Value investing, long term compounder"},
        "bridgewater": {"name": "Ray Dalio", "fund": "Bridgewater Associates", "style": "Macro, risk parity, all weather"},
        "renaissance": {"name": "Jim Simons", "fund": "Renaissance Technologies", "style": "Quantitative, systematic trading"},
        "citadel": {"name": "Ken Griffin", "fund": "Citadel Advisors", "style": "Multi strategy, market making"},
        "soros fund": {"name": "George Soros", "fund": "Soros Fund Management", "style": "Macro, reflexivity theory"},
        "two sigma": {"name": "John Overdeck & David Siegel", "fund": "Two Sigma Investments", "style": "Quantitative, AI driven"},
        "point72": {"name": "Steve Cohen", "fund": "Point72 Asset Management", "style": "Multi strategy, discretionary"},
        "pershing square": {"name": "Bill Ackman", "fund": "Pershing Square Capital", "style": "Activist, concentrated bets"},
        "third point": {"name": "Dan Loeb", "fund": "Third Point LLC", "style": "Event driven, activist"},
        "appaloosa": {"name": "David Tepper", "fund": "Appaloosa Management", "style": "Distressed debt, macro"},
        "elliott": {"name": "Paul Singer", "fund": "Elliott Management", "style": "Activist, distressed, event driven"},
        "baupost": {"name": "Seth Klarman", "fund": "Baupost Group", "style": "Deep value, margin of safety"},
        "greenlight": {"name": "David Einhorn", "fund": "Greenlight Capital", "style": "Value, short selling"},
        "lone pine": {"name": "Stephen Mandel", "fund": "Lone Pine Capital", "style": "Long short equity, growth"},
        "viking global": {"name": "Andreas Halvorsen", "fund": "Viking Global Investors", "style": "Long short equity, fundamental"},
        "millennium": {"name": "Israel Englander", "fund": "Millennium Management", "style": "Multi strategy, pod based"},
        "d.e. shaw": {"name": "David Shaw", "fund": "D.E. Shaw & Co", "style": "Quantitative, systematic"},
        "de shaw": {"name": "David Shaw", "fund": "D.E. Shaw & Co", "style": "Quantitative, systematic"},
        "tiger global": {"name": "Chase Coleman", "fund": "Tiger Global Management", "style": "Growth equity, tech focused"},
        "coatue": {"name": "Philippe Laffont", "fund": "Coatue Management", "style": "TMT focused, long short"},
        "druckenmiller": {"name": "Stanley Druckenmiller", "fund": "Duquesne Family Office", "style": "Macro, growth at reasonable price"},
        "duquesne": {"name": "Stanley Druckenmiller", "fund": "Duquesne Family Office", "style": "Macro, growth at reasonable price"},
        "ark invest": {"name": "Cathie Wood", "fund": "ARK Invest", "style": "Disruptive innovation, high conviction"},
        "icahn": {"name": "Carl Icahn", "fund": "Icahn Enterprises", "style": "Activist, corporate raider"},
        "jana partners": {"name": "Barry Rosenstein", "fund": "JANA Partners", "style": "Activist, event driven"},
        "valueact": {"name": "Mason Morfit", "fund": "ValueAct Capital", "style": "Constructive activism, concentrated"},
    }

    def _get_institutional_holders_sync(self, symbols: list[str]) -> dict:
        """Fetch institutional holders for each symbol and flag legendary investors."""
        result = {}
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                inst = ticker.institutional_holders
                mf = ticker.mutualfund_holders

                holders = []
                legendary_matches = []

                if inst is not None and not inst.empty:
                    for _, row in inst.iterrows():
                        holder_name = str(row.get("Holder", ""))
                        shares_held = int(row.get("Shares", 0)) if row.get("Shares") else 0
                        pct = float(row.get("pctHeld", 0) or row.get("% Out", 0) or 0)
                        value = float(row.get("Value", 0)) if row.get("Value") else 0
                        date_reported = str(row.get("Date Reported", ""))[:10] if row.get("Date Reported") is not None else ""

                        entry = {
                            "holder": holder_name,
                            "shares": shares_held,
                            "pct_held": round(pct * 100, 2),
                            "value": round(value, 0),
                            "date_reported": date_reported,
                        }
                        holders.append(entry)

                        # Check if this is a legendary investor
                        name_lower = holder_name.lower()
                        for key, info in self.LEGENDARY_INVESTORS.items():
                            if key in name_lower:
                                legendary_matches.append({
                                    **entry,
                                    "investor_name": info["name"],
                                    "fund_name": info["fund"],
                                    "style": info["style"],
                                })
                                break

                # Also check mutual fund holders for notable names
                if mf is not None and not mf.empty:
                    for _, row in mf.iterrows():
                        holder_name = str(row.get("Holder", ""))
                        name_lower = holder_name.lower()
                        for key, info in self.LEGENDARY_INVESTORS.items():
                            if key in name_lower:
                                shares_held = int(row.get("Shares", 0)) if row.get("Shares") else 0
                                pct = float(row.get("pctHeld", 0) or row.get("% Out", 0) or 0)
                                value = float(row.get("Value", 0)) if row.get("Value") else 0
                                date_reported = str(row.get("Date Reported", ""))[:10] if row.get("Date Reported") is not None else ""
                                legendary_matches.append({
                                    "holder": holder_name,
                                    "shares": shares_held,
                                    "pct_held": round(pct * 100, 2),
                                    "value": round(value, 0),
                                    "date_reported": date_reported,
                                    "investor_name": info["name"],
                                    "fund_name": info["fund"],
                                    "style": info["style"],
                                })
                                break

                result[symbol] = {
                    "top_holders": holders[:10],
                    "legendary": legendary_matches,
                    "total_institutional_holders": len(holders),
                }
            except Exception as e:
                logger.warning("Failed to get holders for %s: %s", symbol, e)
                result[symbol] = {
                    "top_holders": [],
                    "legendary": [],
                    "total_institutional_holders": 0,
                }
        return result

    async def get_institutional_holders(self, symbols: list[str]) -> dict:
        """Get institutional holders and legendary investor matches for symbols."""
        cache_key = f"holders:{','.join(sorted(symbols))}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            result = await _run_sync(self._get_institutional_holders_sync, symbols)
            cache.set(cache_key, result, ttl_seconds=3600)
            return result
        except Exception as e:
            logger.error("Failed to fetch institutional holders: %s", e)
            return {}

    async def get_options(self, symbol: str, expiration: str = None, risk_free_rate: float = 0.0435) -> dict:
        """Get options chain for a symbol enriched with Black Scholes Greeks."""
        cache_key = f"options:{symbol}:{expiration or 'nearest'}:{risk_free_rate:.4f}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            result = await _run_sync(self._get_options_sync, symbol, expiration, risk_free_rate)
            if "error" not in result:
                cache.set(cache_key, result, ttl_seconds=900)  # 15 min
            return result
        except Exception as e:
            logger.error("Failed to fetch options for %s: %s", symbol, e)
            return {"symbol": symbol, "error": str(e)}


class FREDClient:
    """Fetches macro indicators from the Federal Reserve Economic Data API.

    CPI is a special case. The raw CPIAUCSL series is an index (currently
    around 327). To be useful it has to be converted to a year over year
    percentage change. We fetch 13 months and compute YoY ourselves rather
    than leaning on a FRED derived series. Spec item P1.1.
    """

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
        """Get latest value of all key macro indicators (fetched in parallel).

        CPI is returned as a year over year percentage rather than the raw
        index value. All other series return the most recent observation.
        """
        cached = cache.get("macro_snapshot")
        if cached is not None:
            return cached

        async def _fetch_standard(name, series_id):
            try:
                obs = await self.get_indicator(series_id, limit=1)
                if obs:
                    return name, {
                        "value": obs[0]["value"],
                        "date": obs[0]["date"],
                        "series_id": series_id,
                        "unit": "percent" if series_id in ("FEDFUNDS", "UNRATE", "DGS10") else "index",
                    }
                return name, {"error": "No observations"}
            except Exception as e:
                logger.error("Failed to fetch FRED indicator %s (%s): %s", name, series_id, e)
                return name, {"error": str(e)}

        async def _fetch_cpi_yoy(name, series_id):
            try:
                # Fetch 16 months to tolerate missing values (FRED occasionally
                # has dot entries in the CPIAUCSL series).
                obs = await self.get_indicator(series_id, limit=16)
                if len(obs) < 2:
                    return name, {"error": "Not enough CPI history for year over year"}
                # Most recent valid observation.
                current_val = float(obs[0]["value"])
                current_date = obs[0]["date"]
                # Find the observation closest to 12 months prior by date.
                from datetime import datetime
                cur_dt = datetime.strptime(current_date, "%Y-%m-%d")
                target_dt = cur_dt.replace(year=cur_dt.year - 1)
                best = None
                best_dist = 9999
                for o in obs[1:]:
                    dt = datetime.strptime(o["date"], "%Y-%m-%d")
                    dist = abs((dt - target_dt).days)
                    if dist < best_dist:
                        best_dist = dist
                        best = o
                if best is None or best_dist > 45:
                    return name, {"error": "Could not find CPI observation from 12 months ago"}
                year_ago_val = float(best["value"])
                yoy_pct = cpi_yoy_pct(current_val, year_ago_val)
                return name, {
                    "value": f"{yoy_pct:.2f}",
                    "date": current_date,
                    "series_id": series_id,
                    "unit": "percent",
                    "cpi_current": round(current_val, 2),
                    "cpi_year_ago": round(year_ago_val, 2),
                    "description": "CPI all urban consumers, year over year change",
                }
            except Exception as e:
                logger.error("Failed to compute CPI YoY: %s", e)
                return name, {"error": str(e)}

        tasks = []
        for name, series_id in self.SERIES.items():
            if name == "cpi_yoy":
                tasks.append(_fetch_cpi_yoy(name, series_id))
            else:
                tasks.append(_fetch_standard(name, series_id))

        results = await asyncio.gather(*tasks)
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
