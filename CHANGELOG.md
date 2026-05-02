# Changelog

All notable changes to Veris — Portfolio Intelligence.

---

## v3.0.0 (2026-04-29)

Prediction markets, gamified learning, trading tools, and portfolio intelligence upgrades. Veris now covers traditional equities, options, macro, and binary prediction markets in a single dashboard.

### Added

**Prediction Markets** (Shihan Mahfuz)
- Polymarket + Kalshi dual-exchange integration with unified market feed
- Historical price charts via Polymarket CLOB API and Kalshi candlestick endpoints
- Cross-platform arbitrage scanner using Bellman-Ford algorithm for multi-hop opportunity detection
- Relevance scoring algorithm with finance keyword matching and meme/novelty filtering
- My Bets portfolio tracker with real-time P&L, average entry price, and outcome tracking
- Both/side-by-side view mode for comparing Polymarket vs Kalshi pricing on matched events
- Collapsible prediction markets panel with persistent open/close state

**Trading Tools** (Shihan Mahfuz)
- EV Calculator for binary prediction markets (expected value with implied probability)
- Kelly Criterion optimal bet sizing with fractional Kelly slider
- Arbitrage scanner across 500+ Polymarket and 350+ Kalshi markets with live spread detection
- Smart money volume spike detection with configurable sensitivity thresholds

**Market Intelligence** (Shihan Mahfuz)
- Calibration curve built from 500 resolved Polymarket markets with Brier score accuracy metric
- Cross-market dependency correlation graph linking related prediction markets
- AI prediction market analysis with trend synthesis from both exchanges

**Portfolio Enhancements** (Shihan Mahfuz)
- Portfolio rebalancing suggestions inspired by Wealthfront's automated allocation methodology
- AI news digest for portfolio holdings with per-ticker summary and sentiment

**Learning Mode** (Shihan Mahfuz)
- 9-stage gamified learning system with 56 lessons and 34 quizzes covering investing fundamentals through advanced analytics
- Duolingo-style vertical skill tree with custom SVG icons for each stage
- XP system with 5 ranks (Novice, Apprentice, Analyst, Strategist, Portfolio Master) and 9 achievement badges
- Tool locking/unlocking system gating 25 dashboard panels behind learning progress
- 55 embedded YouTube video links and 38 Investopedia article references as learning resources
- Quiz passing mark at 70% with retry and per-question feedback
- Badge cabinet displaying earned and locked achievements with unlock criteria
- Streak tracking with daily login detection and streak multiplier
- Confetti unlock ceremonies on stage completion and badge earn
- Admin bypass for user `shihanmahfuz` and tester mode for user `abdullah`

**UX/Frontend** (Shihan Mahfuz)
- Cmd+K command palette (Linear-inspired) with fuzzy search across all dashboard panels and actions
- Graduated gray design system replacing flat backgrounds with depth-layered surfaces
- Glassmorphism metric cards with backdrop blur and subtle border highlights
- Green Veris favicon (SVG) matching the brand identity

### Fixed

**Bug Fixes** (Shihan Mahfuz)
- Fixed 8 bugs identified in the initial code audit
- Fixed what-if simulator allowing sale of non-owned stocks and overselling existing positions
- Fixed regime detection date misalignment between volatility series and market data
- Fixed drawdown calculation division by zero when cumulative max is zero
- Thread-safe cache with locking to prevent race conditions under concurrent requests
- Variable shadowing fix in `renderResults` where inner `let` masked outer scope

### New API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/polymarket` | GET | Trending Polymarket prediction markets |
| `/api/kalshi` | GET | Trending Kalshi prediction events |
| `/api/polymarket/history/{clob_token_id}` | GET | Price history for a Polymarket outcome token |
| `/api/kalshi/history/{ticker}` | GET | Candlestick history for a Kalshi market |
| `/api/predictions/analysis` | GET | AI analysis of trending prediction markets |
| `/api/arbitrage` | GET | Cross-platform arbitrage opportunities |
| `/api/calibration` | GET | Calibration curve from resolved markets |
| `/api/smart-money` | GET | Volume spike detection across markets |
| `/api/market-correlations` | GET | Cross-market dependency correlations |
| `/api/news-digest` | POST | AI news digest for portfolio holdings |
| `/api/rebalance` | POST | Portfolio rebalancing suggestions |

---

## v2.1.0 (2026-04-17)

Minute-resolution intraday data. Veris now covers the full time spectrum from 1-minute ticks to daily bars.

### Added

