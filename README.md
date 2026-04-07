# FinGPT Portfolio Analyzer v4

An institutional-grade portfolio analytics platform powered by FinGPT (Llama2-7B + LoRA).
Combines quantitative finance, Monte Carlo simulation, Markowitz optimization, and
AI-driven sentiment analysis in a single interactive dashboard.

**v3 (Core Platform)** — Askar Kassimov
**v4 (Advanced Analytics + Frontend Redesign)** — Shihan Mahfuz

---

## Architecture

```
Google Colab (T4 GPU)                          FRED API
  Llama2-7B + FinGPT LoRA                     (macro data)
  4-bit quantized (~3.5 GB VRAM)                   |
  Exposed via ngrok tunnel                         |
         |                                         |
         | HTTP                                    |
         v                                         v
  +---------------------------------------------------------+
  |  FastAPI Backend (Python 3.9+)                          |
  |                                                         |
  |  app.py ................ API server, request routing     |
  |  data_fetcher.py ....... yfinance, FRED, SEC EDGAR      |
  |  portfolio.py .......... Core analytics engine          |
  |  advanced_analytics.py . Monte Carlo, Frontier, Stress  |
  |  cache.py .............. In-memory TTL cache            |
  |  model_client.py ....... FinGPT Colab bridge            |
  +---------------------------------------------------------+
         |
         | Serves HTML + JSON API
         v
  +---------------------------------------------------------+
  |  Single-Page Dashboard (Vanilla JS)                     |
  |                                                         |
  |  Plotly.js .... Candlestick, Monte Carlo, Heatmaps      |
  |  Chart.js ..... Allocation doughnut                     |
  |  Info Modals .. Educational explanations per section     |
  +---------------------------------------------------------+
```

---

## Quantitative Methods and Formulas

### Daily Returns

Simple percentage returns computed from closing prices (oldest to newest):

```
r_t = (P_t - P_{t-1}) / P_{t-1}
```

Where `P_t` is the closing price on day *t*.

---

### Annualized Volatility

Standard deviation of daily returns, scaled to annual:

```
sigma_annual = sigma_daily * sqrt(T)
```

Where `T = 252` (trading days) for stocks and `T = 365` for crypto.

**Why it matters:** Volatility measures how much a stock's price fluctuates. Higher volatility means more uncertainty. Annualizing lets you compare assets with different trading frequencies.

---

### Sharpe Ratio

Risk-adjusted return relative to a risk-free benchmark:

```
Sharpe = (mean(r - r_f)) / std(r - r_f) * sqrt(T)
```

Where `r_f` is the daily risk-free rate derived from the Fed Funds Rate (fetched live from FRED API).

**Interpretation:**
- `> 1.0` — Good risk-adjusted performance
- `> 2.0` — Very good
- `< 0` — Underperforming the risk-free rate (e.g., T-bills)

**Note:** A negative Sharpe (like -1.8) means the portfolio's annualized return is below the risk-free rate. This is mathematically correct and common during market downturns. It does not indicate a bug.

---

### Sortino Ratio

Like Sharpe, but only penalizes downside volatility:

```
Sortino = mean(r - r_f) / std(r_downside) * sqrt(T)
```

Where `r_downside` includes only the excess returns that are negative.

**Why it matters:** Investors typically only care about downside risk, not upside "risk." The Sortino ratio gives a better picture for asymmetric return distributions.

---

### Maximum Drawdown

Largest peak-to-trough decline in the price series:

```
MaxDD = max_over_t [ (Peak_t - Trough_t) / Peak_t ]
```

**Why it matters:** Tells you the worst historical loss an investor would have experienced. A 30% max drawdown means at some point, the investment fell 30% from its high.

---

### Beta (vs. SPY)

Sensitivity of a stock's returns to market (S&P 500) returns:

```
Beta = Cov(r_stock, r_market) / Var(r_market)
```

SPY daily data is fetched automatically as the benchmark.

