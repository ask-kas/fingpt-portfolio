"""
model_client.py — AI model client with priority: Colab → Ollama → offline.

Uses the Colab/ngrok notebook as the primary AI backend when available.
Falls back to local Ollama (Gemma) or offline mode.
"""

import httpx
import logging
import os
from typing import Optional

logger = logging.getLogger("fingpt.model")

NGROK_HEADERS = {"ngrok-skip-browser-warning": "true"}
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b")


def _normalize_sentiment(text: str) -> str:
    """Map any model output (positive/POS/bullish/up/etc.) to the canonical 3 buckets."""
    s = (text or "").strip().lower()
    if not s:
        return "neutral"
    if any(k in s for k in ("pos", "bull", "up", "good", "buy", "strong")):
        return "positive"
    if any(k in s for k in ("neg", "bear", "down", "bad", "sell", "weak")):
        return "negative"
    return "neutral"


class FinGPTClient:
    """AI client: Colab notebook → Ollama (local) → offline."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._available = None
        self._ollama_available = None

    async def health_check(self) -> bool:
        if await self._check_colab():
            return True
        if await self._check_ollama():
            return True
        return False

    async def _check_ollama(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                r = await client.get(f"{OLLAMA_URL}/api/tags")
                if r.status_code != 200:
                    self._ollama_available = False
                    return False
                models = r.json().get("models", [])
                self._ollama_available = any(m.get("name", "").startswith("gemma") for m in models)
                return self._ollama_available
        except Exception:
            self._ollama_available = False
            return False

    async def _check_colab(self) -> bool:
        """
        Probe the Colab notebook. Try /health first, fall back to GET / and
        OPTIONS /batch_analyze. Different FinGPT notebooks expose different
        routes; we just need to know the tunnel is alive and reachable.
        """
        if not self.base_url or "localhost" in self.base_url:
            self._available = False
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                for path in ("/health", "/", "/batch_analyze"):
                    try:
                        r = await client.get(f"{self.base_url}{path}", headers=NGROK_HEADERS)
                        # Any 2xx, 3xx, or 405 (Method Not Allowed on POST-only route)
                        # means the server is reachable and accepting requests.
                        if r.status_code < 400 or r.status_code == 405:
                            self._available = True
                            logger.info("Colab reachable at %s%s (%d)", self.base_url, path, r.status_code)
                            return True
                    except Exception:
                        continue
            self._available = False
            return False
        except Exception as e:
            logger.warning("Colab health check error: %s", e)
            self._available = False
            return False

    @property
    def is_available(self) -> Optional[bool]:
        return self._ollama_available or self._available

    @property
    def model_name(self) -> str:
        if self._available:
            return "Veris AI"
        if self._ollama_available:
            return "Veris AI"
        return "Veris AI (offline)"

    async def generate_insight(self, context: str) -> dict:
        if self._available:
            return await self._call("insight", context)
        if self._ollama_available:
            return await self._ollama_call(context)
        return {"error": "No AI model backend is available"}

    async def analyze_sentiment(self, headline: str) -> dict:
        prompt = f"Classify this financial headline as positive, negative, or neutral. Reply with ONLY one word.\n\nHeadline: {headline}"
        if self._available:
            return await self._call("sentiment", headline)
        if self._ollama_available:
            return await self._ollama_call(prompt)
        return {"error": "No AI model backend is available"}

    async def classify_headline(self, headline: str) -> dict:
        prompt = f"Will this headline cause the stock price to go up? Answer Yes or No briefly.\n\nHeadline: {headline}"
        if self._available:
            return await self._call("headline", headline)
        if self._ollama_available:
            return await self._ollama_call(prompt)
        return {"error": "No AI model backend is available"}

    async def batch_sentiment(self, headlines: list[str]) -> list[dict]:
        """
        Returns one dict per headline with at minimum a `sentiment` key set to
        'positive' / 'negative' / 'neutral'. Tolerates several Colab response
        shapes — different FinGPT notebook versions name the key differently.
        """
        if self._available:
            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    r = await client.post(
                        f"{self.base_url}/batch_analyze",
                        json={"headlines": headlines, "task": "sentiment"},
                        headers=NGROK_HEADERS,
                    )
                    r.raise_for_status()
                    payload = r.json()
                    raw = (
                        payload.get("results")
                        or payload.get("predictions")
                        or payload.get("data")
                        or (payload if isinstance(payload, list) else [])
                    )
                    logger.info(
                        "Colab sentiment: got %d results for %d headlines",
                        len(raw), len(headlines),
                    )
                    return [
                        self._coerce_sentiment_result(raw[i], headlines[i])
                        if i < len(raw) else {"sentiment": "neutral", "headline": headlines[i]}
                        for i in range(len(headlines))
                    ]
            except Exception as e:
                logger.warning("Colab sentiment failed: %s", e)
                return [{"error": str(e), "headline": h, "sentiment": "neutral"} for h in headlines]

        if self._ollama_available:
            results = []
            for h in headlines[:5]:
                r = await self._ollama_call(f"Classify as positive/negative/neutral (one word): {h}")
                s = r.get("insight", "neutral").strip().lower()
                sent = "positive" if "positive" in s else ("negative" if "negative" in s else "neutral")
                results.append({"sentiment": sent, "headline": h})
            return results

        return [{"error": "No AI model backend is available", "headline": h, "sentiment": "neutral"} for h in headlines]

    @staticmethod
    def _coerce_sentiment_result(item, headline: str) -> dict:
        """
        Normalize a single sentiment record into {"sentiment": str, "headline": str}.
        Accepts strings, dicts with various key names ('sentiment', 'label',
        'prediction', 'class', 'output', etc.), or HuggingFace-style
        [{"label": "POS", "score": 0.9}] entries.
        """
        # Plain string ("positive")
        if isinstance(item, str):
            return {"sentiment": _normalize_sentiment(item), "headline": headline}

        # List of {label, score} — pick highest score
        if isinstance(item, list) and item:
            best = max(item, key=lambda x: x.get("score", 0) if isinstance(x, dict) else 0)
            if isinstance(best, dict):
                label = (best.get("label") or best.get("sentiment") or "")
                return {"sentiment": _normalize_sentiment(label), "headline": headline}

        if isinstance(item, dict):
            for key in ("sentiment", "label", "prediction", "class", "output", "result", "answer"):
                v = item.get(key)
                if isinstance(v, str) and v.strip():
                    return {
                        "sentiment": _normalize_sentiment(v),
                        "headline": item.get("headline", headline),
                    }
            # Nothing matched — log and default to neutral
            logger.debug("Unrecognized sentiment shape: %s", item)

        return {"sentiment": "neutral", "headline": headline}

    async def _ollama_call(self, prompt: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                r = await client.post(f"{OLLAMA_URL}/api/generate", json={
                    "model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 512},
                })
                r.raise_for_status()
                return {"insight": r.json().get("response", ""), "model": OLLAMA_MODEL}
        except Exception as e:
            return {"error": str(e)}

    async def _call(self, task: str, text: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(f"{self.base_url}/analyze", json={"text": text, "task": task}, headers=NGROK_HEADERS)
                r.raise_for_status()
                return r.json()
        except Exception as e:
            return {"error": str(e)}


def create_model_client() -> FinGPTClient:
    from dotenv import load_dotenv
    load_dotenv("config/.env")
    url = os.getenv("COLAB_MODEL_URL", "http://localhost:5000")
    ollama = OLLAMA_MODEL
    print(f"  AI Priority: Colab ({url}) → Ollama ({ollama}) → offline")
    return FinGPTClient(url)
