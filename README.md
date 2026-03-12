# FinGPT Portfolio Analyzer

A full-stack portfolio management tool powered by FinGPT (Llama2-7B + LoRA) running
on Google Colab, with a local Python backend and web frontend.

## Architecture

```
┌─────────────────────────────────────────────┐
│  Google Colab (T4 GPU)                      │
│  ┌───────────────────────────────────────┐  │
│  │  FinGPT Model (4-bit quantized)       │  │
│  │  Llama2-7B + FinGPT LoRA adapter      │  │
│  │  Exposed via ngrok tunnel              │  │
│  └───────────────────────────────────────┘  │
└──────────────────┬──────────────────────────┘
                   │ HTTP (ngrok URL)
┌──────────────────▼──────────────────────────┐
│   (Local Machine)                           │
│  ┌───────────────────────────────────────┐  │
│  │  FastAPI Backend                      │  │
│  │  - Fetches data from APIs             │  │
│  │  - Sends prompts to Colab model       │  │
│  │  - Portfolio analytics engine         │  │
│  │  - Serves frontend                    │  │
│  └───────────────────────────────────────┘  │
│  ┌───────────────────────────────────────┐  │
│  │  Web Frontend (HTML/JS/Chart.js)      │  │
│  │  - Portfolio dashboard                │  │
│  │  - AI sentiment & analysis panel      │  │
│  │  - Market data visualizations         │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

## What FinGPT Actually Does Here

FinGPT (v3 series) is fine-tuned for **financial sentiment analysis** and
**headline classification**. On a T4 with 4-bit quantization (~3.5GB VRAM),
it runs Llama2-7B as the base with a LoRA adapter. In this project it:

1. **Analyzes sentiment** of financial news headlines for your portfolio stocks
2. **Classifies headlines** (price up/down signals)
3. **Generates natural language insights** about portfolio composition
4. **Provides risk commentary** based on macro indicators from FRED

It does NOT predict exact stock prices — that's snake oil. It gives you
structured sentiment signals you can use alongside quantitative metrics.

## Setup

### 1. Get Your API Keys

You need free API keys from:
- **Alpha Vantage**: https://www.alphavantage.co/support/#api-key
- **FRED**: https://fred.stlouisfed.org/docs/api/api_key.html
- **SEC EDGAR**: Just need a User-Agent string (name + email)
- **ngrok**: https://dashboard.ngrok.com/signup (free tier works)
- **Hugging Face**: https://huggingface.co/settings/tokens (for Llama2 access)

### 2. Configure Secrets (Local)

```bash
cp config/.env.example config/.env
# Edit config/.env with your actual keys
```

**IMPORTANT**: `config/.env` is in `.gitignore` — it will NOT be pushed to GitHub.

### 3. Start the Colab Model Server

1. Open `colab/fingpt_server.ipynb` in Google Colab
2. Set runtime to **T4 GPU**
3. Add your HuggingFace token and ngrok token in the notebook secrets
4. Run all cells — it will print an ngrok URL
5. Copy that URL into your `config/.env` as `COLAB_MODEL_URL`

### 4. Start the Local Backend + Frontend

```bash
cd fingpt-portfolio
pip install -r requirements.txt
python backend/app.py
```

Open http://localhost:8000 in your browser.

## Project Structure

```
fingpt-portfolio/
├── config/
│   ├── .env.example      # Template — copy to .env and fill in
│   └── .env              # YOUR secrets (git-ignored)
├── colab/
│   └── fingpt_server.ipynb   # Run this on Colab with T4
├── backend/
│   ├── app.py            # FastAPI server (entry point)
│   ├── data_fetcher.py   # Alpha Vantage, FRED, SEC EDGAR clients
│   ├── portfolio.py      # Portfolio analytics engine
│   └── model_client.py   # Talks to the Colab FinGPT server
├── frontend/
│   └── static/
│       └── index.html    # Single-page dashboard
├── requirements.txt
├── .gitignore
└── README.md
```

## Disconnecting Colab

When you're done, stop the Colab notebook to free your compute units.
The local backend will gracefully handle the model being unavailable —
quantitative analytics still work, just AI insights become disabled.