**Interpretation:**
- `Beta = 1.0` — Moves with the market
- `Beta > 1.0` — More volatile than market (amplifies moves)
- `Beta < 1.0` — Less volatile than market (dampens moves)

---

### Jensen's Alpha

Excess return beyond what beta predicts (CAPM-based):

```
Alpha = (mean(r_stock) - r_f) - Beta * (mean(r_market) - r_f)
```

Annualized by multiplying the daily alpha by `T`.

**Why it matters:** Positive alpha means the stock outperformed what you'd expect given its risk level. It measures manager skill or stock-specific outperformance.

---

### Treynor Ratio

Excess return per unit of systematic (beta) risk:

```
Treynor = (R_annual - r_f) / Beta
```

**Why it matters:** While Sharpe uses total risk (volatility), Treynor uses only systematic risk (beta). Useful for evaluating assets within a diversified portfolio.

---

### Calmar Ratio

Annualized return divided by maximum drawdown:

```
Calmar = R_annual / MaxDD
```

**Why it matters:** Combines profitability with worst-case loss. Higher is better — it means you're earning more per unit of "pain."

---

### RSI (Relative Strength Index)

Momentum oscillator measuring speed and change of price movements:

```
RS = avg_gain_over_14_days / avg_loss_over_14_days
RSI = 100 - (100 / (1 + RS))
```

**Interpretation:**
- `RSI > 70` — Overbought (potential pullback)
- `RSI < 30` — Oversold (potential bounce)
- `RSI ~ 50` — Neutral

---

### Simple Moving Averages (SMA-20, SMA-50)

Arithmetic mean of closing prices over a rolling window:

```
SMA_n = (1/n) * sum(P_{t-i} for i in 0..n-1)
```

**Why it matters:** Short-term SMA (20-day) crossing above long-term SMA (50-day) is a bullish "golden cross" signal. The reverse is a "death cross."

---

### Diversification Score

Based on the Herfindahl-Hirschman Index (HHI):

```
HHI = sum(w_i^2) for each holding weight w_i
Score = 1 - HHI
```

**Range:** 0 (single asset) to approaching 1 (perfectly diversified).

---

## Advanced Analytics (v4)

### Monte Carlo Value at Risk (VaR / CVaR)

Simulates 10,000 possible 30-day futures using historical return distributions.

**Method:**
1. Compute mean daily returns and covariance matrix from historical data
2. Sample daily returns from a multivariate normal distribution: `r ~ N(mu, Sigma)`
3. Compound daily returns over 30 days: `V_T = V_0 * product(1 + r_t)`
4. VaR at 95% = 5th percentile of the final return distribution
5. CVaR (Expected Shortfall) = average of returns below the VaR threshold

```
VaR_95 = Percentile(simulated_returns, 5)
CVaR_95 = mean(r | r <= VaR_95)
```

**Why VaR matters:** "With 95% confidence, your portfolio will not lose more than X% over 30 days."
**Why CVaR matters:** "If the worst does happen (bottom 5%), on average you'd lose Y%." CVaR captures tail risk better than VaR.

**Visualization:** Histogram of return distribution with VaR lines, plus a percentile fan chart (5th, 25th, 50th, 75th, 95th) showing portfolio value paths over time.

---

### Efficient Frontier (Markowitz Mean-Variance Optimization)

Finds the set of portfolios that maximize return for each level of risk.

**Method (using PyPortfolioOpt):**
1. Estimate expected returns via mean historical return
2. Estimate risk via sample covariance matrix
3. Solve the quadratic optimization problem:
   ```
   minimize  w' * Sigma * w
   subject to  w' * mu >= target_return
                sum(w) = 1,  w >= 0
   ```
4. Sweep target returns to generate the frontier curve
5. Identify special portfolios:
   - **Max Sharpe** — tangency portfolio (highest Sharpe ratio)
   - **Min Volatility** — leftmost point on the frontier

**Visualization:** Scatter plot showing the frontier curve, your current portfolio position, the max-Sharpe point, and the min-volatility point. Below it, a comparison of your current allocation weights vs. the optimal weights.

---

### Correlation Matrix

