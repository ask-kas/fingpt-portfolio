"""
model_client.py — Sends prompts to the FinGPT model server running on Colab.

The Colab notebook exposes a simple HTTP endpoint:
    POST /analyze  {text: "...", task: "sentiment|headline|insight"}
    → {result: "positive/negative/neutral", raw: "..."}
"""

import httpx
import os
from typing import Optional

# ngrok free tier shows a browser warning page — this header bypasses it
NGROK_HEADERS = {
    "ngrok-skip-browser-warning": "true",
}


class FinGPTClient:
    """Client for the FinGPT inference server running on Google Colab."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._available = None

    async def health_check(self) -> bool:
        """Check if the Colab model server is reachable."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{self.base_url}/health",
                    headers=NGROK_HEADERS,
                )
                self._available = r.status_code == 200
                return self._available
        except Exception:
            self._available = False
            return False

    @property
    def is_available(self) -> Optional[bool]:
        return self._available

    async def analyze_sentiment(self, headline: str) -> dict:
        """
        Send a headline to FinGPT for sentiment classification.
        Returns: {sentiment: "positive"|"negative"|"neutral", confidence: str}
        """
        return await self._call("sentiment", headline)

    async def classify_headline(self, headline: str) -> dict:
        """
        Ask FinGPT if a headline signals price going up or down.
        Returns: {direction: "Yes"|"No", raw: str}
        """
        return await self._call("headline", headline)

    async def generate_insight(self, context: str) -> dict:
        """
        Send portfolio context and macro data to FinGPT for a natural language insight.
        Returns: {insight: str}
        """
        return await self._call("insight", context)

    async def batch_sentiment(self, headlines: list[str]) -> list[dict]:
        """Analyze sentiment for multiple headlines."""
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
            return [{"error": str(e), "headline": h} for h in headlines]

    async def _call(self, task: str, text: str) -> dict:
        """Generic call to the Colab model server."""
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
            return {"error": "Colab model server unreachable. Is the notebook running?"}
        except httpx.TimeoutException:
            return {"error": "Model inference timed out (T4 can be slow on long prompts)"}
        except Exception as e:
            return {"error": str(e)}


def create_model_client() -> FinGPTClient:
    from dotenv import load_dotenv
    load_dotenv("config/.env")
    url = os.getenv("COLAB_MODEL_URL", "http://localhost:5000")
    print(f"  Model URL: {url}")
    return FinGPTClient(url)