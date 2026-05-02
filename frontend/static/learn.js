/**
 * Veris Learning Mode — Gamified financial education with tool unlocking.
 * 9 stages, each with lessons → quiz → unlock ceremony.
 * Tools start locked, progressively unlock as users learn.
 */

// ── Stage Definitions ────────────────────────────────────
const STAGES = [
  // Stage 1: The Trader's Desk (unlocked by default)
  {
    id: 1, name: "The Trader's Desk", icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>',
    desc: "Your starting toolkit — add stocks, view prices, read the news.",
    xpReward: 0,
    lessons: [],
    quiz: [],
    unlocks: {
      panels: ['sectionSummary', 'sectionNews', 'candlePanel'],
      navItems: ['Summary', 'News', 'Charts'],
      holdingsCols: ['symbol', 'price', 'value', 'priceRet'],
      sections: [],
    },
  },
  // Stage 2: Reading the Tape
  {
    id: 2, name: "Reading the Tape", icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>',
    desc: "Understand what your portfolio numbers actually mean.",
    unlockPreview: "Unlocks: Full Holdings Detail (16 columns), SMA overlays on charts, Intraday Tape, Macro Environment, Allocation pie chart, AI Insight",
    xpReward: 150,
    lessons: [
      { type: 'concept', title: 'Price Return vs Total Return', body: 'Your AAPL might show +2151%. But that\'s <b>price return</b> only. <b>Total return</b> includes dividends reinvested. Over 20 years, dividends can account for 40%+ of total equity returns. Always check both.<br><br><b>After this lesson:</b> You\'ll see both Price Return AND Total Return columns in your Holdings table, plus the Dividends column.', video: 'https://www.youtube.com/watch?v=h_BJ7sf1lks' },
      { type: 'concept', title: 'Volatility as a Number', body: 'Annualized volatility measures how much a stock\'s price swings in a year. AAPL at 22.8% vol means its price typically moves within ±22.8% of its mean. NFLX at 38.3% is almost twice as volatile — more risk, but also more opportunity.<br><br><b>After this lesson:</b> The Volatility, Sharpe, and Sortino metrics will unlock in your Portfolio Summary — three of the most important numbers in finance.', video: 'https://www.youtube.com/watch?v=3_jjS3x3oC0' },
      { type: 'concept', title: 'SMA 20 vs SMA 50', body: 'The Simple Moving Average smooths price noise. <b>SMA 20</b> (short-term trend) crossing above <b>SMA 50</b> (medium-term) is a <b>"golden cross"</b> — a bullish signal. The reverse is a <b>"death cross."</b> These are the most-watched indicators on Wall Street.<br><br><b>After this lesson:</b> Your Price Charts will show SMA 20 and SMA 50 overlay lines, and you\'ll get the Intraday Tape for minute-by-minute price action.', video: 'https://www.youtube.com/watch?v=JLtrI_J5N3I' },
      { type: 'concept', title: 'RSI — Overbought or Oversold?', body: 'RSI (Relative Strength Index) oscillates 0-100. Above 70 = <span style="color:var(--red)">overbought</span> (price may pull back). Below 30 = <span style="color:var(--green)">oversold</span> (potential bounce). RSI 14 uses 14 periods of Wilder smoothing — the industry standard since 1978.<br><br><b>After this lesson:</b> RSI 14 column appears in your Holdings table for every stock.', video: 'https://www.youtube.com/watch?v=hbcCykbX14U' },
      { type: 'concept', title: 'What is the Sharpe Ratio?', body: 'Think of Sharpe like a <b>restaurant rating adjusted for price</b>. A $100 steak rated 4 stars is not as impressive as a $10 burger rated 4 stars. Sharpe does the same for investments: it divides your return (above the risk-free rate) by the volatility you took to get it.<br><br><b>How to read it:</b><br>\u2022 Above 1.0 = good risk-adjusted return<br>\u2022 Above 2.0 = excellent<br>\u2022 Below 0 = you lost money, or earned less than treasury bills<br>\u2022 Negative Sharpe = a savings account would have beaten you<br><br><b>Formula in words:</b> (Portfolio return minus risk-free rate) divided by portfolio volatility.<br><br><b>After this lesson:</b> The Sharpe ratio metric card unlocks in your Portfolio Summary.', video: 'https://www.youtube.com/watch?v=Nw2e_GQG2sY' },
      { type: 'concept', title: 'What is the Sortino Ratio?', body: 'Sortino is <b>Sharpe\'s smarter cousin</b>. Here\'s the problem with Sharpe: it penalizes ALL volatility equally. But if your portfolio goes UP 5% in a day, that\'s GOOD volatility! Why punish that?<br><br>Sortino fixes this by only counting <b>downside volatility</b> (days you lost money). Same formula as Sharpe but the denominator only uses negative returns.<br><br><b>How to read it:</b><br>\u2022 Higher = better<br>\u2022 Sortino is always >= Sharpe (same numerator, smaller denominator)<br>\u2022 If Sortino is MUCH higher than Sharpe, your upside vol is strong<br><br><b>After this lesson:</b> The Sortino ratio metric card unlocks in your Portfolio Summary.', video: 'https://www.youtube.com/watch?v=741I3Oe1qDU' },
      { type: 'concept', title: 'What is Max Drawdown?', body: 'Imagine your portfolio as a roller coaster. Max drawdown is the <b>biggest drop from the highest peak to the lowest valley</b> before it recovered.<br><br>Example: Portfolio goes $10,000 \u2192 $12,000 \u2192 $8,400 \u2192 $11,000. The max drawdown is from $12,000 to $8,400 = <span style="color:var(--red)">-30%</span>.<br><br><b>How to read it:</b><br>\u2022 -10% = mild (normal market correction)<br>\u2022 -20% = significant (bear market territory)<br>\u2022 -50%+ = devastating (2008 crisis level)<br><br>Max drawdown answers: "What was the worst ride down?" Even if you recovered, could you have stomached that drop?<br><br><b>After this lesson:</b> Max Drawdown column unlocks in your Holdings table.', video: 'https://www.youtube.com/watch?v=3_jjS3x3oC0' },
      { type: 'concept', title: 'The Macro Environment', body: 'Three numbers move ALL markets:<br>• <b>Fed Funds Rate</b> — cost of borrowing<br>• <b>CPI</b> — inflation measure<br>• <b>10-Year Treasury</b> — the "risk-free" rate<br><br>When the Fed raises rates, stocks usually fall because future earnings are worth less today. Understanding macro is essential for timing and context.<br><br><b>After this lesson:</b> The Macro Environment panel unlocks with live FRED data, plus the Allocation pie chart and AI Insight panel.', video: 'https://www.youtube.com/watch?v=PHe0bXAIuk0' },
      { type: 'concept', title: 'Reading Financial News Like a Pro', body: 'Not all news moves markets equally. Here is how to read financial news:<br><br><b>1. Earnings reports</b> — The most market-moving news. Revenue, EPS, and guidance drive stock prices. "Beat expectations" = stock goes up (usually).<br><br><b>2. Fed announcements</b> — Rate decisions affect EVERY stock. "Dovish" (likely to cut rates) = bullish. "Hawkish" (likely to raise) = bearish.<br><br><b>3. Analyst upgrades/downgrades</b> — When Goldman says "Buy AAPL," the stock moves. When they downgrade, it drops.<br><br><b>4. Macro data releases</b> — CPI (inflation), jobs report, GDP. These set the tone for the whole market.<br><br><b>5. Sentiment vs. Substance</b> — Headlines designed to generate clicks. Look for: actual numbers, not opinions. Compare "AAPL misses revenue by 2%" (substance) vs "AAPL is in trouble" (sentiment).<br><br><b>After this lesson:</b> The News and Sentiment panel unlocks. Learn to distinguish signal from noise in financial media.', video: 'https://www.youtube.com/watch?v=PHe0bXAIuk0' },
    ],
    quiz: [
      { q: 'Your portfolio cost $4,100. Current value is $54,955. What is your approximate price return?', options: ['134%', '1,240%', '13.4%', '50,855%'], correct: 1, explanation: 'Price return = (54,955 - 4,100) / 4,100 = 1,240%. This is the gain relative to your cost basis.' },
      { q: 'NFLX has 38.3% annualized vol vs AAPL\'s 22.8%. Which is riskier on this metric?', options: ['AAPL', 'NFLX', 'They\'re equal', 'Can\'t determine'], correct: 1, explanation: 'Higher volatility = higher risk. NFLX at 38.3% swings nearly twice as much as AAPL\'s 22.8%.' },
      { q: 'An RSI of 75 signals what?', options: ['Oversold', 'Overbought', 'Neutral', 'Bullish momentum'], correct: 1, explanation: 'RSI above 70 is overbought — the price has risen fast and may be due for a pullback.' },
      { q: 'Which news event typically has the BIGGEST impact on a single stock price?', options: ['Fed rate decision', 'Quarterly earnings report', 'Analyst opinion piece', 'Industry conference'], correct: 1, explanation: 'Earnings reports are the single biggest mover for individual stocks. Revenue, EPS, and forward guidance can swing prices 5-20% in a day. Fed decisions affect the whole market, but earnings are stock-specific.' },
      { q: 'A portfolio has Sharpe ratio of -0.5. What does this mean?', options: ['The portfolio is doing great', 'A savings account would have beaten it', 'It has low volatility', 'It\'s perfectly hedged'], correct: 1, explanation: 'Negative Sharpe means the portfolio earned LESS than the risk-free rate (treasury bills). A savings account literally would have performed better.' },
      { q: 'Sortino ratio only penalizes which type of volatility?', options: ['All volatility equally', 'Upside volatility only', 'Downside volatility only', 'Market volatility only'], correct: 2, explanation: 'Sortino only counts downside volatility (days you lost money). Upside volatility is good — why punish profits? This makes Sortino a smarter risk metric than Sharpe.' },
      { q: 'Your portfolio went from $10,000 to $15,000, then dropped to $9,000, then recovered to $12,000. What is the max drawdown?', options: ['-10%', '-40%', '-25%', '-60%'], correct: 1, explanation: 'Max drawdown = worst peak-to-trough drop. Peak was $15,000, trough was $9,000. Drop = ($15,000 - $9,000) / $15,000 = -40%. The recovery to $12,000 doesn\'t matter — the drawdown already happened.' },
    ],
    unlocks: {
      panels: ['sectionHoldings', 'intradayPanel', 'sectionAllocation', 'sectionMacro', 'sectionAI', 'rebalancePanel', 'newsDigestPanel'],
      navItems: ['Holdings', 'Allocation', 'Macro', 'AI Insight', 'Rebalance'],
      holdingsCols: ['vol', 'sharpe', 'sortino', 'beta', 'alpha', 'maxDD', 'sma20', 'sma50', 'rsi14', 'tax'],
      sections: [],
    },
  },
  // Stage 3: Understanding Risk
  {
    id: 3, name: "Understanding Risk", icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
    desc: "How much could you actually lose?",
    unlockPreview: "Unlocks: Monte Carlo VaR (10,000 simulations), CVaR, Regime Aware Risk Engine, Event Risk Calendar, Data Quality Dashboard",
    xpReward: 200,
    lessons: [
      { type: 'concept', title: 'The Loss Distribution', body: 'Your portfolio doesn\'t gain or lose the same amount every day. Returns follow a <b>distribution</b> — mostly small moves, but occasionally huge ones. The left tail (big losses) is what risk management focuses on.<br><br><b>Why this matters:</b> The VaR panel you\'re about to unlock shows exactly where YOUR portfolio sits on this distribution.', video: 'https://www.youtube.com/watch?v=2SMkbMDypXI' },
      { type: 'concept', title: 'VaR 95% Explained', body: 'Value at Risk at 95% confidence says: <b>"95% of the time, your 30-day loss won\'t exceed X%."</b> If your VaR is -12.55%, there\'s only a 5% chance you\'ll lose more than 12.55% in a month. But that 5% tail can be devastating.<br><br><b>After this lesson:</b> You\'ll see YOUR portfolio\'s exact VaR number calculated from 10,000 Monte Carlo simulations.', video: 'https://www.youtube.com/watch?v=Qo4Dw7AfEN8' },
      { type: 'concept', title: 'CVaR / Expected Shortfall', body: 'CVaR answers: <b>"When losses DO exceed VaR, how bad is it on average?"</b> If VaR 95% = -12.55% and CVaR = -16.03%, the average loss in the worst 5% of scenarios is 16%. CVaR is always worse than VaR — and it\'s what banks actually use for risk capital.', video: 'https://www.youtube.com/watch?v=L_EZQhLrwAU' },
      { type: 'concept', title: 'Monte Carlo Simulation', body: 'We run <b>10,000 simulated paths</b> of your portfolio using Student-t distributions (which capture fat tails better than Normal) and <b>Cholesky decomposition</b> (which preserves correlations between stocks). The fan chart shows percentile bands of possible outcomes.<br><br><b>After this lesson:</b> The full Monte Carlo fan chart unlocks with VaR, CVaR, and simulated path visualization.', video: 'https://www.youtube.com/watch?v=psOYFdx838E' },
      { type: 'concept', title: 'Regime Detection', body: 'Markets operate in regimes:<br>• <span style="color:var(--green)">LOW</span> vol (&lt;12%)<br>• <span style="color:var(--muted)">NORMAL</span> (12-20%)<br>• <span style="color:var(--yellow)">ELEVATED</span> (20-30%)<br>• <span style="color:var(--red)">CRISIS</span> (&gt;30%)<br><br>The current regime affects your risk estimates — VaR calculated in a crisis regime is much worse than in a calm regime.<br><br><b>After this lesson:</b> The Regime Aware Risk Engine unlocks, showing the current regime and regime-conditional VaR.', video: 'https://www.youtube.com/watch?v=LwkGF6FZKzs' },
      { type: 'concept', title: 'Event Risk', body: 'Earnings announcements are the biggest source of overnight <b>gap risk</b>. A stock can move 5-10% on earnings day. Knowing when earnings are coming and how the stock has historically reacted lets you size positions appropriately.<br><br><b>After this lesson:</b> The Event Risk Calendar and Data Quality Dashboard unlock.', video: 'https://www.youtube.com/watch?v=2SMkbMDypXI' },
    ],
    quiz: [
      { q: 'VaR 95% = -12.55% means what?', options: ['You\'ll lose exactly 12.55%', '95% chance loss won\'t exceed 12.55%', 'Your max possible loss is 12.55%', '5% of days you gain 12.55%'], correct: 1, explanation: 'VaR 95% is a confidence threshold: 95% of the time, your loss stays within this bound. It\'s NOT the maximum possible loss.' },
      { q: 'Your CVaR is -16.03%. Is that better or worse than VaR 95% = -12.55%?', options: ['Better (less risk)', 'Worse (more risk)', 'They measure the same thing', 'Depends on the regime'], correct: 1, explanation: 'CVaR is always worse (more negative) than VaR because it averages the tail losses BEYOND VaR. -16% average in the worst 5% vs -12.55% threshold.' },
      { q: 'The current regime is ELEVATED (25% vol). What does this mean for VaR?', options: ['VaR is more accurate', 'VaR understates risk', 'VaR overstates risk', 'VaR is unaffected'], correct: 1, explanation: 'In elevated volatility regimes, unconditional VaR (calculated from all historical data) understates your real risk because it averages calm and turbulent periods.' },
      { q: 'Order from least to most risk: Expected Return, VaR 95%, VaR 99%, CVaR', options: ['Expected Return < VaR95 < VaR99 < CVaR', 'CVaR < VaR99 < VaR95 < Expected Return', 'VaR95 < CVaR < VaR99 < Expected Return', 'Expected Return < CVaR < VaR99 < VaR95'], correct: 0, explanation: 'Expected return is your average (positive). VaR 95% is a loss threshold, VaR 99% is stricter, and CVaR is the worst — it\'s the average of the tail beyond VaR.' },
    ],
    unlocks: {
      panels: ['monteCarloPanel', 'regimePanel', 'eventsPanel', 'qualityPanel'],
      navItems: ['VaR', 'Regime', 'Events', 'Quality'],
      holdingsCols: [],
      sections: [],
    },
  },
  // Stage 4: Building a Better Portfolio
  {
    id: 4, name: "Building a Better Portfolio", icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19.439 7.85c-.049.322.059.648.289.878l1.568 1.568c.47.47.706 1.087.706 1.704s-.235 1.233-.706 1.704l-1.611 1.611a.98.98 0 01-.837.276c-.47-.07-.802-.48-.968-.925a2.501 2.501 0 10-3.214 3.214c.446.166.855.497.925.968a.979.979 0 01-.276.837l-1.61 1.611a2.404 2.404 0 01-1.705.707 2.402 2.402 0 01-1.704-.706l-1.568-1.568a1.026 1.026 0 00-.877-.29c-.493.074-.84.504-1.02.968a2.5 2.5 0 11-3.237-3.237c.464-.18.894-.527.967-1.02a1.026 1.026 0 00-.289-.877l-1.568-1.568A2.402 2.402 0 011.998 12c0-.617.236-1.234.706-1.704L4.23 8.77c.24-.24.581-.353.917-.303.515.077.877.528 1.073 1.01a2.5 2.5 0 103.259-3.259c-.482-.196-.933-.558-1.01-1.073-.05-.336.062-.676.303-.917l1.525-1.525A2.402 2.402 0 0112 1.998c.617 0 1.234.236 1.704.706l1.568 1.568c.23.23.556.338.877.29.493-.074.84-.504 1.02-.968a2.5 2.5 0 113.237 3.237c-.464.18-.894.527-.967 1.02z"/></svg>',
    desc: "Correlation, diversification, and the efficient frontier.",
    unlockPreview: "Unlocks: Correlation Matrix heatmap, Efficient Frontier optimizer, What-If Trade Simulator, HHI/Effective N/Div Ratio metrics, Legendary Investors panel",
    xpReward: 200,
    lessons: [
      { type: 'concept', title: 'Correlation Explained', body: 'Correlation measures how two assets move together:<br>• <b>+1</b> = perfectly in sync (no diversification)<br>• <b>0</b> = independent (good diversification)<br>• <b>-1</b> = perfectly opposite (perfect hedge)<br><br>AAPL and MSFT might have 0.7 correlation (tech moves together). AAPL and Gold might be 0.05 (nearly independent).<br><br><b>After this lesson:</b> The Correlation Matrix heatmap unlocks — see exactly how correlated YOUR holdings are.', video: 'https://www.youtube.com/watch?v=oUVbe3PYjp8' },
      { type: 'concept', title: 'Why Correlation Reduces Risk', body: 'Portfolio volatility isn\'t just the weighted average of individual vols. The <b>covariance term</b> means that when assets have low correlation, their ups and downs partially cancel out. A 2-stock portfolio with correlation 0 has ~30% less risk than either stock alone.<br><br>This is the mathematical foundation of modern portfolio theory — and why diversification is called the only "free lunch" in finance.', video: 'https://www.youtube.com/watch?v=K7sT1IJepmI' },
      { type: 'concept', title: 'The Efficient Frontier', body: 'The frontier is a curve showing the <b>best possible return for each level of risk</b>. Points below the frontier are suboptimal. Your portfolio likely sits below it — the optimizer shows how to get ON it by rebalancing.<br><br><b>After this lesson:</b> The Efficient Frontier panel unlocks with Markowitz optimization + Ledoit-Wolf shrinkage. See your portfolio dot vs the optimal portfolio.', video: 'https://www.youtube.com/watch?v=yWz5Kqn_D4c' },
      { type: 'concept', title: 'What-If Trading', body: 'Before you buy or sell, <b>simulate it</b>. The What-If tool shows how adding NVDA changes your Sharpe ratio, volatility, and beta — before you commit real money. Think of it as a flight simulator for your portfolio.<br><br><b>After this lesson:</b> The What-If Trade Simulator unlocks — test any trade before executing it.', video: 'https://www.youtube.com/watch?v=yWz5Kqn_D4c' },
      { type: 'concept', title: 'What is HHI (Concentration Index)?', body: 'Imagine a <b>pizza</b>. If one person eats 95% of it, that\'s extremely concentrated. If 10 people each eat 10%, that\'s evenly spread.<br><br>HHI (Herfindahl-Hirschman Index) works the same way for your portfolio. It squares each stock\'s weight and adds them up.<br><br><b>How to read it:</b><br>\u2022 HHI = 1.0 \u2192 you own ONE stock (max concentration)<br>\u2022 HHI = 0.5 \u2192 like having 2 equal stocks<br>\u2022 HHI = 0.1 \u2192 like having 10 equal stocks (well diversified)<br>\u2022 HHI = 0.04 \u2192 like having 25 equal stocks (very diversified)<br><br>Lower HHI = more diversified = less single-stock risk.<br><br><b>After this lesson:</b> HHI metric card unlocks in your Portfolio Summary.', video: 'https://www.youtube.com/watch?v=vc8yC7JCKIo' },
      { type: 'concept', title: 'What is Effective N?', body: 'Effective N translates HHI into something intuitive: <b>"How many equal-sized stocks do I effectively have?"</b><br><br>Formula: Effective N = 1 / HHI<br><br><b>Examples:</b><br>\u2022 HHI = 1.0 \u2192 Effective N = 1 (one-stock portfolio)<br>\u2022 HHI = 0.5 \u2192 Effective N = 2<br>\u2022 HHI = 0.1 \u2192 Effective N = 10<br><br>You might hold 10 stocks, but if 90% is in one name, your Effective N might be 1.2 \u2014 you basically have a one-stock portfolio with decoration.<br><br><b>After this lesson:</b> Effective N metric card unlocks in your Portfolio Summary.', video: 'https://www.youtube.com/watch?v=vc8yC7JCKIo' },
      { type: 'concept', title: 'What is the Diversification Ratio?', body: 'The diversification ratio answers: <b>"Are my stock correlations actually helping me?"</b><br><br>It compares two numbers:<br>\u2022 Numerator: weighted average of each stock\'s individual volatility<br>\u2022 Denominator: the actual portfolio volatility<br><br>If Div Ratio > 1.0, your portfolio is less volatile than a naive average \u2014 correlations are <span style="color:var(--green)">helping you</span>. The higher above 1.0, the more diversification benefit you\'re getting.<br><br><b>How to read it:</b><br>\u2022 1.0 = no diversification benefit (perfect correlation)<br>\u2022 1.2 = modest benefit<br>\u2022 1.5+ = strong diversification working for you<br><br><b>After this lesson:</b> Diversification Ratio metric card unlocks in your Portfolio Summary.', video: 'https://www.youtube.com/watch?v=a7EehSVfct4' },
      { type: 'concept', title: 'HHI Concentration', body: 'The <b>Herfindahl-Hirschman Index</b> measures portfolio concentration:<br>• HHI = 1.0 → one stock (maximum concentration)<br>• HHI = 0.1 → 10 equal stocks (well diversified)<br>• <b>Effective N</b> = 1/HHI → equivalent number of equal-weight positions<br><br><b>After this lesson:</b> HHI, Effective N, and Diversification Ratio metrics unlock in your Summary, plus the Legendary Investors panel showing which 13F filers hold your stocks.', video: 'https://www.youtube.com/watch?v=oUVbe3PYjp8' },
    ],
    quiz: [
      { q: 'Two assets with correlation = 1.0 provide what level of diversification?', options: ['Maximum diversification', 'Zero diversification', 'Moderate diversification', 'Negative diversification'], correct: 1, explanation: 'Correlation +1.0 means the assets move in perfect lockstep. Adding another identical mover doesn\'t reduce risk at all — zero diversification benefit.' },
      { q: 'Your portfolio\'s HHI is 0.967. Is this good diversification?', options: ['Excellent', 'Good', 'Poor', 'Average'], correct: 2, explanation: 'HHI of 0.967 is extremely concentrated — almost all your money is in one stock. Effective N = 1/0.967 ≈ 1.03, meaning you essentially have a one-stock portfolio.' },
      { q: 'Moving correlation from -1 to +1: what happens to 2-stock portfolio vol?', options: ['Vol stays constant', 'Vol decreases to zero', 'Vol increases monotonically', 'Vol first decreases then increases'], correct: 2, explanation: 'At correlation -1, portfolio vol can reach zero (perfect hedge). As correlation increases toward +1, portfolio vol increases until it equals the weighted average of individual vols.' },
    ],
    unlocks: {
      panels: ['frontierPanel', 'corrPanel', 'whatifPanel', 'holdersPanel'],
      navItems: ['Frontier', 'Correlation', 'What If', 'Investors'],
      holdingsCols: [],
      sections: [],
    },
  },
  // Stage 5: When Markets Break
  {
    id: 5, name: "When Markets Break", icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
    desc: "Stress testing, factor models, and crisis preparation.",
    unlockPreview: "Unlocks: Stress Testing (5 crises + reverse), Factor Attribution (CAPM), Calmar/Treynor/Info Ratio/Beta/Alpha metrics",
    xpReward: 250,
    lessons: [
      { type: 'concept', title: 'What is Beta?', body: 'Think of beta as a <b>volume knob</b> for market movements. If the market (SPY) goes up 10%:<br><br>\u2022 Beta 1.0 = your portfolio goes up 10% (moves with market)<br>\u2022 Beta 1.5 = your portfolio goes up 15% (amplified)<br>\u2022 Beta 0.5 = your portfolio goes up 5% (dampened)<br>\u2022 Beta 0 = your portfolio doesn\'t care what the market does<br><br>But beta works both ways! In a crash, beta 1.5 means you lose 50% MORE than the market.<br><br><b>How to read YOUR beta:</b><br>\u2022 < 0.8 = defensive (less market exposure)<br>\u2022 0.8-1.2 = market-like<br>\u2022 > 1.2 = aggressive (amplified market risk)<br><br><b>After this lesson:</b> Beta vs SPY metric card unlocks in your Portfolio Summary.', video: 'https://www.youtube.com/watch?v=fFK6HZ7EEG0' },
      { type: 'concept', title: 'What is Alpha (Jensen\'s Alpha)?', body: 'Alpha is your <b>stock-picking report card</b>. It answers: "Did your picks add value beyond what the market gave you?"<br><br>Formula in words: Your actual return MINUS what you SHOULD have earned based on your beta and the market\'s return.<br><br><b>How to read it:</b><br>\u2022 Alpha > 0 = your picks BEAT the market (after adjusting for risk)<br>\u2022 Alpha = 0 = you matched what beta predicted<br>\u2022 Alpha < 0 = an index fund would have done better<br><br>If your alpha is -20%, it means your stock selections COST you 20% compared to just buying SPY. This is why 90% of active fund managers underperform \u2014 generating positive alpha is extremely hard.<br><br><b>After this lesson:</b> Alpha metric card unlocks in your Portfolio Summary.', video: 'https://www.youtube.com/watch?v=fo0Ba9-GCts' },
      { type: 'concept', title: 'What is the Calmar Ratio?', body: 'Calmar asks: <b>"Is the ride worth the pain?"</b><br><br>It divides your annual return by your max drawdown. Think of it like a theme park ride \u2014 a ride with great views (returns) but terrifying drops (drawdowns) might not be worth it.<br><br><b>Examples:</b><br>\u2022 20% return / -10% drawdown = Calmar 2.0 (great ride)<br>\u2022 20% return / -40% drawdown = Calmar 0.5 (painful)<br>\u2022 5% return / -30% drawdown = Calmar 0.17 (terrible)<br><br><b>How to read it:</b><br>\u2022 Above 1.0 = return exceeds worst drop (comfortable)<br>\u2022 Above 3.0 = excellent risk-adjusted<br>\u2022 Below 0.5 = the drops are brutal relative to returns<br><br><b>After this lesson:</b> Calmar ratio metric card unlocks in your Portfolio Summary.', video: 'https://www.youtube.com/watch?v=siuy26Rb3AI' },
      { type: 'concept', title: 'What is the Treynor Ratio?', body: 'Treynor is <b>Sharpe\'s twin, but for market risk only</b>.<br><br>While Sharpe divides return by TOTAL volatility, Treynor divides by BETA. This means Treynor only cares about systematic (market) risk, not company-specific risk.<br><br><b>When to use Treynor over Sharpe:</b><br>\u2022 Use Sharpe for your whole portfolio<br>\u2022 Use Treynor to compare individual funds or stocks<br>\u2022 Treynor is better for well-diversified portfolios where idiosyncratic risk is low<br><br><b>How to read it:</b> Higher = better. Negative = bad (losing money or high risk for low return).<br><br><b>After this lesson:</b> Treynor ratio metric card unlocks in your Portfolio Summary.', video: 'https://www.youtube.com/watch?v=wP-L2vQZd7g' },
      { type: 'concept', title: 'What is the Information Ratio?', body: 'The Information Ratio answers: <b>"How consistently do you beat the benchmark?"</b><br><br>It\'s like a batting average, but for investing. High IR means you reliably add value. Low IR means your wins and losses are random.<br><br>Formula: (Your return minus benchmark return) divided by tracking error (how much your returns deviate from the benchmark).<br><br><b>How to read it:</b><br>\u2022 IR > 0.5 = good (consistently beating benchmark)<br>\u2022 IR > 1.0 = exceptional (hedge fund territory)<br>\u2022 IR < 0 = consistently underperforming<br>\u2022 IR near 0 = no consistent edge either way<br><br><b>After this lesson:</b> Information Ratio metric card unlocks in your Portfolio Summary.', video: 'https://www.youtube.com/watch?v=h_db4JFFRes' },
      { type: 'concept', title: 'Historical Crises', video: 'https://www.youtube.com/watch?v=LwkGF6FZKzs', body: '2008 Financial Crisis: SPY -38.9%. COVID Crash 2020: SPY -33.7%. Dot-Com Bust 2000: SPY -49.1%. Euro Crisis 2011: SPY -19.4%. These events seemed impossible beforehand. Stress testing asks: "If it happened again, what happens to MY portfolio?"' },
      { type: 'concept', title: 'Beta as Crisis Amplifier', video: 'https://www.youtube.com/watch?v=f_IYuz3YLgY', body: 'Portfolio beta measures sensitivity to the market. Beta 0.91 means: if SPY drops 10%, you drop ~9.1%. In the 2008 crisis (-38.9% SPY), a 0.91 beta portfolio would have lost ~35.4%. Beta amplifies both gains AND losses.' },
      { type: 'concept', title: 'Reverse Stress Test', video: 'https://www.youtube.com/watch?v=2SMkbMDypXI', body: 'Instead of asking "how bad would X crisis be?" — reverse stress testing asks "how much would SPY need to fall to cause a 20% loss in MY portfolio?" At beta 0.91, the answer is: SPY needs to drop 22.1%. This threshold is your early warning level.' },
      { type: 'concept', title: 'CAPM Factor Decomposition', video: 'https://www.youtube.com/watch?v=_RBevTla7pA', body: 'The Capital Asset Pricing Model splits your return into two parts: beta return (what the market gave you) and alpha (your stock-picking skill). Negative alpha means your picks underperformed what simple market exposure would have delivered.' },
      { type: 'concept', title: 'Jensen\'s Alpha', body: 'Alpha = Portfolio Return - [Risk-Free Rate + Beta × (Market Return - Risk-Free Rate)]. Negative alpha means you\'d have been better off in an index fund. Positive alpha is the holy grail — genuine stock-picking skill that beats the market after adjusting for risk.' },
      { type: 'concept', title: 'Information Ratio', video: 'https://www.youtube.com/watch?v=_RBevTla7pA', body: 'IR = Alpha / Tracking Error. It measures how consistently you beat (or underperform) the benchmark. IR > 0.5 is good, > 1.0 is exceptional. Negative IR means you\'re consistently underperforming — a strong signal to consider index investing.' },
    ],
    quiz: [
      { q: 'What does a beta of 1.5 mean for your portfolio?', options: ['50% less volatile than the market', '50% more volatile than the market', 'No relationship to the market', 'Half the market return'], correct: 1, explanation: 'Beta 1.5 means your portfolio amplifies market moves by 50%. If SPY goes up 10%, you go up 15%. If SPY drops 10%, you drop 15%. It\'s a volume knob for market exposure.' },
      { q: 'Your alpha is -15%. What should you consider?', options: ['Buy more stocks', 'Your stock picks are costing you — consider index funds', 'You\'re beating the market', 'Alpha doesn\'t matter'], correct: 1, explanation: 'Negative alpha means your stock selections underperformed what a simple index fund (matching your beta) would have delivered. -15% alpha is significant underperformance.' },
      { q: 'Portfolio beta is 0.91. Market drops 10%. Estimated portfolio drop?', options: ['10%', '9.1%', '0.91%', '19.1%'], correct: 1, explanation: 'Beta × Market Move = 0.91 × 10% = 9.1%. Beta is a linear multiplier of market movements.' },
      { q: 'Alpha = -20.66%. This means:', options: ['Your picks added value', 'Your picks cost you returns vs the market', 'Your portfolio has low risk', 'You beat SPY'], correct: 1, explanation: 'Negative alpha means your stock selections underperformed what the market beta alone would have delivered. You lost 20.66% to stock picking.' },
      { q: 'Which 2008-style stress event would hurt a beta=1.5 portfolio most?', options: ['2008 Crisis (-38.9%)', 'COVID Crash (-33.7%)', 'Dot-Com (-49.1%)', 'Euro Crisis (-19.4%)'], correct: 2, explanation: 'Dot-Com had the largest SPY drop (-49.1%). At beta 1.5: 1.5 × 49.1% = 73.65% loss. Higher beta amplifies the worst scenarios most.' },
      { q: 'Reverse stress: SPY needs to drop 22.1% for your 20% loss. Adding a beta=0.2 asset would make this threshold...', options: ['Go up (more SPY drop needed)', 'Go down (less SPY drop needed)', 'Stay the same', 'Become undefined'], correct: 0, explanation: 'Adding a low-beta asset reduces your overall portfolio beta. Lower beta means SPY needs to fall MORE to cause the same portfolio loss. The threshold goes UP — you\'re more protected.' },
    ],
    unlocks: {
      panels: ['stressPanel', 'factorPanel'],
      navItems: ['Stress', 'Factor'],
      holdingsCols: [],
      sections: [],
    },
  },
  // Stage 6: The Real Cost of Investing
  {
    id: 6, name: "The Real Cost of Investing", icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>',
    desc: "Taxes, tariffs, and the true cost of your positions.",
    unlockPreview: "Unlocks: Tax Liability panel (LTCG calculator + tax-loss harvesting), Tariff Exposure calculator (China COGS impact)",
    xpReward: 200,
    lessons: [
      { type: 'concept', title: 'Capital Gains Tax', video: 'https://www.youtube.com/watch?v=0maGu_QHFjU', body: 'Long-term capital gains (held >1 year) are taxed at 23.8% for high earners. Short-term gains are taxed as ordinary income (up to 37%). This means a $50,000 gain could cost you $11,900 in LTCG tax or $18,500 in short-term tax. Holding period matters enormously.' },
      { type: 'concept', title: 'Tax-Loss Harvesting', video: 'https://www.youtube.com/watch?v=TLFG1_jFQ_Y', body: 'If you have a losing position, you can sell it to "harvest" the loss. This loss offsets your gains, reducing your tax bill. Example: $51,634 gain on AAPL, -$778 loss on NFLX. Harvesting NFLX saves you $185 in taxes. You can immediately buy a similar (not identical) asset to maintain exposure.' },
      { type: 'concept', title: 'After-Tax Returns', video: 'https://www.youtube.com/watch?v=0maGu_QHFjU', body: 'Your AAPL shows +2151% price return. But after 23.8% LTCG tax on the $51,634 gain, you owe $12,289. Your after-tax profit is $39,345 — still great, but 24% less than the headline number. Always think in after-tax terms.' },
      { type: 'concept', title: 'Tariff Exposure', video: 'https://www.youtube.com/watch?v=s7QfCsGqeuw', body: 'AAPL sources ~$87B in goods from China. A 25% tariff with 50% pass-through means AAPL absorbs $10.875B in extra costs. That\'s an 11.57% hit to earnings, which directly impacts the stock price. Trade policy is portfolio risk.' },
      { type: 'concept', title: 'The Full Picture', video: 'https://www.youtube.com/watch?v=0maGu_QHFjU', body: 'The real return on your AAPL position: +2151% price return, minus 23.8% tax on gains, minus potential tariff impact on future earnings. The number you see on your screen is never the number you take home. Professional investors always think after-tax, after-fees, after-friction.' },
    ],
    quiz: [
      { q: 'AAPL has $51,634 unrealized gain. At 23.8% LTCG, tax owed?', options: ['$5,163', '$12,289', '$19,120', '$51,634'], correct: 1, explanation: '$51,634 × 0.238 = $12,288.89 ≈ $12,289. Almost a quarter of your gain goes to taxes.' },
      { q: 'Why harvest a NFLX loss even though the stock is down?', options: ['To buy more NFLX cheaper', 'To offset gains and reduce tax bill', 'Because losses always recover', 'To increase portfolio beta'], correct: 1, explanation: 'Harvesting the loss creates a tax deduction that offsets gains from winners. You save 23.8% × the loss amount in taxes.' },
      { q: 'At 25% tariff, 50% pass-through, $87B China COGS: earnings hit?', options: ['$87B', '$21.75B', '$10.875B', '$43.5B'], correct: 2, explanation: '$87B × 25% tariff = $21.75B cost. At 50% pass-through (half absorbed): $21.75B × 50% = $10.875B earnings hit.' },
    ],
    unlocks: {
      panels: ['taxPanel', 'tariffPanel'],
      navItems: ['Tax', 'Tariff'],
      holdingsCols: [],
      sections: [],
    },
  },
  // Stage 7: Options & Derivatives
  {
    id: 7, name: "Options & Derivatives", icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 3h6M12 3v7l-5.5 8.5a2 2 0 001.7 3h7.6a2 2 0 001.7-3L12 10"/></svg>',
    desc: "Calls, puts, Greeks, and implied volatility.",
    unlockPreview: "Unlocks: Full Options Chain with Greeks (Delta/Gamma/Theta/Vega/IV), IV Skew analysis, Put/Call Ratio",
    xpReward: 300,
    lessons: [
      { type: 'concept', title: 'What is a Call Option?', video: 'https://www.youtube.com/watch?v=EfmTWu2yn5Q', body: 'A call gives you the RIGHT (not obligation) to BUY a stock at a specific price (strike) by a specific date (expiry). AAPL $270 call = you can buy AAPL at $270 no matter how high it goes. If AAPL hits $300, your call is worth at least $30.' },
      { type: 'concept', title: 'What is a Put Option?', video: 'https://www.youtube.com/watch?v=EfmTWu2yn5Q', body: 'A put gives you the RIGHT to SELL at the strike price. It\'s downside protection — insurance for your portfolio. If you own AAPL at $270 and buy a $250 put, your maximum loss is $20 per share no matter how far AAPL falls.' },
      { type: 'concept', title: 'Delta — Price Sensitivity', video: 'https://www.youtube.com/watch?v=MOjFvY9QJiQ', body: 'Delta measures how much an option\'s price moves per $1 move in the stock. Delta 0.50 = the option moves $0.50 for every $1 in the stock. Deep in-the-money calls approach delta 1.0 (moves dollar for dollar with stock). Deep OTM calls have delta near 0.' },
      { type: 'concept', title: 'Gamma — The Curvature', video: 'https://www.youtube.com/watch?v=w3thnpF7UiM', body: 'Gamma is the rate of change of delta. High gamma means delta changes fast — your position\'s risk profile shifts rapidly. Gamma is highest for at-the-money options near expiry. This is why option prices get "jumpy" in the last few days.' },
      { type: 'concept', title: 'Theta — Time Decay', video: 'https://www.youtube.com/watch?v=MOjFvY9QJiQ', body: 'Theta is the daily cost of holding an option. If theta = -$0.27, your option loses $0.27 per day just from time passing. Time decay accelerates as expiry approaches — the last 30 days eat the most value. Sellers love theta; buyers fight it.' },
      { type: 'concept', title: 'Vega — Volatility Sensitivity', video: 'https://www.youtube.com/watch?v=ysQiE-yb9kQ', body: 'Vega measures how much the option price changes per 1% change in implied volatility. High vega = the option is very sensitive to IV changes. Before earnings, IV spikes (people buy protection), inflating option prices. After earnings, IV collapses ("IV crush").' },
      { type: 'concept', title: 'IV Skew — The Fear Gauge', video: 'https://www.youtube.com/watch?v=DvLmayY1S7Q', body: 'When put IV exceeds call IV, it means traders are paying MORE for downside protection than upside bets. A +14pt skew (puts 81.5% IV vs calls 67.5% IV) signals fear in the market. The skew is one of the best sentiment indicators available.' },
    ],
    quiz: [
      { q: 'AAPL call with delta 0.60, AAPL rises $2. Option price change?', options: ['$0.60', '$1.20', '$2.00', '$0.30'], correct: 1, explanation: 'Delta × Stock Move = 0.60 × $2 = $1.20. The option gains $1.20 for every $2 move in the stock.' },
      { q: 'Theta = -$0.271/day. What happens to the option\'s value each day?', options: ['Gains $0.271', 'Loses $0.271', 'Unchanged', 'Depends on the stock'], correct: 1, explanation: 'Negative theta means time decay. The option loses $0.271 per day automatically, even if the stock doesn\'t move.' },
      { q: 'Put/Call ratio OI = 0.83. Market sentiment?', options: ['Strongly bullish', 'Slightly bearish', 'Neutral', 'Slightly bullish — more calls than puts'], correct: 3, explanation: 'Put/Call ratio < 1.0 means more call open interest than puts. More calls = more bullish bets. 0.83 is slightly bullish.' },
      { q: 'IV Skew = +13.97 pts (puts > calls). This signals:', options: ['Greed', 'Fear / downside hedging', 'Bullish momentum', 'No market view'], correct: 1, explanation: 'When put IV exceeds call IV, traders are paying a premium for downside protection. This is a fear signal — the market is pricing in crash risk.' },
    ],
    unlocks: {
      panels: ['optionsPanel'],
      navItems: ['Options'],
      holdingsCols: [],
      sections: [],
    },
  },
  // Stage 8: Prediction Markets
  {
    id: 8, name: "Prediction Markets", icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>',
    desc: "Probability, calibration, and betting markets.",
    unlockPreview: "Unlocks: Polymarket + Kalshi browser, My Bets portfolio tracker, Calibration Curve (500 resolved markets), Personal Accuracy tracker",
    xpReward: 200,
    lessons: [
      { type: 'concept', title: 'What Are Prediction Markets?', video: 'https://www.youtube.com/watch?v=lWaOiSHf6L8', body: 'Prediction markets are exchanges where you buy contracts that pay $1 if an event happens and $0 if it doesn\'t. A contract trading at $0.54 implies the market assigns 54% probability to that event. Real money on the line means better forecasts than polls or pundits.' },
      { type: 'concept', title: 'Reading Probabilities', video: 'https://www.youtube.com/watch?v=i5Ckbzhpn9k', body: '"Yes 54%" on a ceasefire market means: the crowd, backed by real money, thinks there\'s a 54% chance of ceasefire. You can buy Yes at $0.54 — if it happens, you profit $0.46. If not, you lose $0.54. The price IS the probability.' },
      { type: 'concept', title: 'Are Markets Calibrated?', video: 'https://www.youtube.com/watch?v=h6UQB9lrcmc', body: 'A perfectly calibrated market means 70% events resolve Yes 70% of the time. We analyzed 500 resolved Polymarket markets and found a Brier score of 0.06 — that\'s excellent. Markets aren\'t perfect, but they\'re among the best forecasting tools we have.' },
      { type: 'concept', title: 'Expected Value', video: 'https://www.youtube.com/watch?v=YFGzYvf7BzQ', body: 'If a contract trades at $0.50 and you think the true probability is 60%, your EV = 0.60 × $0.50 - 0.40 × $0.50 = +$0.10 per contract. Positive EV means the bet is profitable on average over many repetitions. But you need to be RIGHT about your 60% estimate.' },
      { type: 'concept', title: 'The Brier Score', video: 'https://www.youtube.com/watch?v=h6UQB9lrcmc', body: 'Brier score = mean of (forecast - outcome)². Perfect score = 0 (you predicted exactly right every time). Coin flip = 0.25. Random guessing = 0.5. Polymarket\'s 0.06 means it\'s very well calibrated. You can track YOUR personal Brier score to measure if you beat the market.' },
    ],
    quiz: [
      { q: 'A contract trades at $0.54 Yes. You believe true probability is 70%. What\'s your EV?', options: ['+$0.16', '+$0.46', '-$0.16', '+$0.70'], correct: 0, explanation: 'EV = P(yes) × payout - P(no) × cost = 0.70 × $0.46 - 0.30 × $0.54 = $0.322 - $0.162 = +$0.16 per contract.' },
      { q: 'Brier score of 0 means:', options: ['Always wrong', 'Always right / perfect calibration', 'Coin flip accuracy', 'No predictions made'], correct: 1, explanation: 'Brier score 0 = every prediction was exactly the outcome (0% or 100% and always correct). It\'s the theoretical optimum.' },
      { q: 'Russia-Ukraine ceasefire at 54% Yes. 10 contracts cost? Max profit if Yes?', options: ['$5.40 cost, $4.60 profit', '$10 cost, $5.40 profit', '$5.40 cost, $10 profit', '$0.54 cost, $0.46 profit'], correct: 0, explanation: '10 contracts × $0.54 = $5.40 cost. If Yes resolves: 10 × $1.00 = $10.00 payout. Profit = $10 - $5.40 = $4.60.' },
    ],
    unlocks: {
      panels: ['polymarketPanel', 'myBetsPanel'],
      navItems: ['Markets'],
      holdingsCols: [],
      sections: ['polymarketPanel', 'myBetsPanel', 'miCalibration', 'miBrier'],
    },
  },
  // Stage 9: Finding Edge
  {
    id: 9, name: "Finding Edge", icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
    desc: "Arbitrage, Kelly criterion, and smart money detection.",
    unlockPreview: "Unlocks: Bellman-Ford Arbitrage Scanner (500+ PM + 350+ KL), EV Calculator, Kelly Criterion, Smart Money detector, Cross-Market Dependencies",
    xpReward: 350,
    lessons: [
      { type: 'concept', title: 'What is Arbitrage?', video: 'https://www.youtube.com/watch?v=6WBQ2jR5M-8', body: 'Arbitrage = guaranteed profit from price discrepancies. If two exchanges price the same event differently, you buy cheap on one and sell expensive on the other. In prediction markets, this means buying Yes on Platform A at $0.45 and No on Platform B at $0.48 — total cost $0.93, guaranteed $1 payout, $0.07 profit.' },
      { type: 'concept', title: 'Cross-Platform Scanning', video: 'https://www.youtube.com/watch?v=AuCH7fHZsZ4', body: 'We scan 500+ Polymarket and 350+ Kalshi markets using Bellman-Ford negative cycle detection. The algorithm treats prices as edge weights in a graph and finds mathematical constraint violations — no fuzzy text matching needed for intra-platform detection.' },
      { type: 'concept', title: 'EV Bets vs Guaranteed Arb', video: 'https://www.youtube.com/watch?v=s7QfCsGqeuw', body: 'GUARANTEED arbitrage: prices violate no-arb constraints (extremely rare, bots catch in milliseconds). EV BETS: positive expected value based on your probability assessment, but unlisted outcomes could still win. Most "arbitrage" in prediction markets is actually EV betting.' },
      { type: 'concept', title: 'Kelly Criterion', video: 'https://www.youtube.com/watch?v=fSbhJvY2ge4', body: 'How much should you bet? Kelly says: f* = (p × b - q) / b, where p = your probability, q = 1-p, b = payout odds. Kelly maximizes long-run growth. But full Kelly is aggressive — practitioners use half-Kelly or quarter-Kelly to reduce variance and risk of ruin.' },
      { type: 'concept', title: 'Smart Money Detection', video: 'https://www.youtube.com/watch?v=_1YpGcZmrPE', body: 'When a market\'s 24-hour volume spikes to 5-10x its daily average, informed traders may be positioning. They have information the market hasn\'t priced in yet. Following smart money isn\'t guaranteed profit, but it\'s one of the best signals available in prediction markets.' },
      { type: 'concept', title: 'Cross-Market Dependencies', video: 'https://www.youtube.com/watch?v=oUVbe3PYjp8', body: 'When the "Fed rate cut" market moves, which other markets move with it? Correlation analysis across prediction markets reveals hidden dependencies. If two markets have 0.8 correlation, a move in one predicts a move in the other — giving you a time advantage.' },
    ],
    quiz: [
      { q: 'PM Yes=$0.06 + KL No=$0.48. Total cost $0.54. Guaranteed profit if Yes?', options: ['$0.46', '$0.54', '$1.00', '$0.06'], correct: 0, explanation: 'If Yes resolves: PM Yes pays $1.00 (profit $0.94), KL No pays $0 (loss $0.48). Net: $0.94 - $0.48 = $0.46. But you paid $0.54 total, so profit = $1.00 - $0.54 = $0.46.' },
      { q: 'Kelly: even odds (b=1), p=0.60, q=0.40. Optimal bankroll fraction?', options: ['60%', '40%', '20%', '10%'], correct: 2, explanation: 'f* = (p×b - q) / b = (0.60×1 - 0.40) / 1 = 0.20 = 20%. Bet 20% of your bankroll. In practice, use half-Kelly (10%) for safety.' },
      { q: 'An EV BET shows 73% implied chance of unlisted outcome. Buying all for 27c means:', options: ['Guaranteed $0.73 profit', 'You\'re betting listed outcomes cover everything', 'Risk-free arbitrage', 'The market is inefficient'], correct: 1, explanation: 'The 73% "implied other" means the market thinks there\'s a 73% chance none of the listed options will win. You\'re betting against that — it\'s speculation, not arbitrage.' },
      { q: 'A market moves 40% → 65% in 2 hours, no public news. Possible explanation?', options: ['Random noise', 'Informed money / smart money moving', 'Market maker manipulation', 'All of the above'], correct: 3, explanation: 'A 25-point move in 2 hours without news could be informed traders, market manipulation, or even random noise on thin markets. Smart money detection flags these for human analysis.' },
    ],
    unlocks: {
      panels: ['tradingToolsPanel', 'marketIntelPanel'],
      navItems: ['Tools', 'Intelligence'],
      holdingsCols: [],
      sections: ['tradingToolsPanel', 'marketIntelPanel'],
    },
  },
];

