# Veris — Portfolio Intelligence

Your portfolio. The truth.

Veris is the first portfolio intelligence platform built on the principle that investors deserve to know the math behind every number they are shown. Not marketing. Not approximations. The actual calculation, the actual source, the actual tax consequence.

Built with a FastAPI backend, vanilla JavaScript frontend, SQLAlchemy persistence, and an optional language model running on Google Colab. All quantitative analytics work offline with zero API cost.

---

## Contributors

| Contributor | Contributions |
|---|---|
| **Askar Kassimov** | Core platform: FastAPI backend, yfinance/FRED/SEC data pipeline, base portfolio analytics, Colab integration with ngrok tunneling, and the initial frontend dashboard. |
| **Shihan Mahfuz** | Institutional-grade analytics rebuild, risk management system, database persistence layer, Veris brand identity, and all features listed below. |
| **Anatolii Chuvashlov** | contributed to financial API integration and core analytics, validated the correctness of the quantitative models,is leading frontend restructuring, and overall feature prioritization, Gemini chat feature integration. |
| **Yanaiya Jain** | contributed to brainstorming the project idea, frontend restructuring, presentation and pitch. |
---

## What Veris Shows You

### Mathematics and Analytics Engine

- **Log returns** replacing simple returns across the entire pipeline, with Bessel-corrected standard deviations (ddof=1)
- **Full covariance portfolio volatility**: `sigma_p = sqrt(w^T * Sigma * w)` using the complete correlation structure
- **252-day OLS beta** against SPY as the single canonical beta source
- **Sortino ratio** using downside deviation only
- **Treynor ratio** (excess return per unit of systematic risk)
- **Calmar ratio** (annualized return divided by maximum drawdown)
- **Information ratio** (active return vs SPY divided by tracking error)
- **Jensen's alpha** via the CAPM formula
- **HHI concentration index**, **effective N**, and **diversification ratio**
- **Wilder-smoothed RSI-14** with labeled bands
- **Total return computation** including dividends, with dividend-adjusted cost basis
- **Tax liability engine** at 23.8% LTCG with tax loss harvesting identification
- **AAPL tariff exposure model** with constant P/E price translation
- **CAPM factor attribution** decomposing portfolio return into beta contribution and alpha

### Monte Carlo VaR/CVaR (10,000 simulations)

- **Student-t marginal distribution** fitted per asset via MLE
- **Cholesky decomposition** of the full covariance matrix for correlated multi-asset draws
- **Rescaling** by `sqrt((nu-2)/nu)` so the simulated covariance matches the sample covariance exactly
- **30-day horizon** with daily compounding of log returns
- VaR at 95% and 99%, CVaR (expected shortfall), percentile fan chart

### Efficient Frontier Optimization

- **Ledoit-Wolf shrinkage** on the covariance matrix for stability
- **Black-Litterman style expected returns**: blends implied equilibrium returns with historical means
- **Box constraints** (5% to 60% per name) to produce investable portfolios

### Intraday Minute Tape

- **Minute-resolution OHLCV** pulled live from Yahoo via yfinance
- Six intervals: **1m, 2m, 5m, 15m, 30m, 1h** (plus 60m, 90m)
- **Interval-aware default windows** so Yahoo's caps are never hit (1m→1d, 5m→5d, 30m→1mo, 1h→3mo)
- **UTC-normalized timestamps** on every bar, independent of server timezone
- **Freshness flag** on the newest bar: `age_seconds`, `is_stale` keyed to 3× the bar interval for stocks, 2× for crypto
- **Interval-tuned caching**: 30s TTL for 1m, 120s for 2–5m, 300s for coarser bars
- Per-holding tabs plus free-text symbol input (works for stocks, crypto like `BTC-USD`, indices)

### Prediction Markets

- **Dual-exchange integration**: Polymarket and Kalshi markets in a unified feed
- **Historical price charts** via Polymarket CLOB API and Kalshi candlestick endpoints
- **Cross-platform arbitrage scanner** using Bellman-Ford algorithm for multi-hop opportunity detection across 500+ Polymarket and 350+ Kalshi markets
- **Relevance scoring** with finance keyword matching and meme/novelty filtering to surface actionable markets
- **My Bets portfolio tracker** with P&L, average entry, and outcome tracking
- **Side-by-side view** for comparing Polymarket vs Kalshi pricing on matched events
- **Calibration curve** from 500 resolved Polymarket markets with Brier score accuracy metric
- **Cross-market dependency correlation graph** linking related prediction markets
- **AI prediction market analysis** synthesizing trends from both exchanges
- **Smart money detection** identifying volume spikes with configurable sensitivity

