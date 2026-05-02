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
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self.base_url}/health", headers=NGROK_HEADERS)
                self._available = r.status_code == 200
                return self._available
        except Exception:
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
        if self._available:
            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    r = await client.post(f"{self.base_url}/batch_analyze", json={"headlines": headlines, "task": "sentiment"}, headers=NGROK_HEADERS)
                    r.raise_for_status()
                    return r.json().get("results", [])
            except Exception as e:
                return [{"error": str(e), "headline": h} for h in headlines]

        if self._ollama_available:
            results = []
            for h in headlines[:5]:
                r = await self._ollama_call(f"Classify as positive/negative/neutral (one word): {h}")
                s = r.get("insight", "neutral").strip().lower()
                sent = "positive" if "positive" in s else ("negative" if "negative" in s else "neutral")
                results.append({"sentiment": sent, "headline": h})
            return results

        return [{"error": "No AI model backend is available", "headline": h} for h in headlines]

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