const ADMIN_USERS = ['shihanmahfuz'];
const TESTER_USERS = ['abdullah'];
const PASS_THRESHOLD = 0.7;

const RANKS = [
  { name: 'New Trader', minXP: 0, icon: '&#9679;' },
  { name: 'Apprentice Analyst', minXP: 200, icon: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/></svg>' },
  { name: 'Junior Quant', minXP: 600, icon: '&#9670;' },
  { name: 'Portfolio Manager', minXP: 1400, icon: '&#9632;' },
  { name: 'Chief Investment Officer', minXP: 3000, icon: '&#9733;' },
];

const BADGES = {
  first_lesson: { icon: '&#10003;', name: 'First Lesson', desc: 'Complete any stage' },
  tape_reader: { icon: '&#8599;', name: 'Tape Reader', desc: 'Complete Stage 2' },
  risk_aware: { icon: '&#9681;', name: 'Risk Aware', desc: 'Complete Stage 3' },
  quant_brain: { icon: '&#8721;', name: 'Quant Brain', desc: 'Complete Stage 5' },
  tax_nerd: { icon: '$', name: 'Tax Nerd', desc: 'Complete Stage 6' },
  options_trader: { icon: '&#916;', name: 'Options Trader', desc: 'Complete Stage 7' },
  prediction_pro: { icon: '&#8982;', name: 'Prediction Pro', desc: 'Complete Stage 8' },
  edge_finder: { icon: '&#8853;', name: 'Edge Finder', desc: 'Complete Stage 9' },
  cio: { icon: '&#9733;', name: 'CIO', desc: 'Pass the final exam' },
};

const STAGE_BADGES = { 2: 'tape_reader', 3: 'risk_aware', 5: 'quant_brain', 6: 'tax_nerd', 7: 'options_trader', 8: 'prediction_pro', 9: 'edge_finder' };

// ── State Management ─────────────────────────────────────
function _learnKey() {
  return _session?.userId ? `veris_learner_${_session.userId}` : 'veris_learner_guest';
}

function getDefaultLearner() {
  return { stage: 1, xp: 0, streak: 0, lastActiveDate: '', completedStages: [1], badges: [], examPassed: false, learningMode: true };
}

function isAdmin() {
  return _session?.username && ADMIN_USERS.includes(_session.username);
}

function isTester() {
  return _session?.username && TESTER_USERS.includes(_session.username);
}

function getLearner() {
  if (isAdmin()) {
    return { stage: 10, xp: 9999, streak: 99, lastActiveDate: new Date().toISOString().slice(0,10), completedStages: [1,2,3,4,5,6,7,8,9], badges: Object.keys(BADGES), examPassed: true, learningMode: false };
  }
  if (isTester() && !window._testerResetDone) {
    window._testerResetDone = true;
    const fresh = getDefaultLearner();
    saveLearner(fresh);
    return fresh;
  }
  try {
    const data = JSON.parse(localStorage.getItem(_learnKey()));
    if (data && typeof data.stage === 'number') return data;
  } catch {}
  return getDefaultLearner();
}

function saveLearner(state) {
  localStorage.setItem(_learnKey(), JSON.stringify(state));
}

function getRank(xp) {
  let rank = RANKS[0];
  for (const r of RANKS) { if (xp >= r.minXP) rank = r; }
  return rank;
}

function getNextRank(xp) {
  for (const r of RANKS) { if (xp < r.minXP) return r; }
  return null;
}

// ── Tool Gating ──────────────────────────────────────────
function getAllUnlockedPanels(learner) {
  if (!learner.learningMode) return null;
  const panels = new Set();
  for (const s of STAGES) {
    if (learner.completedStages.includes(s.id)) {
      s.unlocks.panels.forEach(p => panels.add(p));
    }
  }
  return panels;
}

function getAllUnlockedNavItems(learner) {
  if (!learner.learningMode) return null;
  const items = new Set();
  for (const s of STAGES) {
    if (learner.completedStages.includes(s.id)) {
      s.unlocks.navItems.forEach(n => items.add(n));
    }
  }
  return items;
}

function getUnlockStageForNav(label) {
  for (const s of STAGES) {
    if (s.unlocks.navItems.includes(label)) return s;
  }
  return null;
}

function isPanelUnlocked(panelId) {
  const learner = getLearner();
  if (!learner.learningMode) return true;
  const panels = getAllUnlockedPanels(learner);
  return panels === null || panels.has(panelId);
}

function isSectionUnlocked(sectionId) {
  const learner = getLearner();
  if (!learner.learningMode) return true;
  for (const s of STAGES) {
    if (learner.completedStages.includes(s.id) && s.unlocks.sections.includes(sectionId)) return true;
  }
  return false;
}

// ── Stage Completion ─────────────────────────────────────
function completeStage(stageNum) {
  const learner = getLearner();
  if (learner.completedStages.includes(stageNum)) return;

  const stage = STAGES.find(s => s.id === stageNum);
  if (!stage) return;

  learner.completedStages.push(stageNum);
  learner.xp += stage.xpReward;
  if (stageNum > learner.stage) learner.stage = stageNum + 1;

  // Streak
  const today = new Date().toISOString().slice(0, 10);
  if (learner.lastActiveDate !== today) {
    const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
    learner.streak = learner.lastActiveDate === yesterday ? learner.streak + 1 : 1;
    learner.lastActiveDate = today;
    learner.xp += 20;
  }

  // Badges
  if (!learner.badges.includes('first_lesson') && stageNum >= 2) {
    learner.badges.push('first_lesson');
  }
  const stageBadge = STAGE_BADGES[stageNum];
  if (stageBadge && !learner.badges.includes(stageBadge)) {
    learner.badges.push(stageBadge);
  }

  saveLearner(learner);
  runUnlockCeremony(stage);
  setTimeout(() => {
    renderLearnSection();
    applyToolGating();
    if (typeof buildNavBar === 'function') buildNavBar();
    // Re-render summary grid to unlock metric cards
    if (typeof lastAnalysisData !== 'undefined' && lastAnalysisData && typeof renderResults === 'function') {
      renderResults(lastAnalysisData);
    }
  }, 3500);
}

// ── UI: Learn Section ────────────────────────────────────
function renderLearnSection() {
  const el = document.getElementById('learnSection');
  if (!el) return;
  const learner = getLearner();

  if (!learner.learningMode) {
    el.style.display = 'none';
    return;
  }
  el.style.display = 'block';

  const rank = getRank(learner.xp);
  const nextRank = getNextRank(learner.xp);
  const progress = nextRank ? ((learner.xp - rank.minXP) / (nextRank.minXP - rank.minXP)) * 100 : 100;
  const currentStage = Math.min(learner.stage, 10);

  const nextStage = Math.max(...learner.completedStages) + 1;
  const lockSvg = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>';
  const checkSvg = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>';
  const flameSvg = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation:flameFlicker 2s ease-in-out infinite"><path d="M12 12c2-2.96 0-7-1-8 0 3.038-1.773 4.741-3 6-1.226 1.26-2 3.24-2 5a6 6 0 1012 0c0-1.532-1.056-3.94-2-5-1.786 3-2.791 3-4 2z"/></svg>';

  // Duolingo-style vertical skill tree
  const stageNodes = STAGES.map((s, idx) => {
    const done = learner.completedStages.includes(s.id);
    const isNext = s.id === nextStage && !done;
    const locked = !done && !isNext;
    const onclick = isNext ? `onclick="openLessonDrawer(${s.id})"` : (locked ? `onclick="showLockedToast(${s.id})"` : '');
    const offset = idx % 2 === 0 ? 'left' : 'right';
    let nodeClass = 'skill-node';
    if (done) nodeClass += ' done';
    else if (isNext) nodeClass += ' active';
    else nodeClass += ' locked';

    const icon = done ? checkSvg : (locked ? lockSvg : s.icon);
    const startBtn = isNext ? '<div class="skill-start">Start</div>' : '';

    return `<div class="skill-row ${offset}">
      <div class="${nodeClass}" ${onclick}>
        <div class="skill-circle">${icon}</div>
        ${startBtn}
      </div>
      <div class="skill-label">${s.name}</div>
    </div>`;
  }).join('');

  // Badge cabinet
  const allBadgeKeys = Object.keys(BADGES);
  const badgeCabinet = allBadgeKeys.map(key => {
    const b = BADGES[key];
    const earned = learner.badges.includes(key);
    return `<div class="badge-slot ${earned ? 'earned' : 'locked'}" title="${b.name}: ${b.desc}">
      <div class="badge-icon">${earned ? b.icon : '?'}</div>
      <div class="badge-name">${b.name}</div>
    </div>`;
  }).join('');

  el.innerHTML = `
    <div class="learn-header">
      <div class="learn-rank-banner">
        <div style="display:flex;align-items:center;gap:10px">
          <span style="font-size:1.4rem">${rank.icon}</span>
          <div>
            <div style="font-weight:700;font-size:0.9rem;letter-spacing:1px">${rank.name.toUpperCase()}</div>
            <div style="font-size:0.65rem;color:var(--muted)">Stage ${Math.min(currentStage, 9)} of 9</div>
          </div>
        </div>
        <div style="flex:1;margin:0 20px">
          <div style="display:flex;justify-content:space-between;font-size:0.62rem;color:var(--muted);margin-bottom:3px">
            <span>${learner.xp} XP</span>
            <span>${nextRank ? nextRank.minXP + ' XP' : 'MAX'}</span>
          </div>
          <div class="learn-xp-bar"><div class="learn-xp-fill" style="width:${progress}%"></div></div>
        </div>
        ${learner.streak > 0 ? `<div class="streak-pill">${flameSvg}<span class="streak-num">${learner.streak}</span><span class="streak-text">day streak</span></div>` : ''}
      </div>
    </div>
    <div class="learn-compact-row">
      <div class="badge-cabinet">
        <div class="badge-cabinet-title">Achievements</div>
        <div class="badge-grid">${badgeCabinet}</div>
      </div>
    </div>
    <div class="skill-tree-wrapper">
      <div class="skill-tree collapsed" id="skillTreeBody">${stageNodes}</div>
      <button class="btn-secondary skill-tree-toggle" onclick="document.getElementById('skillTreeBody').classList.toggle('collapsed');this.textContent=this.textContent.includes('See')? 'Hide stages' : 'See all 9 stages'" style="margin-top:8px;font-size:0.7rem;width:100%">See all 9 stages</button>
    </div>
  `;
}

// ── UI: Lesson Drawer ────────────────────────────────────
let _lessonState = { stage: null, cardIdx: 0, quizIdx: 0, quizCorrect: 0 };

function openLessonDrawer(stageNum) {
  const stage = STAGES.find(s => s.id === stageNum);
  if (!stage || (!stage.lessons.length && !stage.quiz.length)) return;

  const learner = getLearner();
  const prevCompleted = stageNum === 1 || learner.completedStages.includes(stageNum - 1);
  if (!prevCompleted) {
    showLockedToast(stageNum);
    return;
  }
  if (learner.completedStages.includes(stageNum)) return;

  _lessonState = { stage: stageNum, cardIdx: 0, quizIdx: 0, quizCorrect: 0 };
  const overlay = document.getElementById('lessonDrawerOverlay');
  overlay.style.display = 'flex';
  renderLessonCard();
}

function closeLessonDrawer() {
  document.getElementById('lessonDrawerOverlay').style.display = 'none';
}

function renderLessonCard() {
  const stage = STAGES.find(s => s.id === _lessonState.stage);
  if (!stage) return;

  const drawer = document.getElementById('lessonDrawerContent');
  const totalCards = stage.lessons.length + stage.quiz.length;
  const currentIdx = _lessonState.cardIdx;
  const isQuiz = currentIdx >= stage.lessons.length;
  const progressPct = ((currentIdx + 1) / totalCards) * 100;

  const encouragements = ['Great job!', 'You\'re on fire!', 'Keep going!', 'Almost there!', 'Crushing it!', 'Nice one!'];
  const encMsg = currentIdx > 0 && !isQuiz ? `<div style="text-align:center;color:var(--green);font-size:0.72rem;font-weight:600;margin-bottom:8px">${encouragements[currentIdx % encouragements.length]}</div>` : '';

  let cardHtml = '';
  if (!isQuiz) {
    const card = stage.lessons[currentIdx];
    const hearts = stage.quiz.length > 0 ? `<div style="text-align:right;font-size:0.72rem;color:var(--muted)">Quiz ahead: need ${Math.ceil(stage.quiz.length * PASS_THRESHOLD)}/${stage.quiz.length} correct</div>` : '';
    const _vid = card.video || '';
    const _vidId = _vid.match(/[?&]v=([^&]+)/)?.[1] || '';
    const _thumb = _vidId ? `https://img.youtube.com/vi/${_vidId}/mqdefault.jpg` : '';
    const videoBtn = _vidId ? `<a href="${_vid}" target="_blank" rel="noopener" style="display:block;margin-top:12px;border-radius:10px;overflow:hidden;border:1px solid rgba(255,0,0,0.2);text-decoration:none;position:relative"><img src="${_thumb}" alt="Video" style="width:100%;display:block;opacity:0.85" onerror="this.parentElement.style.display='none'"><div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(255,0,0,0.85);width:48px;height:48px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.2rem;color:#fff"><svg width="18" height="18" viewBox="0 0 24 24" fill="white" stroke="none"><polygon points="5 3 19 12 5 21 5 3"/></svg></div><div style="padding:8px 12px;background:rgba(0,0,0,0.6);font-size:0.7rem;color:#ccc">Watch video explainer on YouTube</div></a>` : '';
    const unlockPrev = currentIdx === 0 && stage.unlockPreview ? `<div style="background:rgba(45,184,122,0.08);border:1px solid rgba(45,184,122,0.2);border-radius:8px;padding:10px 14px;margin-bottom:12px;font-size:0.72rem;color:var(--green)"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 019.9-1"/></svg> <b>Complete this lesson to unlock:</b> ${stage.unlockPreview}</div>` : '';
    // Science-based learning: Active Recall prompt before moving on
    const recallPrompts = [
      'Before moving on: can you explain this concept in your own words?',
      'Quick check: how would you explain this to a friend?',
      'Pause and think: what is the key takeaway from this card?',
      'Active recall: close your eyes and try to remember the main formula.',
      'Self-test: what makes this metric "good" vs "bad"?',
    ];
    const recallPrompt = `<div style="background:rgba(45,184,122,0.08);border-left:3px solid #2DB87A;padding:8px 12px;margin-top:12px;font-size:0.7rem;color:var(--muted);font-style:italic">${recallPrompts[currentIdx % recallPrompts.length]}</div>`;

    // Article link (Investopedia) based on card title keywords
    const articleMap = {
      'Sharpe': 'https://www.investopedia.com/terms/s/sharperatio.asp',
      'Sortino': 'https://www.investopedia.com/terms/s/sortinoratio.asp',
      'Volatility': 'https://www.investopedia.com/terms/v/volatility.asp',
      'Max Drawdown': 'https://www.investopedia.com/terms/m/maximum-drawdown-mdd.asp',
      'SMA': 'https://www.investopedia.com/terms/s/sma.asp',
      'RSI': 'https://www.investopedia.com/terms/r/rsi.asp',
      'Macro': 'https://www.investopedia.com/terms/m/macroeconomics.asp',
      'VaR': 'https://www.investopedia.com/terms/v/var.asp',
      'CVaR': 'https://www.investopedia.com/terms/c/conditional_value_at_risk.asp',
      'Monte Carlo': 'https://www.investopedia.com/terms/m/montecarlosimulation.asp',
      'Regime': 'https://www.investopedia.com/terms/v/volatility.asp',
      'Correlation': 'https://www.investopedia.com/terms/c/correlation.asp',
      'Efficient Frontier': 'https://www.investopedia.com/terms/e/efficientfrontier.asp',
      'What-If': 'https://www.investopedia.com/terms/s/scenario_analysis.asp',
      'HHI': 'https://www.investopedia.com/terms/h/hhi.asp',
      'Effective N': 'https://www.investopedia.com/terms/d/diversification.asp',
      'Diversification': 'https://www.investopedia.com/terms/d/diversification.asp',
      'Beta': 'https://www.investopedia.com/terms/b/beta.asp',
      'Alpha': 'https://www.investopedia.com/terms/a/alpha.asp',
      'Calmar': 'https://www.investopedia.com/terms/c/calmarratio.asp',
      'Treynor': 'https://www.investopedia.com/terms/t/treynorratio.asp',
      'Information Ratio': 'https://www.investopedia.com/terms/i/informationratio.asp',
      'Stress': 'https://www.investopedia.com/terms/s/stresstesting.asp',
      'CAPM': 'https://www.investopedia.com/terms/c/capm.asp',
      'Capital Gains': 'https://www.investopedia.com/terms/c/capitalgain.asp',
      'Tax-Loss': 'https://www.investopedia.com/terms/t/taxgainlossharvesting.asp',
      'Tariff': 'https://www.investopedia.com/terms/t/tariff.asp',
      'Call Option': 'https://www.investopedia.com/terms/c/calloption.asp',
      'Put Option': 'https://www.investopedia.com/terms/p/put.asp',
      'Delta': 'https://www.investopedia.com/terms/d/delta.asp',
      'Gamma': 'https://www.investopedia.com/terms/g/gamma.asp',
      'Theta': 'https://www.investopedia.com/terms/t/theta.asp',
      'Vega': 'https://www.investopedia.com/terms/v/vega.asp',
      'IV Skew': 'https://www.investopedia.com/terms/v/volatility-skew.asp',
      'Prediction Market': 'https://www.investopedia.com/terms/p/prediction-market.asp',
      'Expected Value': 'https://www.investopedia.com/terms/e/expected-value.asp',
      'Kelly': 'https://www.investopedia.com/articles/trading/04/091504.asp',
      'Arbitrage': 'https://www.investopedia.com/terms/a/arbitrage.asp',
      'Brier': 'https://en.wikipedia.org/wiki/Brier_score',
    };
    let articleUrl = '';
    for (const [keyword, url] of Object.entries(articleMap)) {
      if (card.title.includes(keyword)) { articleUrl = url; break; }
    }
    const articleBtn = articleUrl ? `<a href="${articleUrl}" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:6px;margin-top:8px;padding:6px 12px;background:rgba(45,184,122,0.08);border:1px solid rgba(45,184,122,0.2);border-radius:8px;color:var(--green);font-size:0.7rem;font-weight:600;text-decoration:none"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z"/><path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z"/></svg> Read article on Investopedia</a>` : '';

    cardHtml = `
      ${encMsg}
      ${unlockPrev}
      <div class="lesson-card concept">
        <div class="lesson-card-type">CONCEPT ${currentIdx + 1} of ${stage.lessons.length}</div>
        <h3>${card.title}</h3>
        <p>${card.body}</p>
        ${recallPrompt}
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">${articleBtn}</div>
        ${videoBtn}
      </div>
      ${hearts}
      <button class="btn-primary" onclick="nextLessonCard()" style="width:100%;margin-top:12px">Got it! →</button>`;
  } else {
    const qIdx = currentIdx - stage.lessons.length;
    const q = stage.quiz[qIdx];
    const testerHint = isTester() ? `<div style="background:rgba(245,166,35,0.1);border:1px solid rgba(245,166,35,0.3);border-radius:8px;padding:8px 12px;margin-bottom:10px;font-size:0.7rem;color:var(--yellow)">TESTER MODE — Correct answer: <b>${q.options[q.correct]}</b> (option ${q.correct + 1})</div>` : '';
    cardHtml = `
      <div class="lesson-card quiz">
        <div class="lesson-card-type">QUIZ — Question ${qIdx + 1} of ${stage.quiz.length}</div>
        ${testerHint}
        <h3>${q.q}</h3>
        <div class="quiz-options" id="quizOptions">
          ${q.options.map((opt, i) => `<button class="quiz-option" onclick="answerQuiz(${i})">${opt}</button>`).join('')}
        </div>
        <div id="quizFeedback" style="display:none"></div>
      </div>`;
  }

  drawer.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <div style="font-size:0.85rem;font-weight:700">${stage.icon} ${stage.name}</div>
      <div style="font-size:0.72rem;color:var(--muted)">Card ${currentIdx + 1} of ${totalCards}</div>
    </div>
    <div class="learn-xp-bar" style="margin-bottom:16px"><div class="learn-xp-fill" style="width:${progressPct}%"></div></div>
    ${cardHtml}`;
}

function nextLessonCard() {
  const stage = STAGES.find(s => s.id === _lessonState.stage);
  const totalCards = stage.lessons.length + stage.quiz.length;
  _lessonState.cardIdx++;
  if (_lessonState.cardIdx >= totalCards) {
    const quizTotal = stage.quiz.length;
    const quizCorrect = _lessonState.quizCorrect;
    const pct = quizTotal > 0 ? quizCorrect / quizTotal : 1;
    if (pct >= PASS_THRESHOLD) {
      closeLessonDrawer();
      completeStage(_lessonState.stage);
    } else {
      showQuizFailure(stage, quizCorrect, quizTotal);
    }
    return;
  }
  renderLessonCard();
}

function showQuizFailure(stage, correct, total) {
  const drawer = document.getElementById('lessonDrawerContent');
  const pct = Math.round(correct / total * 100);
  const needed = Math.ceil(total * PASS_THRESHOLD);
  drawer.innerHTML = `
    <div style="text-align:center;padding:40px 20px">
      <div style="font-size:2rem;margin-bottom:12px;color:var(--red)">&#10007;</div>
      <h3 style="color:var(--red);margin-bottom:8px">Not quite there yet!</h3>
      <p style="font-size:0.85rem;color:var(--muted);margin-bottom:16px">
        You scored <b style="color:var(--red)">${correct}/${total}</b> (${pct}%).
        <br>You need <b style="color:var(--green)">${needed}/${total}</b> (${Math.round(PASS_THRESHOLD*100)}%) to pass.
      </p>
      <div style="font-size:0.78rem;color:var(--muted);margin-bottom:20px">
        Review the concepts and try again. You've got this!
      </div>
      <div style="display:flex;gap:10px;justify-content:center">
        <button class="btn-primary" onclick="openLessonDrawer(${stage.id})" style="font-size:0.78rem">
          Retry Lesson
        </button>
        <button class="btn-secondary" onclick="closeLessonDrawer()" style="font-size:0.78rem">
          Close
        </button>
      </div>
    </div>`;
}

function answerQuiz(optionIdx) {
  const stage = STAGES.find(s => s.id === _lessonState.stage);
  const qIdx = _lessonState.cardIdx - stage.lessons.length;
  const q = stage.quiz[qIdx];
  const correct = optionIdx === q.correct;

  const btns = document.querySelectorAll('#quizOptions .quiz-option');
  btns.forEach((btn, i) => {
    btn.disabled = true;
    if (i === q.correct) btn.classList.add('correct');
    if (i === optionIdx && !correct) btn.classList.add('wrong');
  });

  const fb = document.getElementById('quizFeedback');
  const quizTotal = stage.quiz.length;
  const quizSoFar = qIdx + 1;
  const scoreTracker = `<div style="font-size:0.68rem;color:var(--muted);margin-top:8px">Score: ${_lessonState.quizCorrect + (correct ? 1 : 0)}/${quizSoFar} — Need ${Math.ceil(quizTotal * PASS_THRESHOLD)}/${quizTotal} to pass</div>`;

  if (correct) {
    const learner = getLearner();
    learner.xp += 10;
    saveLearner(learner);
    _lessonState.quizCorrect++;
    const celebs = ['Nailed it!', 'On fire!', 'Brilliant!', 'Perfect!', 'Crushed it!'];
    const celeb = celebs[qIdx % celebs.length];
    fb.innerHTML = `<div class="quiz-fb correct" style="font-size:1.1rem">${celeb} +10 XP</div><p style="font-size:0.75rem;color:var(--muted);margin-top:6px">${q.explanation}</p>${scoreTracker}`;
  } else {
    fb.innerHTML = `<div class="quiz-fb wrong" style="font-size:1.1rem;color:var(--red)">&#10007; Not quite!</div><p style="font-size:0.75rem;color:var(--muted);margin-top:6px">${q.explanation}</p>${scoreTracker}`;
  }
  fb.style.display = 'block';
  fb.insertAdjacentHTML('afterend', '<button class="btn-primary" onclick="nextLessonCard()" style="width:100%;margin-top:12px">Next →</button>');
}

