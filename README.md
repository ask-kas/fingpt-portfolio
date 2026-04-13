# FinGPT Portfolio Analyzer

An institutional-grade portfolio analytics platform that combines quantitative finance, Monte Carlo simulation, Markowitz optimization, options pricing, and AI-driven sentiment analysis in a single interactive dashboard. Built with a FastAPI backend, vanilla JavaScript frontend, and an optional FinGPT language model running on Google Colab.

**All quantitative analytics work offline with zero API cost.** The AI features (sentiment, insight) are optional and require a free Google Colab GPU.

---

## Contributors

This is a collaborative group project. Both contributors are co-creators.

| Contributor | Contributions |
|---|---|
| **Askar Kassimov** | Core platform: FastAPI backend, yfinance/FRED/SEC data pipeline, base portfolio analytics (Sharpe, volatility, max drawdown, diversification), FinGPT Colab integration with ngrok tunneling, and the initial frontend dashboard with allocation charts, news feed, macro indicators, and options chain viewer. |
| **Shihan Mahfuz** | Institutional-grade analytics rebuild, risk management system, and all features listed in [What was added](#what-was-added-by-shihan-mahfuz) below. |

---

## What was added by Shihan Mahfuz

### Mathematics and Analytics Engine

- **Log returns** replacing simple returns across the entire pipeline, with Bessel-corrected standard deviations (ddof=1)
- **Full covariance portfolio volatility**: `sigma_p = sqrt(w^T * Sigma * w)` using the complete correlation structure, not the diagonal-only approximation
- **252-day OLS beta** against SPY as the single canonical beta source used everywhere (holdings, stress tests, factor attribution)
- **Sortino ratio** using downside deviation only (returns below the minimum acceptable return)
- **Treynor ratio** (excess return per unit of systematic risk)
- **Calmar ratio** (annualized return divided by maximum drawdown)
- **Information ratio** (active return vs SPY divided by tracking error)
- **Jensen's alpha** via the CAPM formula: `alpha = R_p - (R_f + beta * (R_m - R_f))`
- **HHI concentration index**, **effective N** (1/HHI), and **diversification ratio** (sum of weighted vols divided by portfolio vol)
- **Wilder-smoothed RSI-14** with labeled bands (extreme oversold, oversold, neutral, overbought, extreme overbought)
- **Total return computation** including dividends, with dividend-adjusted cost basis
- **Tax liability engine** at 23.8% LTCG (20% federal + 3.8% NIIT) with tax loss harvesting identification
- **AAPL tariff exposure model** using China COGS ($87B), net income ($94B), configurable tariff rate and pass-through, with constant P/E price translation
- **CAPM factor attribution** decomposing portfolio return into beta contribution and alpha (skill)

### Monte Carlo VaR/CVaR (10,000 simulations)

- **Student-t marginal distribution** fitted per asset via MLE, with the conservative minimum degrees of freedom used across all assets to capture fat tails
- **Cholesky decomposition** of the full covariance matrix for correlated multi-asset draws
- **Rescaling** by `sqrt((nu-2)/nu)` so the simulated covariance matches the sample covariance exactly
- **30-day horizon** with daily compounding of log returns
- VaR at 95% and 99%, CVaR (expected shortfall), percentile fan chart (5th/25th/50th/75th/95th paths)

### Efficient Frontier Optimization

- **Ledoit-Wolf shrinkage** on the covariance matrix for stability with small samples
- **Black-Litterman style expected returns**: blends implied equilibrium returns (`Pi = lambda * Sigma * w_market`) with historical means at 50/50 to prevent corner solutions
- **Box constraints** (5% to 60% per name) to produce investable portfolios
- Current portfolio position, max Sharpe tangency portfolio, and minimum volatility portfolio plotted together

### Options Chain with Black-Scholes Greeks

- Full Black-Scholes pricing with **delta, gamma, theta, vega, rho** computed from market implied volatility
- **Put/call ratio** (open interest and volume based) with positioning interpretation
- **IV skew** (10% OTM put IV minus 10% OTM call IV) with market interpretation
- Risk-free rate sourced live from the 10-year Treasury via FRED

### Stress Testing

- Beta-adjusted losses under 5 historical crises (2008 GFC, COVID-19, 2022 rate hikes, dot-com bust, 2010 flash crash)
- **Reverse stress test**: solves for the market drop required to produce a given portfolio loss threshold
- Per-holding beta breakdown cards

### Regime-Aware Risk Engine

- **21-day rolling realized volatility** classifying the market into four regimes: low (<12%), normal (12-20%), elevated (20-30%), crisis (>30%)
- **Regime-conditional VaR** using only returns observed during the current regime, producing more accurate risk estimates than unconditional VaR
- Regime transition probabilities and historical regime distribution
- Rolling volatility bar chart with threshold lines

### What-If Trade Simulator

- Simulate adding or removing any position before executing a trade
- Recomputes the full portfolio metric stack on the hypothetical portfolio
- Shows before/after/delta for Sharpe, volatility, beta, HHI, effective N, and VaR
- Color-coded deltas indicating whether each metric improves or degrades

### Legendary Investors (SEC 13F)

- Cross-references portfolio stocks against institutional holder data from SEC 13F filings via yfinance
- Matches against 25+ curated legendary investors: Warren Buffett, Ray Dalio, Jim Simons, Ken Griffin, George Soros, Bill Ackman, Stanley Druckenmiller, Steve Cohen, David Tepper, Seth Klarman, Carl Icahn, Cathie Wood, and more
- Investor cards showing fund name, investing style, shares held, percentage, and dollar value
- **Dynamic search**: type any ticker to look up its institutional holders in real time, with removable tags and cached results
- Expandable top 10 institutional holders table per stock

### Event-Risk Calendar

- Upcoming earnings dates per stock holding from yfinance calendar data
- Historical earnings-day return distribution (close-to-close on announcement days)
- Average and standard deviation of earnings-day returns for sizing risk

### Data Quality Dashboard

- Per-ticker quality assessment: expected vs actual bars, missing percentage, zero volume days, staleness
- **Gap detection**: identifies multi-day gaps in the price series that are not explained by weekends
- **Composite quality score** (0-100): 40 points for completeness, 30 for freshness, 15 for volume quality, 15 for gap-free data
- Overall portfolio data quality score

### Frontend

- Complete UI redesign with dark theme, gradient accents, and responsive layout
- **Sticky navigation bar** with 20 section links and scroll-tracking highlight
- **Educational info modals** on every panel explaining the methodology, formulas, inputs, and interpretation
- **14 summary metric cards** (value, price return, total return, volatility, Sharpe, Sortino, Calmar, Treynor, info ratio, beta, alpha, HHI, effective N, diversification ratio)
- **16-column holdings table** with per-row stale price indicators, RSI labels, and tax cells
- **CSV/JSON export** with 19 fields including dividends, RSI labels, and tax breakdowns
- Interactive candlestick charts with SMA-20/SMA-50 overlays per holding
- Correlation heatmap with average off-diagonal interpretation
- Warnings banner merging backend warnings with stale price detection

### Database Persistence Layer

- **SQLAlchemy ORM** with 8 models: User, Portfolio, Holding, AnalysisSnapshot, TradeJournal, Watchlist, Alert, AuditLog
- **Multi-backend support**: SQLite (default, zero-config), MySQL, PostgreSQL — configured via `DATABASE_URL` or individual env vars
- **Connection pooling** (pool_size=10, max_overflow=20, pool_recycle=3600, pool_pre_ping=True) for production databases
- **User authentication** with session persistence (login, register, guest mode)
- **Portfolio auto-save**: holdings automatically synced to database on analysis
- **Auto-snapshot**: every analysis run saves a full analytics snapshot for historical tracking
- **Weighted-average cost basis** merge when adding duplicate symbols
- **Audit logging** on every write operation for full traceability
- **Admin dashboard** with tabbed view of all 8 database tables and aggregate stats
- **30 REST endpoints** under `/api/db/` for full CRUD on all entities
- **Trade journal** for recording executed, simulated, and rebalance trades
- **Watchlist and alerts** with configurable metric thresholds (price, Sharpe, beta, volatility, VaR, RSI)

### Infrastructure

- **CPI year-over-year fix**: fetches 16 months from FRED and uses date-matching (within 45-day tolerance) to handle missing observations
- **Live risk-free rate**: 10-year Treasury (preferred) -> Fed Funds -> 4.35% fallback, used consistently across Sharpe, Sortino, Treynor, Black-Scholes, and CAPM
- **URL fingerprint deduplication** for news articles (SHA-1 hash of normalized URL, strips tracking parameters)
- **In-memory TTL cache** with appropriate TTLs (prices 1hr, quotes 5min, news 15min, macro 4hr, holders 1hr)
- Price freshness metadata with staleness detection and age reporting
- Crypto symbol normalization (BTC -> BTC-USD) with 365-day annualization

---

## Architecture

```
Google Colab (T4 GPU)                          FRED API
  Llama-2-7B + FinGPT LoRA                    (macro data)
  4-bit NF4 quantized (~3.5 GB VRAM)               |
  Exposed via ngrok tunnel                          |
         |                                          |
         | HTTP                                     |
         v                                          v
  +-----------------------------------------------------------+
  |  FastAPI Backend (backend/)                               |
  |                                                           |
  |  app.py ................. API server, 45 endpoints        |
  |  portfolio.py ........... Core analytics engine           |
  |  advanced_analytics.py .. Monte Carlo, Frontier, Stress,  |
  |                           What-If, Regime, Data Quality   |
  |  data_fetcher.py ........ yfinance, FRED, SEC EDGAR,      |
  |                           Earnings, Institutional Holders |
  |  options_math.py ........ Black-Scholes + Greeks          |
  |  cache.py ............... In-memory TTL cache             |
  |  model_client.py ........ FinGPT Colab bridge             |
  |  database/ .............. SQLAlchemy ORM persistence      |
  |    engine.py ............ Connection pooling, multi-DB    |
  |    models.py ............ 8 ORM models (User, Portfolio,  |
  |                           Holding, Snapshot, Trade, etc.) |
  |    crud.py .............. 35+ CRUD functions + audit log  |
  |    schemas.py ........... Pydantic request/response DTOs  |
  +-----------------------------------------------------------+
         |                            |
         | HTML + JSON API :8000      | SQLAlchemy
         v                            v
  +---------------------------+  +---------------------------+
  |  Single-Page Dashboard    |  |  Database                 |
  |  (frontend/static/)       |  |  SQLite (default)         |
  |                           |  |  MySQL / PostgreSQL       |
  |  20 analytics panels      |  |  8 tables, audit log,     |
  |  Auth overlay (login/     |  |  auto-snapshots,          |
  |    register/guest)        |  |  connection pooling       |
  |  Admin dashboard panel    |  +---------------------------+
  |  Plotly.js, Chart.js      |
  +---------------------------+
```

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/Shihanmahfuz/fingpt-portfolio.git
cd fingpt-portfolio
pip install -r requirements.txt
```

### 2. Configure API keys

```bash
cp config/.env.example config/.env
```

Open `config/.env` and fill in your FRED API key (free at [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html)). All other keys are only needed for optional features.

### 3. Run

```bash
python3 backend/app.py
```

Open **http://localhost:8000** in your browser. Enter your holdings and click "Analyze Portfolio."

> **Note:** Use `python3` on macOS. If port 8000 is busy: `lsof -ti :8000 | xargs kill -9`

### 4. (Optional) Enable AI features

The AI features (FinGPT sentiment per headline, portfolio insight narrative) require a GPU:

1. Open `colab/fingpt_server.ipynb` in [Google Colab](https://colab.research.google.com/)
2. Runtime -> Change runtime type -> **T4 GPU** -> Save
3. Add `HF_TOKEN` and `NGROK_AUTH_TOKEN` to Colab Secrets (key icon in sidebar)
4. Runtime -> Run all. Wait 2-4 minutes for the model to load.
5. Copy the printed ngrok URL into `config/.env` as `COLAB_MODEL_URL`
6. Restart the backend. The status indicator turns green when connected.

---

## Dashboard Sections

| # | Section | Description |
|---|---------|-------------|
| 1 | **Portfolio Input** | Enter holdings: symbol, shares, avg cost, dividends per share |
| 2 | **Portfolio Summary** | 14 metric cards: value, returns, volatility, Sharpe, Sortino, Calmar, Treynor, info ratio, beta, alpha, HHI, effective N, diversification ratio |
| 3 | **AI Insight** | Natural language risk assessment from FinGPT (requires Colab) |
| 4 | **Holdings Detail** | 16-column table with per-stock metrics, RSI labels, tax cells. CSV/JSON export |
| 5 | **Price Charts** | Interactive candlestick charts with SMA-20 and SMA-50 overlays |
| 6 | **Monte Carlo VaR** | 10,000 simulated paths, VaR/CVaR at 95% and 99%, return histogram, fan chart |
| 7 | **Efficient Frontier** | Markowitz optimization with Ledoit-Wolf + Black-Litterman. Current vs optimal weights |
| 8 | **Correlation Matrix** | Pairwise correlation heatmap with diversification interpretation |
| 9 | **Stress Testing** | Beta-adjusted losses under 5 crises + reverse stress test |
| 10 | **Factor Attribution** | CAPM decomposition: beta contribution vs alpha (skill) |
| 11 | **Tariff Exposure** | AAPL China COGS shock model with constant P/E translation |
| 12 | **Tax Liability** | Per-position LTCG at 23.8%, harvestable losses, after-tax totals |
| 13 | **Options Chain** | Black-Scholes Greeks, put/call ratio, IV skew |
| 14 | **Allocation** | Doughnut chart of portfolio weights |
| 15 | **Macro Environment** | Live FRED data: Fed Funds, CPI YoY, 10Y Treasury, unemployment, S&P 500 |
| 16 | **News & Sentiment** | Deduplicated headlines with FinGPT sentiment badges |
| 17 | **Legendary Investors** | SEC 13F cross-reference against 25+ top investors. Dynamic ticker search |
| 18 | **What-If Simulator** | Preview metric changes before executing a trade |
| 19 | **Regime Risk Engine** | Rolling volatility regime detection with conditional VaR |
| 20 | **Event Calendar** | Upcoming earnings dates with historical return distributions |
| 21 | **Data Quality** | Per-ticker completeness, freshness, gaps, and quality score |
| 22 | **Admin Dashboard** | Tabbed view of all 8 database tables with aggregate stats (click Admin button in header) |

Every section has an **(i)** info button that opens an educational modal explaining the methodology, formulas, inputs, and interpretation.

The app starts with a **login/register overlay** — create an account or continue as guest. Logged-in users get automatic portfolio persistence across sessions.

---

## API Endpoints

### Analytics (15 endpoints)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Backend + model server status |
| `/api/quote/{symbol}` | GET | Real-time stock quote |
| `/api/daily/{symbol}` | GET | Daily OHLCV data (default 100 bars) |
| `/api/news` | GET | Financial news for tickers (comma-separated) |
| `/api/macro` | GET | FRED macro snapshot (5 indicators) |
| `/api/filings/{ticker}` | GET | SEC EDGAR filings (10-K, 10-Q) |
| `/api/options/{symbol}` | GET | Options chain with Greeks and IV skew |
| `/api/earnings` | GET | Upcoming earnings dates and historical returns |
| `/api/holders` | GET | Institutional holders and legendary investor matches |
| `/api/portfolio/analyze` | POST | Full portfolio analysis (auto-saves snapshot if user logged in) |
| `/api/whatif` | POST | What-if trade simulation with metric deltas |
| `/api/regime` | POST | Regime detection and conditional VaR |
| `/api/data-quality` | POST | Per-ticker data quality report |
| `/api/model/analyze` | POST | Direct FinGPT access (sentiment/headline/insight) |
| `/api/cache/clear` | POST | Clear the in-memory data cache |

### Database CRUD (30 endpoints)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/db/register` | POST | Create new user account |
| `/api/db/login` | POST | Authenticate and get user + default portfolio |
| `/api/db/users/{id}` | GET/PUT | Get or update user profile |
| `/api/db/users/{id}/dashboard` | GET | User dashboard stats (holdings, trades, snapshots) |
| `/api/db/portfolios` | POST | Create a new portfolio |
| `/api/db/portfolios/{id}` | GET/PUT/DELETE | Portfolio CRUD |
| `/api/db/users/{id}/portfolios` | GET | List user's portfolios |
| `/api/db/portfolios/{id}/holdings` | GET/POST | List or add holdings (auto-merges duplicates) |
| `/api/db/holdings/{id}` | PUT/DELETE | Update or remove a holding |
| `/api/db/portfolios/{id}/snapshots` | GET | Paginated analysis snapshot history |
| `/api/db/snapshots/{id}` | GET | Full snapshot detail with payload |
| `/api/db/portfolios/{id}/snapshots/latest` | GET | Most recent snapshot |
| `/api/db/portfolios/{id}/snapshots/timeseries` | GET | Metric time-series (Sharpe, VaR, etc.) |
| `/api/db/portfolios/{id}/trades` | GET/POST | Trade journal (record and list trades) |
| `/api/db/portfolios/{id}/trades/summary` | GET | Trade summary stats |
| `/api/db/users/{id}/watchlist` | GET/POST | Watchlist management |
| `/api/db/watchlist/{id}` | PUT/DELETE | Update or remove watchlist item |
| `/api/db/users/{id}/alerts` | GET/POST | Price/metric alerts |
| `/api/db/alerts/{id}` | PUT/DELETE | Update or remove alert |
| `/api/db/users/{id}/activity` | GET | Recent audit log entries |
| `/api/db/admin/overview` | GET | All tables with stats (admin dashboard) |

Full interactive API docs available at **http://localhost:8000/docs** (Swagger UI).

---

## Quantitative Methods

### Returns and Risk

| Metric | Formula | Notes |
|--------|---------|-------|
| Log returns | `r_t = ln(P_t / P_{t-1})` | Used everywhere. Oldest-first output. |
| Annualized volatility | `sigma * sqrt(252)` | Bessel-corrected (ddof=1). Full covariance for portfolio level. |
| Sharpe ratio | `(R_p - R_f) / sigma_p` | R_f from live 10Y Treasury. |
| Sortino ratio | `(R_p - R_f) / sigma_downside` | Only penalizes returns below MAR. |
| Calmar ratio | `R_annual / MaxDD` | Return per unit of worst-case loss. |
| Treynor ratio | `(R_p - R_f) / beta` | Excess return per unit of systematic risk. |
| Information ratio | `mean(R_p - R_b) / std(R_p - R_b)` | Active return vs SPY, annualized. |
| Beta | OLS slope of `r_stock ~ r_spy` | 252-day window. Single canonical source. |
| Jensen's alpha | `R_p - (R_f + beta * (R_m - R_f))` | CAPM residual. Positive = skill. |
| HHI | `sum(w_i^2)` | Concentration. 1/n = perfect diversification. |
| Effective N | `1 / HHI` | Equivalent number of equal-weight positions. |
| Diversification ratio | `sum(w_i * sigma_i) / sigma_portfolio` | >1 means correlations are helping. |
| Max drawdown | `max((peak - trough) / peak)` | Scanned across full price history. |
| RSI-14 | Wilder smoothing | Seeded with SMA of first 14 deltas, then exponentially smoothed. |

### Monte Carlo VaR

1. Build daily log return matrix, align to common length
2. Estimate mean vector, covariance matrix (Bessel), Student-t dof per asset (MLE)
3. Cholesky factor `L = cholesky(Sigma + 1e-10 * I)`
4. Draw 10,000 x 30 days of iid Student-t vectors, rescale by `sqrt((nu-2)/nu)`, apply `L`
5. Portfolio daily log return = weight dot product. Cumulate and convert to simple returns.
6. VaR 95 = 5th percentile. CVaR 95 = mean below VaR.

### Efficient Frontier

1. Ledoit-Wolf shrunk covariance for stability
2. Black-Litterman implied returns: `Pi = lambda * Sigma * w_market` (lambda=2.5)
3. Blend 50/50 with historical mean returns
4. Box constraints: 5% to 60% per position
5. Sweep 50 target returns between min-vol and max-Sharpe

### Black-Scholes Greeks

| Greek | Meaning | Computed as |
|-------|---------|-------------|
| Delta | Price sensitivity | `dC/dS = N(d1)` for calls |
| Gamma | Delta sensitivity | `d2C/dS2 = n(d1) / (S * sigma * sqrt(T))` |
| Theta | Time decay | `dC/dT / 365` (per calendar day) |
| Vega | Volatility sensitivity | `dC/dsigma / 100` (per vol point) |
| Rho | Rate sensitivity | `dC/dr / 100` (per rate point) |

### Stress Testing

| Scenario | Period | Market Drop |
|----------|--------|-------------|
| 2008 Global Financial Crisis | Sep 2008 - Mar 2009 | -38.9% |
| COVID-19 Crash | Feb - Mar 2020 | -33.7% |
| 2022 Rate Hike Selloff | Jan - Oct 2022 | -25.2% |
| Dot-Com Bust | Mar 2000 - Oct 2002 | -49.1% |
| 2010 Flash Crash | May 6, 2010 | -6.9% |

Portfolio loss = `portfolio_beta * market_drop`. Reverse stress test: `market_drop = loss_threshold / portfolio_beta`.

---

## Data Sources

| Source | Data | Auth |
|--------|------|------|
| **yfinance** | Prices, OHLCV, options chains, news, earnings calendar, institutional holders | None (free) |
| **FRED API** | Fed Funds Rate, CPI (YoY computed), unemployment, 10Y Treasury, S&P 500 | Free API key |
| **SEC EDGAR** | Company filings (10-K, 10-Q) | User-Agent string |
| **FinGPT (Colab)** | Sentiment, headline classification, portfolio insight | HuggingFace token + ngrok |

---

## Project Structure

```
fingpt-portfolio/
├── backend/
│   ├── app.py                 # FastAPI server, 45 API endpoints, request routing
│   ├── portfolio.py           # Core analytics: returns, volatility, beta, alpha,
│   │                          #   Sharpe, Sortino, Treynor, Calmar, RSI, tax, tariff
│   ├── advanced_analytics.py  # Monte Carlo VaR, Efficient Frontier, Correlation,
│   │                          #   Stress Test, What-If Simulator, Regime Detection,
│   │                          #   Data Quality Report
│   ├── data_fetcher.py        # yfinance client (quotes, daily, news, options,
│   │                          #   earnings, institutional holders), FRED client
│   │                          #   (macro indicators, CPI YoY), SEC EDGAR client
│   ├── options_math.py        # Black-Scholes pricing and Greeks
│   ├── cache.py               # In-memory TTL cache (no external dependencies)
│   ├── model_client.py        # Async HTTP bridge to FinGPT Colab server
│   └── database/              # SQLAlchemy persistence layer
│       ├── __init__.py        # Package exports
│       ├── engine.py          # Connection pooling, multi-backend (SQLite/MySQL/PG)
│       ├── models.py          # 8 ORM models with UUID PKs, UTC timestamps
│       ├── crud.py            # 35+ CRUD functions with automatic audit logging
│       └── schemas.py         # 22 Pydantic request/response DTOs
├── frontend/
│   └── static/
│       └── index.html         # Single-page dashboard (~1800 lines)
│                              #   Plotly.js, Chart.js, 22 panels, auth overlay,
│                              #   admin dashboard, nav bar
├── colab/
│   └── fingpt_server.ipynb    # Llama-2-7B + FinGPT LoRA on Colab T4 GPU
├── config/
│   ├── .env.example           # Template with placeholder keys + DB config
│   └── .env                   # Your secrets (git-ignored)
├── data/                      # SQLite database file (git-ignored)
├── tests/
│   └── test_spec_validation.py  # Validation tests for math correctness
├── requirements.txt
├── CHANGELOG.md
├── LICENSE                    # MIT
└── README.md
```

---

## Supported Assets

- **Stocks**: Enter ticker symbols directly (AAPL, MSFT, GOOGL, NVDA, TSLA, etc.)
- **Crypto**: Enter shorthand (BTC, ETH, SOL, ADA, DOGE, etc.) -- auto-mapped to BTC-USD format with 365-day annualization
- **Options**: View full chains with Greeks for any stock holding after analysis

---

## Database

FinGPT uses **SQLite by default** — zero configuration, the database file is created automatically at `data/fingpt.db` on first run.

For production deployments, configure MySQL or PostgreSQL via `config/.env`:

```bash
# Option 1: Full connection URL
DATABASE_URL=mysql+pymysql://user:password@host:3306/fingpt

# Option 2: Individual variables
DB_HOST=localhost
DB_USER=your_user
DB_PASSWORD=your_password
DB_NAME=fingpt
DB_PORT=3306
DB_DRIVER=mysql+pymysql
```

The database is **completely optional** — guest mode works without it, and all analytics run without persistence.

---

## Requirements

- Python 3.9+
- Dependencies: `fastapi`, `uvicorn`, `httpx`, `pandas`, `numpy`, `yfinance`, `scipy`, `PyPortfolioOpt`, `SQLAlchemy`, `PyMySQL`
- Browser: Any modern browser (Chrome, Firefox, Safari, Edge)
- Optional: Google Colab account with T4 GPU access (free tier works) for AI features

---

## License

MIT License. See [LICENSE](LICENSE) for details.