**Intraday Tape** (Shihan Mahfuz)
- New `GET /api/intraday/{symbol}` endpoint returning minute-resolution OHLCV bars
- Eight Yahoo intraday intervals supported: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h
- Interval-aware default periods so Yahoo's caps are never hit (1m→1d, 5m→5d, 30m→1mo, 1h→3mo)
- UTC-normalized ISO-8601 timestamps on every bar
- Freshness metadata on newest bar: `fetched_at`, `age_seconds`, `is_stale`, `interval`
- Staleness threshold scales with bar size: 3× interval for stocks, 2× for crypto (trades 24/7)
- Interval-tuned TTL caching: 30s for 1m, 120s for 2–5m, 300s for coarser intervals
- Input validation returns 400 on invalid intervals with the allowed list
- 400 validation errors distinct from 404 no-data responses

**Frontend — Intraday Tape Panel**
- New full-width panel in the Charts section, populated from active holdings
- Per-holding tabs for one-click ticker switching
- Free-text symbol input (stocks, crypto like `BTC-USD`, indices)
- Interval dropdown (1m, 2m, 5m, 15m, 30m, 1h) with auto-refresh on change
- Candlestick chart with dedicated volume pane (domain-split y-axes)
- Category-axis x-labels (`MM-DD HH:MM`) to eliminate overnight/weekend gaps
- Monospace freshness status line, green when live, red when stale
- Info modal explaining Yahoo's windows, staleness math, and caching

---

## v2.0.0 (2026-04-13)

Complete rebrand from FinGPT to Veris. New visual identity, design system, and brand voice.

### Changed