### Trading Tools

- **EV Calculator** for binary prediction markets with implied probability
- **Kelly Criterion** optimal bet sizing with fractional Kelly slider
- **Arbitrage scanner** with live spread detection across both exchanges
- **Smart money volume spike detection** with configurable thresholds

### Learning Mode

- **9-stage gamified learning system** with 56 lessons and 34 quizzes covering investing fundamentals through advanced analytics
- **Duolingo-style vertical skill tree** with custom SVG icons for each stage
- **XP system** with 5 ranks (Novice, Apprentice, Analyst, Strategist, Portfolio Master) and 9 achievement badges
- **Tool locking/unlocking** gating 25 dashboard panels behind learning progress
- **55 YouTube videos** and **38 Investopedia articles** as learning resources
- **Quiz passing mark** at 70% with retry and per-question feedback
- **Badge cabinet** with earned and locked achievement display
- **Streak tracking** with daily login detection
- **Confetti unlock ceremonies** on stage completion and badge earn
- **Admin bypass** (shihanmahfuz) and **tester mode** (abdullah)

### Options Chain with Black-Scholes Greeks

- Full Black-Scholes pricing with **delta, gamma, theta, vega, rho**
- **Put/call ratio** with positioning interpretation
- **IV skew** with market interpretation
- Risk-free rate sourced live from the 10-year Treasury via FRED

### Stress Testing

- Beta-adjusted losses under 5 historical crises
- **Reverse stress test**: solves for the market drop required to produce a given portfolio loss
- Per-holding beta breakdown cards

### Regime-Aware Risk Engine

- **21-day rolling realized volatility** classifying the market into four regimes
- **Regime-conditional VaR** using only returns observed during the current regime
- Regime transition probabilities and historical regime distribution

### What-If Trade Simulator

- Simulate adding or removing any position before executing
- Before/after/delta for Sharpe, volatility, beta, HHI, effective N, and VaR

### Legendary Investors (SEC 13F)

- Cross-references portfolio stocks against 25+ curated legendary investors
- Dynamic ticker search with cached results

### Event-Risk Calendar

- Upcoming earnings dates with historical earnings-day return distributions

### Data Quality Dashboard

- Per-ticker quality assessment with composite quality score (0-100)

### Portfolio Rebalancing

- **Wealthfront-inspired rebalancing suggestions** comparing current vs target allocations
- **AI news digest** for portfolio holdings with per-ticker summary and sentiment

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Cmd+K` / `Ctrl+K` | Open command palette |

The **command palette** (Linear-inspired) provides fuzzy search across all dashboard panels, actions, and navigation targets.

### Database Persistence Layer

- **SQLAlchemy ORM** with 8 models: User, Portfolio, Holding, AnalysisSnapshot, TradeJournal, Watchlist, Alert, AuditLog
- **Multi-backend support**: SQLite (default), MySQL, PostgreSQL
- **User authentication** with session persistence (login, register, guest mode)
- **Auto-snapshot**: every analysis saves a full analytics snapshot for historical tracking
- **Admin dashboard** with credential-protected access to all database tables
- **PBKDF2-HMAC-SHA256** password hashing with bcrypt support
- **30 REST endpoints** under `/api/db/` for full CRUD

---

## Architecture

```
Google Colab (T4 GPU)          FRED API         Polymarket API     Kalshi API
  Llama-2-7B + FinGPT LoRA   (macro data)      (CLOB + Gamma)     (REST v2)
  4-bit NF4 quantized             |                   |                |
  Exposed via ngrok tunnel        |                   |                |
         |                        |                   |                |
         | HTTP                   |                   |                |
         v                        v                   v                v
  +------------------------------------------------------------------------+
  |  FastAPI Backend (backend/)                                            |
  |                                                                        |
  |  app.py ................. API server, 57 endpoints                     |
  |  portfolio.py ........... Core analytics engine                        |
  |  advanced_analytics.py .. Monte Carlo, Frontier, Stress, What-If,      |
  |                           Regime, Data Quality, Arbitrage              |
  |  data_fetcher.py ........ yfinance, FRED, SEC, Polymarket, Kalshi      |
  |  options_math.py ........ Black-Scholes + Greeks                       |
  |  cache.py ............... Thread-safe in-memory TTL cache              |
  |  model_client.py ........ Colab LLM bridge                            |
  |  database/ .............. SQLAlchemy ORM persistence                   |
  |    engine.py ............ Connection pooling, multi-DB                 |
  |    models.py ............ 8 ORM models                                 |
  |    crud.py .............. 35+ CRUD functions + audit log               |
  |    schemas.py ........... Pydantic request/response DTOs               |
  +------------------------------------------------------------------------+
         |                            |
         | HTML + JSON API :8000      | SQLAlchemy
         v                            v
  +---------------------------+  +---------------------------+
  |  Veris Dashboard          |  |  Database                 |
  |  (frontend/static/)       |  |  SQLite (default)         |
  |                           |  |  MySQL / PostgreSQL       |
  |  33 panels + Learning     |  |  8 tables, audit log,     |
  |  Auth overlay             |  |  auto-snapshots,          |
  |  Cmd+K command palette    |  |  connection pooling       |
  |  Admin dashboard          |  +---------------------------+
  |  Plotly.js, Chart.js      |
  +---------------------------+