Pearson correlation coefficients between all pairs of holdings:

```
rho_{i,j} = Cov(r_i, r_j) / (sigma_i * sigma_j)
```

**Range:** -1 (perfect inverse) to +1 (perfect positive).

**Interpretation:** Low average correlation means good diversification — your holdings don't all move together. High correlation means concentrated risk.

**Visualization:** Color-coded heatmap (green = low/negative correlation, red = high correlation).

---

### Historical Stress Testing

Estimates portfolio losses under 5 major historical market crises using beta-adjusted returns:

```
Estimated_Loss_i = Beta_i * Market_Drop
Portfolio_Loss = sum(w_i * Estimated_Loss_i)
```

| Scenario | Period | Market Drop |
|----------|--------|-------------|
| 2008 Global Financial Crisis | Sept 2008 - Mar 2009 | -38.9% |
| COVID-19 Crash | Feb - Mar 2020 | -33.7% |
| 2022 Rate Hike Selloff | Jan - Oct 2022 | -25.2% |
| Dot-Com Bust | Mar 2000 - Oct 2002 | -49.1% |
| 2010 Flash Crash | May 6, 2010 | -6.9% |

**Why it matters:** Shows how your current portfolio would have performed in past crises, adjusted for each holding's sensitivity to the market.

---

## Technical Indicators (per holding)

| Indicator | Formula | Signal |
|-----------|---------|--------|
| SMA-20 | 20-day simple moving average | Short-term trend |
| SMA-50 | 50-day simple moving average | Medium-term trend |
| RSI-14 | 14-day relative strength index | Overbought (>70) / Oversold (<30) |

Displayed as overlays on interactive candlestick charts (Plotly.js).

---

## Data Sources

| Source | Data | Authentication |
|--------|------|----------------|
| **yfinance** | Stock/crypto prices, OHLCV, options chains, news | None (free) |
| **FRED API** | Fed Funds Rate, CPI, Unemployment, Treasury 10Y, S&P 500 | API key (free) |
| **SEC EDGAR** | Company filings (10-K, 10-Q) | User-Agent string |
| **FinGPT (Colab)** | Sentiment analysis, headline classification, insights | HuggingFace token + ngrok |

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Backend + model server status |
| `/api/quote/{symbol}` | GET | Real-time quote |
| `/api/daily/{symbol}` | GET | Daily OHLCV data |
| `/api/news` | GET | Financial news for tickers |
| `/api/macro` | GET | FRED macro indicators |
| `/api/filings/{ticker}` | GET | SEC EDGAR filings |
| `/api/options/{symbol}` | GET | Options chain (calls/puts) |
| `/api/portfolio/analyze` | POST | Full portfolio analysis |
| `/api/model/analyze` | POST | Direct FinGPT access |
| `/api/cache/clear` | POST | Clear data cache |

---

## Setup

### 1. Clone and Install

```bash
git clone https://github.com/YOUR_USERNAME/FINGPT.git
cd FINGPT
pip install -r requirements.txt
```

Dependencies: `fastapi`, `uvicorn`, `httpx`, `python-dotenv`, `pandas`, `numpy`, `yfinance`, `scipy`, `PyPortfolioOpt`

### 2. Configure API Keys

```bash
cp config/.env.example config/.env
```

Edit `config/.env`:

```ini
FRED_API_KEY=your_fred_key_here          # https://fred.stlouisfed.org/docs/api/api_key.html
SEC_USER_AGENT=YourName your@email.edu   # Required by SEC fair access policy
HF_TOKEN=hf_xxxx                         # https://huggingface.co/settings/tokens
NGROK_AUTH_TOKEN=xxxx                     # https://dashboard.ngrok.com/signup
COLAB_MODEL_URL=http://localhost:5000     # Updated after running Colab notebook
```

`config/.env` is in `.gitignore` and will never be pushed.

### 3. Start the Backend

```bash
python backend/app.py
```

Open http://localhost:8000 in your browser. All quantitative analytics work immediately.

### 4. (Optional) Enable AI Features