// ── Unlock Ceremony ──────────────────────────────────────
function runUnlockCeremony(stage) {
  const overlay = document.getElementById('unlockCeremonyOverlay');
  overlay.style.display = 'flex';

  if (typeof confetti === 'function') {
    setTimeout(() => {
      confetti({ particleCount: 100, spread: 80, origin: {y: 0.5}, colors: ['#10b981','#06b6d4','#8b5cf6','#f59e0b'], gravity: 0.8, scalar: 1.2 });
    }, 300);
    setTimeout(() => {
      confetti({ particleCount: 50, angle: 60, spread: 55, origin: {x: 0}, colors: ['#10b981','#8b5cf6'] });
      confetti({ particleCount: 50, angle: 120, spread: 55, origin: {x: 1}, colors: ['#06b6d4','#f59e0b'] });
    }, 800);
  }

  const unlockList = [...stage.unlocks.navItems, ...stage.unlocks.panels.map(p => p.replace('Panel', '').replace('section', ''))].filter((v, i, a) => a.indexOf(v) === i).slice(0, 6);

  const rank = getRank(getLearner().xp);
  const badge = STAGE_BADGES[stage.id];
  const badgeInfo = badge ? BADGES[badge] : null;
  const badgeHtml = badgeInfo ? `<div style="margin-top:10px;font-size:1.5rem">${badgeInfo.icon} <span style="font-size:0.78rem;color:var(--green)">${badgeInfo.name} earned!</span></div>` : '';

  overlay.innerHTML = `
    <div class="ceremony-content">
      <div class="ceremony-stage" style="animation:bounce 0.6s ease">${stage.icon}</div>
      <div class="ceremony-title">STAGE ${stage.id} COMPLETE!</div>
      <div class="ceremony-subtitle">${stage.name}</div>
      <div class="ceremony-xp" style="animation:xpCount 1s ease">+${stage.xpReward} XP</div>
      ${badgeHtml}
      <div style="font-size:0.72rem;color:var(--muted);margin:8px 0">${rank.icon} ${rank.name}</div>
      <div style="font-size:0.78rem;color:var(--green);margin-bottom:12px;font-weight:600">New tools unlocked:</div>
      <div class="ceremony-unlocks">
        ${unlockList.map((u, i) => `<div class="ceremony-unlock-item" style="animation-delay:${0.5 + i * 0.15}s">${u}</div>`).join('')}
      </div>
      <button class="btn-primary" onclick="document.getElementById('unlockCeremonyOverlay').style.display='none'" style="margin-top:24px;font-size:0.85rem;padding:10px 30px">
        Continue
      </button>
    </div>`;
}