```

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/ask-kas/fingpt-portfolio.git
cd fingpt-portfolio

# Create and activate a virtualenv (recommended)
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Configure

```bash
cp config/.env.example config/.env
```

Open `config/.env`. The minimum to get the dashboard running is a **FRED API key** (free at [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html)). Everything else is optional and unlocks specific features — see the AI Setup section below.

### 3. Run

```bash
python3 backend/app.py
```

Open **http://localhost:8000**. Enter your holdings and click "Analyze Portfolio."

---

## AI Setup (Optional)

Veris ships with **two independent AI integrations**. You can enable either, both, or neither.

### Veris Chat — Gemini-powered assistant (recommended)

Powers the chat panel in the dashboard. Uses Google's `gemini-2.5-flash` with function-calling over the local MCP volatility tools, so the assistant cites computed numbers instead of guessing. Free, fast, and no GPU required.

1. Get a free key at **[aistudio.google.com/apikey](https://aistudio.google.com/apikey)**.
   - Sign in with a Google account
   - Click "Create API key" and copy the value (starts with `AIza...`)
   - Free tier is generous and requires no billing setup
2. Paste the key into `config/.env`:
   ```
   GEMINI_API_KEY=AIzaSy...your_key_here
   ```
3. Restart the backend. The chat panel now responds; without the key it returns HTTP 503.

### V-Lab MCP bridge — institutional volatility (optional, OAuth)

[NYU Stern's V-Lab](https://vlab.stern.nyu.edu) (Robert Engle's research group) exposes its GARCH-family volatility analytics over MCP at `https://vlab.stern.nyu.edu/mcp`. When enabled, the chat assistant can call `vlab_*` tools alongside the local ones and cite "V-Lab" in its replies.

The endpoint requires OAuth, so the backend wraps it via the `mcp-remote` npm package which handles the browser dance.