**Brand Identity** (Shihan Mahfuz)
- Renamed from "FinGPT Portfolio Analyzer" to "Veris — Portfolio Intelligence"
- New color system: Veris Deep (#0A3D2E), Signal (#1D9E75), Mist (#5DCAA5), Risk Red (#E24B4A), Amber (#EF9F27)
- Typography: Georgia serif for brand/display, system sans for UI, monospace for financial values
- Veris logotype with signature dot (reads as decimal point / verification mark)
- Dark theme built on Void (#111816) with green-tinted surfaces
- All buttons, accents, and interactive elements use Veris Signal green
- Metric card values rendered in monospace for digit alignment

**Security**
- Password hashing upgraded from SHA-256 to PBKDF2-HMAC-SHA256 (160k iterations) with bcrypt fallback
- Removed hardcoded default admin key; ADMIN_KEY env var now required
- Timing-safe comparison for admin key verification
- Legacy password hashes auto-migrate on login

**Backend**
- All module docstrings, loggers, and FastAPI title updated to Veris
- Database file renamed from fingpt.db to veris.db
- Session storage key renamed from fingpt_session to veris_session

**Frontend**
- Auth overlay updated with Veris branding and Georgia serif logotype
- Admin panel styled with Veris design tokens
- All FinGPT text references replaced throughout UI and JavaScript
- Model status messages updated to Veris voice

---

## v1.1.0 (2026-04-12)

Database persistence layer with user authentication, portfolio auto-save, admin dashboard, and 30 new API endpoints.

### Added

**Database Persistence** (Shihan Mahfuz)
- SQLAlchemy ORM with 8 models: User, Portfolio, Holding, AnalysisSnapshot, TradeJournal, Watchlist, Alert, AuditLog
- Multi-backend support: SQLite (default, zero-config), MySQL, PostgreSQL via DATABASE_URL
- Connection pooling (pool_size=10, max_overflow=20, pool_recycle=3600, pool_pre_ping=True)
- 35+ CRUD functions with automatic audit logging on every write
- 22 Pydantic request/response schemas with validation
- Holdings auto-merge on duplicate symbol with weighted-average cost basis
- Auto-snapshot: every `/api/portfolio/analyze` call saves full analytics payload to DB
- Snapshot time-series queries for tracking portfolio metrics over time

**User Authentication**
- Login, register, and guest mode with session persistence via localStorage
- Auth overlay on app launch (login form, registration form, guest bypass)
- User bar in header showing logged-in username with Sign Out button

**Admin Dashboard**
- Admin button in header (visible to all logged-in users)
- Tabbed overlay panel showing all 8 database tables
- Aggregate stats grid (users, portfolios, holdings, snapshots, trades)
- Dynamic table rendering with smart formatting (timestamps, currency, booleans)
- Single API call (`/api/db/admin/overview`) joins all tables with usernames

**30 New API Endpoints** under `/api/db/`
- User auth: register, login, get, update, dashboard stats
- Portfolio CRUD: create, read, update, delete, list by user
- Holdings CRUD: list, add (with merge), update, delete
- Snapshots: list (paginated), detail, latest, time-series
- Trade journal: record, list, summary stats
- Watchlist: add, list, update, remove
- Alerts: create, list, update, remove
- Audit log: recent activity by user
- Admin: full overview with all tables and stats

**Frontend Enhancements**
- Auth overlay with login/register/guest mode
- Session management (auto-load portfolio on return)
- Holdings auto-sync to database on successful analysis
- Save indicator flash on successful DB write
- Admin dashboard panel with tabbed table viewer

**Infrastructure**
- `backend/database/` package: engine.py, models.py, crud.py, schemas.py
- SQLite WAL mode with foreign keys enabled
- UUID hex primary keys, UTC timestamps throughout
- JSON columns for analytics snapshot payloads
- `requirements.txt`: added SQLAlchemy, PyMySQL
- `config/.env.example`: added DATABASE_URL and individual DB config vars
- `.gitignore`: added `data/` for SQLite database file

---

## v1.0.0 (2026-04-12)

Full institutional-grade analytics platform with 21 dashboard panels, 15 API endpoints, and interactive educational documentation.

### Added

**Analytics Engine** (Shihan Mahfuz)
- Log returns with Bessel-corrected standard deviations across the entire pipeline
- Full covariance portfolio volatility: `sigma_p = sqrt(w^T * Sigma * w)`
- 252-day OLS beta against SPY as the single canonical beta source
- Sortino, Treynor, Calmar, and Information ratios
- Jensen's alpha via CAPM
- HHI concentration, effective N, and diversification ratio
- Wilder-smoothed RSI-14 with labeled bands
- Total return computation including dividends
- Tax liability at 23.8% LTCG with tax loss harvesting identification
- AAPL tariff exposure model (China COGS shock with constant P/E translation)
- CAPM factor attribution (beta contribution vs alpha)

**Monte Carlo VaR/CVaR**
- 10,000 simulations with Student-t marginal distributions (MLE fitted)
- Cholesky decomposition for correlated multi-asset draws
- 30-day horizon with VaR/CVaR at 95% and 99%
- Percentile fan chart and return histogram

**Efficient Frontier**
- Ledoit-Wolf shrinkage on covariance matrix
- Black-Litterman style expected returns (equilibrium + historical blend)
- Box constraints (5% to 60% per position)
- Current vs max Sharpe vs min volatility comparison

**Options Chain**
- Black-Scholes Greeks (delta, gamma, theta, vega, rho) from market IV
- Put/call ratio (OI and volume) with positioning interpretation
- IV skew (10% OTM) with market interpretation
- Live risk-free rate from 10Y Treasury

**Stress Testing**
- Beta-adjusted losses under 5 historical crises
- Reverse stress test (what market drop triggers a given portfolio loss)
- Per-holding beta breakdown

**Regime-Aware Risk Engine**
- 21-day rolling realized volatility with 4 regime classifications
- Regime-conditional VaR vs unconditional VaR
- Transition probabilities and regime history chart

**What-If Trade Simulator**
- Simulate buy/sell before executing
- Before/after/delta for Sharpe, volatility, beta, HHI, effective N, VaR

**Legendary Investors (SEC 13F)**
- Cross-reference against 25+ legendary investors (Buffett, Dalio, Simons, etc.)
- Dynamic ticker search with removable tags and caching
- Top 10 institutional holders per stock

**Event-Risk Calendar**
- Upcoming earnings dates from yfinance
- Historical earnings-day return distributions

**Data Quality Dashboard**
- Per-ticker completeness, freshness, zero volume, gap detection
- Composite quality score (0-100)

**Frontend**
- Dark theme UI redesign with 20 analytics panels
- Sticky navigation bar with scroll-tracking highlight
- Educational info modals on every section
- 14 summary metric cards, 16-column holdings table
- CSV/JSON export with 19 fields

**Infrastructure**
- CPI YoY fix (16-month fetch with date-matching)
- Live risk-free rate cascade (10Y Treasury -> Fed Funds -> fallback)
- URL fingerprint deduplication for news (SHA-1)
- In-memory TTL cache
- Price freshness metadata with staleness detection

### Fixed
- Stress test beta was always 1.0 (SPY data not being passed to function)
- CPI showing "N/A" due to FRED missing value handling
- FRED API key not loading from config/.env
- Tax totaling discrepancy (~$9 off) from missing loss benefit in footer sum

---

## v0.2.0 (2026-04-06)

Advanced analytics layer added on top of the core platform.

### Added (Shihan Mahfuz)

- Monte Carlo VaR/CVaR simulation (initial multivariate normal version)
- Markowitz Efficient Frontier with PyPortfolioOpt
- Correlation matrix heatmap
- Historical stress testing (5 scenarios)
- Sortino, Calmar, Beta, Alpha, Treynor ratios
- Interactive candlestick charts with SMA overlays
- SPY benchmark integration for beta computation
- Frontend redesign with educational info modals
- In-memory caching system

---

## v0.1.0 (2026-03-12)

Core platform created.

### Added (Askar Kassimov)

- FastAPI backend with yfinance, FRED API, and SEC EDGAR data fetching
- Base portfolio analytics (Sharpe, volatility, max drawdown, diversification score)
- FinGPT Colab integration (Llama-2-7B + LoRA, 4-bit quantized, ngrok tunnel)
- Frontend dashboard with allocation chart, news feed, macro indicators
- Options chain viewer (calls/puts, IV, volume, open interest)
- Yahoo Finance migration (from Alpha Vantage)