// ── Tool Gating Application ──────────────────────────────
function applyToolGating() {
  const learner = getLearner();
  if (!learner.learningMode) {
    document.querySelectorAll('.learn-locked-section').forEach(el => el.classList.remove('learn-locked-section'));
    return;
  }

  const unlockedPanels = getAllUnlockedPanels(learner);
  if (!unlockedPanels) return;

  const ALL_GATED_PANELS = [
    'sectionSummary', 'sectionAI', 'sectionHoldings', 'candlePanel', 'intradayPanel',
    'monteCarloPanel', 'frontierPanel', 'corrPanel', 'stressPanel', 'factorPanel',
    'tariffPanel', 'taxPanel', 'optionsPanel', 'sectionAllocation', 'sectionMacro',
    'sectionNews', 'holdersPanel', 'whatifPanel', 'regimePanel', 'eventsPanel',
    'qualityPanel', 'tradingToolsPanel', 'marketIntelPanel', 'polymarketPanel', 'myBetsPanel',
  ];

  ALL_GATED_PANELS.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    if (unlockedPanels.has(id)) {
      el.classList.remove('learn-locked-section');
      el.style.removeProperty('display');
    } else {
      el.classList.add('learn-locked-section');
    }
  });
}

function buildNavBarWithLocks(originalBuildNavBar) {
  const learner = getLearner();
  if (!learner.learningMode) { originalBuildNavBar(); return; }

  const unlockedNavItems = getAllUnlockedNavItems(learner);
  const container = document.getElementById('navLinks');
  if (!container) return;

  container.innerHTML = NAV_SECTIONS.map(s => {
    const unlocked = unlockedNavItems === null || unlockedNavItems.has(s.label);
    if (unlocked) {
      return `<a class="nav-link" data-target="${s.id}" onclick="scrollToSection('${s.id}')">${s.label}</a>`;
    } else {
      const stage = getUnlockStageForNav(s.label);
      const tip = stage ? `Complete "${stage.name}" to unlock` : 'Locked';
      return `<a class="nav-link nav-locked" title="${tip}" onclick="showLockedToast(${stage ? stage.id : 0})"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg> ${s.label}</a>`;
    }
  }).join('');
}

