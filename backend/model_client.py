"""
model_client.py — AI model client with priority: Claude API → Ollama → offline.

Uses NYU AI Gateway (Portkey) for Claude access when available.
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
    """AI client: Claude API (fast) → Ollama (local) → Colab (legacy)."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._available = None
        self._ollama_available = None
        self._claude_available = None

        self._claude_base = os.getenv("ANTHROPIC_BASE_URL", "")
        self._claude_key = os.getenv("ANTHROPIC_API_KEY", "")
        self._claude_headers = self._parse_custom_headers()
        self._claude_model = os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL", "anthropic.claude-sonnet-4-6")

    def _parse_custom_headers(self) -> dict:
        raw = os.getenv("ANTHROPIC_CUSTOM_HEADERS", "")
        headers = {}
        for line in raw.strip().split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()
        return headers

    async def health_check(self) -> bool:
        if await self._check_claude():
            return True
        if await self._check_ollama():
            return True
        return await self._check_colab()

    async def _check_claude(self) -> bool:
        if not self._claude_base or not self._claude_key:
            self._claude_available = False
            return False
        if not self._claude_headers:
            self._claude_available = False
            return False
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(self._claude_base)
                self._claude_available = r.status_code in (200, 401, 403, 404, 405)
                return self._claude_available
        except Exception:
            self._claude_available = False
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
        return self._claude_available or self._ollama_available or self._available

    @property
    def model_name(self) -> str:
        if self._claude_available:
            return "Veris AI"
        if self._ollama_available:
            return "Veris AI"
        if self._available:
            return "Veris AI"
        return "Veris AI (offline)"

    async def generate_insight(self, context: str) -> dict:
        if self._claude_available:
            return await self._claude_call(context)
        if self._ollama_available:
            return await self._ollama_call(context)
        return await self._call("insight", context)

    async def analyze_sentiment(self, headline: str) -> dict:
        prompt = f"Classify this financial headline as positive, negative, or neutral. Reply with ONLY one word.\n\nHeadline: {headline}"
        if self._claude_available:
            return await self._claude_call(prompt)
        if self._ollama_available:
            return await self._ollama_call(prompt)
        return await self._call("sentiment", headline)

    async def classify_headline(self, headline: str) -> dict:
        prompt = f"Will this headline cause the stock price to go up? Answer Yes or No briefly.\n\nHeadline: {headline}"
        if self._claude_available:
            return await self._claude_call(prompt)
        if self._ollama_available:
            return await self._ollama_call(prompt)
        return await self._call("headline", headline)

    async def batch_sentiment(self, headlines: list[str]) -> list[dict]:
        if self._claude_available:
            prompt = "Classify each headline as positive, negative, or neutral. Return one word per line.\n\n" + "\n".join(f"- {h}" for h in headlines[:10])
            resp = await self._claude_call(prompt)
            text = resp.get("insight", "")
            lines = [l.strip().lower() for l in text.split("\n") if l.strip()]
            results = []
            for i, h in enumerate(headlines[:10]):
                sent = "neutral"
                if i < len(lines):
                    if "positive" in lines[i]: sent = "positive"
                    elif "negative" in lines[i]: sent = "negative"
                results.append({"sentiment": sent, "headline": h})
            return results

        if self._ollama_available:
            results = []
            for h in headlines[:5]:
                r = await self._ollama_call(f"Classify as positive/negative/neutral (one word): {h}")
                s = r.get("insight", "neutral").strip().lower()
                sent = "positive" if "positive" in s else ("negative" if "negative" in s else "neutral")
                results.append({"sentiment": sent, "headline": h})
            return results

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(f"{self.base_url}/batch_analyze", json={"headlines": headlines, "task": "sentiment"}, headers=NGROK_HEADERS)
                r.raise_for_status()
                return r.json().get("results", [])
        except Exception as e:
            return [{"error": str(e), "headline": h} for h in headlines]

    async def _claude_call(self, prompt: str) -> dict:
        try:
            headers = {
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
                **self._claude_headers,
            }
            body = {
                "model": self._claude_model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            }
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(f"{self._claude_base}/v1/messages", headers=headers, json=body)
                r.raise_for_status()
                data = r.json()
                text = data.get("content", [{}])[0].get("text", "")
                return {"insight": text, "model": self._claude_model}
        except Exception as e:
            logger.error("Claude API call failed: %s", e)
            return {"error": str(e)}

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
    claude_base = os.getenv("ANTHROPIC_BASE_URL", "")
    ollama = OLLAMA_MODEL
    print(f"  AI Priority: Claude ({claude_base[:30]}...) → Ollama ({ollama}) → Colab ({url})")
    return FinGPTClient(url)
