# Changelog

All notable changes to FinGPT Portfolio Analyzer.

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