**Prerequisites:** [Node.js](https://nodejs.org) installed so `npx` is on PATH, and a free V-Lab account.

**First-run flow:**
1. In `config/.env`, comment out or set `VLAB_DISABLED=0`.
2. Restart the backend and send any chat message.
3. **Watch the backend's terminal** (the one running `python3 backend/app.py`) — `mcp-remote` prints an `Open this URL to authorize` line. If a browser tab doesn't open automatically, copy that URL into your browser manually.
4. Complete the V-Lab login. The token caches in `~/.mcp-auth/` and lasts ~24 hours.

**To skip V-Lab entirely** (recommended if you don't have Node.js or don't want to OAuth), keep the default `VLAB_DISABLED=1` in `config/.env`. The chat still works using only the local volatility tools.

If V-Lab discovery hangs (e.g. OAuth popup never appeared), the backend falls back to local tools after `VLAB_DISCOVERY_TIMEOUT` seconds (default 12) — chat will never block forever.

### Heavy LLM — Llama-2 + FinGPT LoRA on Colab (optional, GPU)

Powers `/api/model/analyze`, the citation-backed research blocks (panel 3, "AI Insight"), the news digest, and the prediction-market analysis. Runs on a free Colab T4.

1. Open `colab/fingpt_server.ipynb` in [Google Colab](https://colab.research.google.com/)
2. Runtime → Change runtime type → **T4 GPU** → Save
3. Add `HF_TOKEN` and `NGROK_AUTH_TOKEN` to Colab Secrets
   - `HF_TOKEN`: [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) — and accept the Llama-2 license at [huggingface.co/meta-llama/Llama-2-7b-chat-hf](https://huggingface.co/meta-llama/Llama-2-7b-chat-hf)
   - `NGROK_AUTH_TOKEN`: free signup at [dashboard.ngrok.com](https://dashboard.ngrok.com/signup)
4. Runtime → Run all. Wait 2–4 minutes for model load.
5. Copy the printed ngrok URL into `config/.env` as `COLAB_MODEL_URL`.
6. Restart the backend.

---

## Dashboard Sections

| # | Section | Description |
|---|---------|-------------|
| 1 | **Portfolio Input** | Enter holdings: symbol, shares, avg cost, dividends per share |
| 2 | **Portfolio Summary** | 14 glassmorphism metric cards with disclosed methodology |
| 3 | **AI Insight** | Citation-backed research from the language model (optional) |
| 4 | **Holdings Detail** | 16-column table with per-stock metrics. CSV/JSON export |
| 5 | **Price Charts** | Interactive candlestick charts with SMA overlays |
| 5b | **Intraday Tape** | Minute-resolution OHLCV candles (1m-1h) with live/stale freshness flag |
| 6 | **Monte Carlo VaR** | 10,000 simulated paths, VaR/CVaR, fan chart |
| 7 | **Efficient Frontier** | Markowitz optimization with current vs optimal weights |
| 8 | **Correlation Matrix** | Pairwise correlation heatmap |
| 9 | **Stress Testing** | Beta-adjusted losses under 5 crises + reverse stress test |
| 10 | **Factor Attribution** | CAPM decomposition: beta contribution vs alpha |
| 11 | **Tariff Exposure** | AAPL China COGS shock model |
| 12 | **Tax Liability** | Per-position LTCG at 23.8%, harvestable losses |
| 13 | **Options Chain** | Black-Scholes Greeks, put/call ratio, IV skew |
| 14 | **Allocation** | Doughnut chart of portfolio weights |
| 15 | **Macro Environment** | Live FRED data: Fed Funds, CPI YoY, 10Y Treasury |
| 16 | **News & Sentiment** | Deduplicated headlines with sentiment classification |
| 17 | **Legendary Investors** | SEC 13F cross-reference against 25+ investors |
| 18 | **What-If Simulator** | Preview metric changes before executing a trade |
| 19 | **Regime Risk Engine** | Rolling volatility regime detection with conditional VaR |
| 20 | **Event Calendar** | Upcoming earnings with historical return distributions |
| 21 | **Data Quality** | Per-ticker completeness, freshness, and quality score |
| 22 | **Admin Dashboard** | Credential-protected view of all database tables |
| 23 | **Prediction Markets** | Polymarket + Kalshi dual-exchange feed with arbitrage scanner |
| 24 | **My Bets** | Prediction market portfolio tracker with P&L |
| 25 | **EV Calculator** | Expected value and Kelly Criterion bet sizing |
| 26 | **Calibration Curve** | Resolved market accuracy with Brier score |
| 27 | **Market Correlations** | Cross-market dependency graph |
| 28 | **Smart Money** | Volume spike detection across prediction markets |
| 29 | **Learning Mode** | 9-stage gamified skill tree with quizzes and XP |
| 30 | **Badge Cabinet** | Achievement display with unlock criteria |
| 31 | **Portfolio Rebalancing** | Wealthfront-inspired allocation suggestions |
| 32 | **AI News Digest** | Per-holding news summary with sentiment |
| 33 | **Command Palette** | Cmd+K fuzzy search across all panels and actions |

Every metric card discloses its computation parameters. Every info button shows the exact formula. Panels 1-22 are available immediately in guest mode; panels gated behind Learning Mode unlock progressively as the user completes stages.

---

## API Endpoints

### Analytics (16 endpoints)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Backend + model server status |
| `/api/quote/{symbol}` | GET | Real-time stock quote |
| `/api/daily/{symbol}` | GET | Daily OHLCV data |
| `/api/intraday/{symbol}` | GET | Intraday OHLCV bars (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h) |
| `/api/news` | GET | Financial news for tickers |
| `/api/macro` | GET | FRED macro snapshot |
| `/api/filings/{ticker}` | GET | SEC EDGAR filings |
| `/api/options/{symbol}` | GET | Options chain with Greeks and IV skew |
| `/api/earnings` | GET | Upcoming earnings dates |
| `/api/holders` | GET | Institutional holders and legendary investor matches |
| `/api/portfolio/analyze` | POST | Full portfolio analysis (auto-saves snapshot if logged in) |
| `/api/whatif` | POST | What-if trade simulation |
| `/api/regime` | POST | Regime detection and conditional VaR |
| `/api/data-quality` | POST | Per-ticker data quality report |
| `/api/model/analyze` | POST | Direct LLM access |
| `/api/cache/clear` | POST | Clear the in-memory data cache |

### Prediction Markets (11 endpoints)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/polymarket` | GET | Trending Polymarket prediction markets with relevance scoring |
| `/api/kalshi` | GET | Trending Kalshi prediction events |
| `/api/polymarket/history/{clob_token_id}` | GET | Price history for a Polymarket outcome token (CLOB API) |
| `/api/kalshi/history/{ticker}` | GET | Candlestick history for a Kalshi market |
| `/api/predictions/analysis` | GET | AI analysis of trending prediction markets |
| `/api/arbitrage` | GET | Cross-platform arbitrage opportunities (Bellman-Ford) |
| `/api/calibration` | GET | Calibration curve from 500 resolved markets with Brier score |
| `/api/smart-money` | GET | Volume spike detection across prediction markets |
| `/api/market-correlations` | GET | Cross-market dependency correlation graph |
| `/api/news-digest` | POST | AI news digest for portfolio holdings |
| `/api/rebalance` | POST | Portfolio rebalancing suggestions |

### Database CRUD (30 endpoints)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/db/register` | POST | Create new user account |
| `/api/db/login` | POST | Authenticate user |
| `/api/db/users/{id}` | GET/PUT | User profile |
| `/api/db/users/{id}/dashboard` | GET | User dashboard stats |
| `/api/db/portfolios` | POST | Create portfolio |
| `/api/db/portfolios/{id}` | GET/PUT/DELETE | Portfolio CRUD |
| `/api/db/portfolios/{id}/holdings` | GET/POST | Holdings (auto-merges duplicates) |
| `/api/db/holdings/{id}` | PUT/DELETE | Update or remove holding |
| `/api/db/portfolios/{id}/snapshots` | GET | Paginated snapshot history |
| `/api/db/snapshots/{id}` | GET | Full snapshot detail |
| `/api/db/portfolios/{id}/trades` | GET/POST | Trade journal |
| `/api/db/users/{id}/watchlist` | GET/POST | Watchlist management |
| `/api/db/users/{id}/alerts` | GET/POST | Price/metric alerts |
| `/api/db/admin/login` | POST | Admin authentication |
| `/api/db/admin/overview` | GET | All tables (admin only) |

Full interactive docs at **http://localhost:8000/docs** (Swagger UI).

---

## Database

Veris uses **SQLite by default** — zero configuration, created automatically at `data/veris.db`.

For production, configure MySQL or PostgreSQL via `config/.env`:

```bash
DATABASE_URL=mysql+pymysql://user:password@host:3306/veris
```

The database is completely optional — guest mode works without it.

---

## Project Structure

```
veris/
├── backend/
│   ├── app.py                 # FastAPI server, 57 endpoints
│   ├── portfolio.py           # Core analytics engine
│   ├── advanced_analytics.py  # Monte Carlo, Frontier, Stress, Regime, Arbitrage
│   ├── data_fetcher.py        # yfinance, FRED, SEC, Polymarket, Kalshi
│   ├── options_math.py        # Black-Scholes pricing and Greeks
│   ├── cache.py               # Thread-safe in-memory TTL cache
│   ├── model_client.py        # Colab LLM bridge
│   └── database/              # SQLAlchemy persistence layer
│       ├── engine.py          # Connection pooling, multi-backend
│       ├── models.py          # 8 ORM models
│       ├── crud.py            # 35+ CRUD functions with audit logging
│       └── schemas.py         # 22 Pydantic DTOs
├── frontend/
│   └── static/
│       └── index.html         # Veris dashboard (33 panels + learning mode)
├── colab/
│   └── fingpt_server.ipynb    # LLM on Colab T4 GPU
├── config/
│   ├── .env.example           # Template
│   └── .env                   # Your secrets (git-ignored)
├── data/                      # Database file (git-ignored)
├── tests/
│   └── test_spec_validation.py
├── requirements.txt
├── CHANGELOG.md
├── LICENSE
└── README.md
```

---

## Requirements

- Python 3.9+
- Dependencies: `fastapi`, `uvicorn`, `httpx`, `pandas`, `numpy`, `yfinance`, `scipy`, `PyPortfolioOpt`, `SQLAlchemy`
- Browser: Any modern browser
- Optional: Google Colab with T4 GPU for AI features

---

## License

MIT License. See [LICENSE](LICENSE) for details.