1. Open `colab/fingpt_server.ipynb` in Google Colab
2. Set runtime to **T4 GPU**
3. Add `HF_TOKEN` and `NGROK_AUTH_TOKEN` as Colab secrets
4. Run all cells. Copy the ngrok URL into `config/.env` as `COLAB_MODEL_URL`
5. The dashboard status indicator will turn green when connected

---

## Supported Assets

- **Stocks** — Enter ticker symbols directly: `AAPL`, `MSFT`, `GOOGL`, `NVDA`
- **Crypto** — Enter shorthand: `BTC`, `ETH`, `SOL` (auto-mapped to `BTC-USD` format, uses 365-day annualization)
- **Options** — View options chains (calls/puts, IV, volume, OI) for any stock holding after analysis

---

## Dashboard Sections

| Section | Description |
|---------|-------------|
| **Your Portfolio** | Input holdings (symbol, shares, avg cost) |
| **Portfolio Summary** | Total value, gain/loss, volatility, Sharpe, Sortino, Beta, Alpha, diversification |
| **AI Insight** | FinGPT-generated portfolio commentary (requires Colab) |
| **Holdings Detail** | Per-stock metrics table with CSV/JSON export |
| **Price Charts** | Interactive candlestick charts with SMA-20/SMA-50 overlays per holding |
| **Monte Carlo VaR** | 10,000-path simulation with VaR/CVaR risk cards, return histogram, fan chart |
| **Efficient Frontier** | Markowitz optimization with current vs. optimal allocation comparison |
| **Correlation Matrix** | Pairwise correlation heatmap with diversification interpretation |
| **Stress Testing** | Beta-adjusted losses under 5 historical crises |
| **Options Chain** | Calls/puts with strike, bid/ask, IV, volume, open interest |
| **Allocation** | Doughnut chart of portfolio weights |
| **Macro Environment** | Live FRED data (Fed Funds Rate, CPI, unemployment, Treasury 10Y, S&P 500) |
| **News & Sentiment** | Headlines with FinGPT sentiment badges (when AI is enabled) |

Each section has an **info button** (i) that opens an educational explanation of the feature, the methodology, and why it matters.

---

## Project Structure

```
fingpt-portfolio/
├── config/
│   ├── .env.example          # Template with placeholder keys
│   └── .env                  # Your secrets (git-ignored)
├── colab/
│   └── fingpt_server.ipynb   # Run on Google Colab with T4 GPU
├── backend/
│   ├── app.py                # FastAPI server, routes, orchestration
│   ├── advanced_analytics.py # Monte Carlo, Efficient Frontier, Correlation, Stress Test
│   ├── cache.py              # In-memory TTL cache (prices 1hr, quotes 5min, macro 4hr)
│   ├── data_fetcher.py       # yfinance, FRED API, SEC EDGAR clients
│   ├── model_client.py       # Async bridge to FinGPT Colab server
│   └── portfolio.py          # Core analytics: Sharpe, Sortino, Beta, Alpha, Treynor, Calmar
├── frontend/
│   └── static/
│       └── index.html        # Single-page dashboard (Plotly.js + Chart.js)
├── requirements.txt
├── .gitignore
├── LICENSE
└── README.md
```

---

## Version History

| Version | Author | Changes |
|---------|--------|---------|
| **v3** | Askar Kassimov | Core platform: FastAPI backend, yfinance/FRED/SEC data fetching, portfolio analytics (Sharpe, volatility, max drawdown, diversification), FinGPT Colab integration, frontend dashboard with allocation chart, news, macro indicators, options chain |
| **v4** | Shihan Mahfuz | Monte Carlo VaR/CVaR (10K simulations), Markowitz Efficient Frontier (PyPortfolioOpt), Correlation Matrix heatmap, Historical Stress Testing (5 crises), Sortino/Calmar/Beta/Alpha/Treynor ratios, interactive candlestick charts with SMA overlays, SPY benchmark integration, frontend redesign with educational info modals, in-memory caching system |

---

## License

MIT
