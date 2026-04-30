"""
model_client.py — AI model client supporting local Ollama (Gemma 4) and remote Colab.

Priority: Ollama local → Colab remote → offline fallback.
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
    """AI client: tries Ollama (Gemma 4) first, falls back to Colab."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._available = None
        self._ollama_available = None

    async def health_check(self) -> bool:
        if await self._check_ollama():
            return True
        return await self._check_colab()

    async def _check_ollama(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{OLLAMA_URL}/api/tags")
                self._ollama_available = r.status_code == 200
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
        if self._ollama_available:
            return True
        return self._available

    @property
    def model_name(self) -> str:
        if self._ollama_available:
            return f"Gemma 4 ({OLLAMA_MODEL}) — local"
        if self._available:
            return "FinGPT (Colab) — remote"
        return "offline"

    async def analyze_sentiment(self, headline: str) -> dict:
        if self._ollama_available:
            return await self._ollama_call(
                f"Classify this financial headline as positive, negative, or neutral. Reply with ONLY one word.\n\nHeadline: {headline}"
            )
        return await self._call("sentiment", headline)

    async def classify_headline(self, headline: str) -> dict:
        if self._ollama_available:
            return await self._ollama_call(
                f"Will this headline cause the stock price to go up? Answer Yes or No with a brief reason.\n\nHeadline: {headline}"
            )
        return await self._call("headline", headline)

    async def generate_insight(self, context: str) -> dict:
        if self._ollama_available:
            return await self._ollama_call(context)
        return await self._call("insight", context)

    async def batch_sentiment(self, headlines: list[str]) -> list[dict]:
        if self._ollama_available:
            results = []
            for h in headlines[:5]:
                r = await self._ollama_call(
                    f"Classify as positive/negative/neutral (one word only): {h}"
                )
                sentiment = r.get("insight", "neutral").strip().lower()
                if "positive" in sentiment:
                    results.append({"sentiment": "positive", "headline": h})
                elif "negative" in sentiment:
                    results.append({"sentiment": "negative", "headline": h})
                else:
                    results.append({"sentiment": "neutral", "headline": h})
            return results

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(
                    f"{self.base_url}/batch_analyze",
                    json={"headlines": headlines, "task": "sentiment"},
                    headers=NGROK_HEADERS,
                )
                r.raise_for_status()
                return r.json().get("results", [])
        except Exception as e:
            logger.error("Batch sentiment failed: %s", e)
            return [{"error": str(e), "headline": h} for h in headlines]

    async def _ollama_call(self, prompt: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                r = await client.post(f"{OLLAMA_URL}/api/generate", json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 512},
                })
                r.raise_for_status()
                data = r.json()
                return {"insight": data.get("response", ""), "model": OLLAMA_MODEL}
        except httpx.TimeoutException:
            logger.warning("Ollama timed out (model may be loading)")
            return {"error": "Gemma 4 inference timed out — model may still be loading"}
        except Exception as e:
            logger.error("Ollama call failed: %s", e)
            return {"error": str(e)}

    async def _call(self, task: str, text: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    f"{self.base_url}/analyze",
                    json={"text": text, "task": task},
                    headers=NGROK_HEADERS,
                )
                r.raise_for_status()
                return r.json()
        except httpx.ConnectError:
            return {"error": "Model server unreachable"}
        except httpx.TimeoutException:
            return {"error": "Model inference timed out"}
        except Exception as e:
            return {"error": str(e)}


def create_model_client() -> FinGPTClient:
    from dotenv import load_dotenv
    load_dotenv("config/.env")
    url = os.getenv("COLAB_MODEL_URL", "http://localhost:5000")
    print(f"  Model URL: {url}")
    print(f"  Ollama model: {OLLAMA_MODEL}")
    return FinGPTClient(url)