function showLockedToast(stageNum) {
  const stage = STAGES.find(s => s.id === stageNum);
  if (!stage) return;
  const learner = getLearner();
  const prevDone = stageNum === 1 || learner.completedStages.includes(stageNum - 1);
  const toast = document.getElementById('lockToast');
  if (!toast) return;
  if (!prevDone) {
    const prevStage = STAGES.find(s => s.id === stageNum - 1);
    toast.innerHTML = `<b><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg> Locked</b> — Complete "${prevStage?.name || 'previous stage'}" first before you can start "${stage.name}".`;
  } else {
    toast.innerHTML = `<b><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg> Locked</b> — Complete "${stage.name}" to unlock. <button class="btn-primary" style="font-size:0.68rem;padding:3px 10px;margin-left:8px" onclick="openLessonDrawer(${stageNum});this.parentElement.style.display='none'">Start Lesson</button>`;
  }
  toast.style.display = 'block';
  setTimeout(() => { toast.style.display = 'none'; }, 6000);
}

// ── Advanced Mode Toggle ─────────────────────────────────
function toggleAdvancedMode() {
  const learner = getLearner();
  if (isAdmin()) return;
  learner.learningMode = !learner.learningMode;
  saveLearner(learner);
  renderLearnSection();
  applyToolGating();
  if (typeof buildNavBar === 'function') buildNavBar();
  if (typeof lastAnalysisData !== 'undefined' && lastAnalysisData && typeof renderResults === 'function') {
    renderResults(lastAnalysisData);
  }
  const btn = document.getElementById('advancedModeBtn');
  if (btn) btn.textContent = learner.learningMode ? 'Advanced Mode: OFF' : 'Advanced Mode: ON';
}

// ── Init ─────────────────────────────────────────────────
function initLearner() {
  const learner = getLearner();
  if (isAdmin()) {
    learner.learningMode = false;
    const el = document.getElementById('learnSection');
    if (el) el.style.display = 'none';
    document.querySelectorAll('.learn-locked-section').forEach(el => el.classList.remove('learn-locked-section'));
    const btn = document.getElementById('advancedModeBtn');
    if (btn) btn.textContent = 'Advanced Mode: ON (Admin)';
    return;
  }
  renderLearnSection();
  applyToolGating();
  const btn = document.getElementById('advancedModeBtn');
  if (btn) btn.textContent = learner.learningMode ? 'Advanced Mode: OFF' : 'Advanced Mode: ON';
}
