# Research Notes — the evidence behind the sidekick

This is the curated reference the specialists draw on when they need to justify a claim with
something other than an opinion. It maps each design choice in the system to the academic and
practitioner literature, states the effect honestly (including how small and how fragile most of
these effects are), and points back to the agent or skill that relies on it.

**How to use this file.** When an agent makes an empirical claim ("insider cluster buys are a real
signal", "selling premium when IV rank is high has positive expectancy"), it should be consistent
with what's written here. If you want to challenge a rule in `CLAUDE.md`, challenge it against this
evidence, not against a feeling.

## Reading-the-evidence disclaimer (read this first)

1. **Effect sizes are small and period-dependent.** Almost every edge below is a few percent per
   year, gross, in-sample, before costs and taxes. None of them is a license to size up.
2. **Published anomalies decay.** McLean & Pontiff (2016) found that the average documented
   predictor's return falls by roughly half (~58%) out of sample and after publication. Assume the
   number you read in a 2005 paper is now smaller — possibly zero.
3. **Multiple-testing inflates everything.** Harvey, Liu & Zhu (2016) argue that, given how many
   factors have been data-mined, the t-statistic hurdle for believing a "new" anomaly should be
   ~3.0, not the textbook 2.0. Treat any single backtest accordingly.
4. **These are summaries.** Verify against the primary sources before betting real capital on a
   paraphrase. Citations are author/year/venue (no URLs); look them up.
5. **Statistical significance ≠ tradable after costs.** A signal that survives a t-test can still
   be unprofitable once spread, impact, borrow, and slippage are subtracted. The `quant-builder`
   and `microstructure-analyst` exist precisely to make that subtraction explicit.

---

## 1. Position sizing and the Kelly criterion
*Used by: `quant-builder`, `risk-officer`, `strategy_001.yaml` (`use_kelly_fraction: 0.25`).*

**Finding.** The Kelly criterion (Kelly 1956; Thorp 2006) maximizes the long-run geometric growth
rate of capital. For a bet with win probability `p` and payoff ratio `b`, the growth-optimal
fraction is `f* = p − (1 − p)/b`. Betting more than `f*` *lowers* long-run growth and increases
drawdown; betting `2·f*` has zero expected growth even with a positive edge.

**Effect / caveat.** Full Kelly is far too aggressive for discretionary trading because (a) `p` and
`b` are estimated with large error, and (b) full-Kelly drawdowns are brutal (a 50% drawdown is a
routine Kelly event). MacLean, Thorp & Ziemba (2011) show fractional Kelly (½ or ¼) keeps most of
the growth with a large reduction in volatility and drawdown. Overestimating your edge makes Kelly
*negative-expectancy* faster than intuition suggests.

**How this system uses it.** `quant-builder` computes `f*`, then explicitly sizes at ¼-Kelly and
shows the arithmetic. If estimated Kelly is negative, it returns `NEEDS_INPUT`/`VETO_INPUT` rather
than sizing. The hard 1%-per-trade cap in `CLAUDE.md` overrides Kelly whenever Kelly would suggest
more — Kelly is a ceiling-check, not a license.

**Sources.** Kelly (1956); Thorp (2006); MacLean, Thorp & Ziemba (2011).

## 2. Risk of ruin, drawdown control, and loss limits
*Used by: `risk-officer`, `daily-debrief`, `risk-audit`, the daily/weekly/monthly halts in `CLAUDE.md`.*

**Finding.** Drawdowns compound asymmetrically: a 50% loss requires a 100% gain to recover. Hard
loss limits and reduced size after losses are the practitioner-standard defense; they cap the left
tail at the cost of occasionally stopping out of a recoverable day.

**Effect / caveat.** Stop-trading rules have no published "alpha" — their value is in survival and
in interrupting tilt cycles (see §13), not in expectancy. A poorly placed daily limit can also
lock in losses on noise. The point is bounding ruin probability, not improving win rate.

**How this system uses it.** Fixed −2% daily / −5% weekly / −8% monthly halts, a 5%-of-equity
portfolio-heat cap, and a default-VETO risk officer. These are deliberately mechanical so they
can't be argued with in the moment.

**Sources.** Practitioner standard; see Vince (1990) on risk-of-ruin math and MacLean/Thorp/Ziemba
(2011) on growth-vs-drawdown trade-offs.

## 3. Insider transactions (Form 4)
*Used by: `insider-watcher`, `aggregate_signals.py` (`insider_cluster_buy` = 1.0, the top weight).*

**Finding.** Insider *purchases* predict modest positive abnormal returns; insider *sales* are
mostly uninformative as a group (they're dominated by diversification and liquidity motives).
Jeng, Metrick & Zeckhauser (2003) estimate purchase portfolios earn abnormal returns on the order
of ~6%/year (gross). Lakonishok & Lee (2001) find the signal concentrates in smaller firms.

**The important refinement.** Cohen, Malloy & Pomorski (2012, "Decoding Inside Information")
separate *routine* insiders (who trade on a predictable calendar) from *opportunistic* ones. The
predictive return is almost entirely in opportunistic trades (~per-month abnormal returns roughly
an order of magnitude larger than routine), and opportunistic *clusters* are the strongest cut.

**Effect / caveat.** Form 4 is filed within ~2 business days, so the signal is timely — but it is a
6-to-12-month signal, not a day-trade trigger. A single insider buy is weak; 3+ buyers in 30 days
(a cluster), especially CEO/CFO and off their routine, is the real signal.

**How this system uses it.** `insider-watcher` flags cluster buys (3+/30d) as HIGH, treats single
sells as noise, and states the ~2-day lag. The aggregator gives `insider_cluster_buy` the highest
weight (1.0) and `insider_single_buy` only 0.4.

**Sources.** Lakonishok & Lee (2001), *RFS*; Jeng, Metrick & Zeckhauser (2003), *Rev. Econ. Stat.*;
Cohen, Malloy & Pomorski (2012), *J. Finance*.

## 4. Congressional trading disclosures
*Used by: `insider-watcher`, `aggregate_signals.py` (`congress_trade` = 0.5).*

**Finding.** Ziobrowski et al. (2004) reported abnormal returns on U.S. Senators' common-stock
purchases; a 2011 companion study found weaker results for the House.

**Effect / caveat.** Later replications and the post-STOCK-Act (2012) disclosure regime have
generally *shrunk* or eliminated the measured edge, and disclosures lag the trade by up to 45 days.
This is a context input, never a trigger. Treat tracker-strategy marketing with skepticism — much
of the apparent alpha disappears after costs and after honest accounting for disclosure lag.

**How this system uses it.** `insider-watcher` surfaces congressional trades with the 45-day-lag
caveat and committee-relevance note, and the aggregator weights them at a deliberately low 0.5.
`CLAUDE.md` records the lag explicitly.

**Sources.** Ziobrowski, Cheng, Boyd & Ziobrowski (2004), *JFQA*; Ziobrowski et al. (2011),
*Business and Politics*.

## 5. Institutional ownership (13F)
*Used by: `flow-analyst`, `insider-watcher`, `aggregate_signals.py` (`filing_13f_new` = 0.3).*

**Finding.** 13F holdings carry some information — "smart money" / high-skill manager holdings have
been linked to modest outperformance (e.g., consensus-vs-contrarian and best-ideas literature).

**Effect / caveat.** 13Fs are filed up to 45 days after quarter-end, so the position you see may be
weeks stale and partly unwound. Longs only (no shorts, no intraquarter trades). This is a slow,
corroborating input, hence the low 0.3 weight and the 45-day half-life in the aggregator.

**How this system uses it.** `flow-analyst` reports new positions / big adds / exits and *always*
states the ~45-day lag. Aggregator half-life for `13f` is 45 days.

**Sources.** General 13F literature (e.g., work on hedge-fund "best ideas" and consensus holdings).
State the lag every time; do not oversell.

## 6. Volume, z-scores, and informed trading
*Used by: `flow-analyst`, `microstructure-analyst`, `scripts/unusual_volume.py`, `CLAUDE.md` z-score rules.*

**Finding.** Volume carries information about informed trading (Easley & O'Hara 1987; the PIN model
of Easley, Kiefer, O'Hara & Paperman 1996). Abnormal volume tends to precede and accompany
information events; volume + price action together is more informative than either alone.

**Effect / caveat.** Daily volume is *right-skewed and fat-tailed*, so a Gaussian z-score is a
convenient proxy, not a literal probability. A z of 2 is genuinely common (much more than the
~2.3% a normal distribution implies) because of the skew — which is exactly why the script *also*
reports a 90-day percentile rank, which makes no normality assumption.

**How this system uses it.** `unusual_volume.py` returns both a 20-day z-score and a 90-day
percentile, plus a price-volume regime label. Thresholds (z=2 notable / 3 significant / 4 extreme)
are encoded in `CLAUDE.md` and the aggregator only rewards z≥3 with the 0.7 weight. The docstring
and §-rules state that z=2 happens far more often than 5% by chance.

**Sources.** Easley & O'Hara (1987), *JFE*; Easley, Kiefer, O'Hara & Paperman (1996), *J. Finance*.

## 7. Momentum (cross-sectional and time-series)
*Used by: `market-regime-analyst`, `multi-timeframe-analyst`, the breakout `strategy_001` template.*

**Finding.** Cross-sectional momentum: past 3–12 month winners outperform past losers over the next
3–12 months (Jegadeesh & Titman 1993; the momentum factor, Carhart 1997). Time-series momentum:
an asset's own past 1–12 month return predicts its next-month return across equities, bonds,
commodities and FX (Moskowitz, Ooi & Pedersen 2012).

**Effect / caveat.** Momentum is one of the most robust documented anomalies, *but* it crashes:
Daniel & Moskowitz (2016, "Momentum Crashes") show severe, predictable losses during sharp market
rebounds following high-volatility bear markets. Momentum works until it violently doesn't — which
is why regime-conditioning and vol-scaling matter.

**How this system uses it.** `market-regime-analyst` only marks momentum/breakout strategies
SUPPORTED in trending, healthy-breadth, non-high-VIX regimes — directly addressing the crash
condition. `multi-timeframe-analyst` ranks signals that agree across timeframes higher.
`strategy_001`'s decay conditions list "VIX > 30 for 5+ days" and range-bound regimes.

**Sources.** Jegadeesh & Titman (1993), *J. Finance*; Carhart (1997), *J. Finance*; Moskowitz, Ooi
& Pedersen (2012), *JFE*; Daniel & Moskowitz (2016), *JFE*.

## 8. Short-term reversal and overreaction
*Used by: `strategy-discovery` / `strategy-researcher` when proposing mean-reversion candidates.*

**Finding.** Very short horizons (days to a week) show *reversal*: Jegadeesh (1990) and Lehmann
(1990) document weekly return reversals; De Bondt & Thaler (1985) document 3–5 year long-horizon
reversal (overreaction). So the sign of autocorrelation flips with horizon: reversal at days and
multi-year, momentum in between.

**Effect / caveat.** Short-term reversal is largely a *liquidity-provision* return — you're being
paid to absorb selling pressure — and much of it is eaten by transaction costs and is hardest to
capture exactly where it's largest (small, illiquid names). Don't confuse it with momentum.

**How this system uses it.** Reinforces that "timeframe" is a first-class parameter: the
`multi-timeframe-analyst` exists because a 5-minute signal and a weekly signal can have opposite
expected signs. Mean-reversion strategy candidates must specify the horizon and the cost
assumptions explicitly in their YAML.

**Sources.** Jegadeesh (1990), *J. Finance*; Lehmann (1990), *QJE*; De Bondt & Thaler (1985),
*J. Finance*.

## 9. Implied volatility, the variance risk premium, and option structure
*Used by: `options-strategist`, `CLAUDE.md` IV-rank rules.*

**Finding.** On average, option-implied volatility exceeds subsequently realized volatility — the
variance risk premium (Bakshi & Kapadia 2003; Carr & Wu 2009; Bollerslev, Tauchen & Zhou 2009).
Equivalently, delta-hedged option *buyers* lose on average and *sellers* are compensated for bearing
volatility/jump risk (Coval & Shumway 2001). IV also mean-reverts, so IV rank/percentile is a
useful relative gauge.

**Effect / caveat.** This is the single most dangerous "edge" for retail because its payoff is
*negatively skewed*: selling premium wins often and small, then loses rarely and catastrophically
(the 2018 "Volmageddon" short-vol blowups). The average premium is real; the path can ruin you.
Term structure (backwardation = elevated near-term event risk) and skew (expensive downside puts)
are pricing information, not free money.

**How this system uses it.** `options-strategist` computes IV rank/percentile, term structure,
skew, and straddle-implied expected move, then maps regime→structure (high IV rank → *defined-risk*
premium selling like spreads/condors, not naked; low IV rank → buy premium). `CLAUDE.md` Hard Rule
#10 forbids approving any options trade on equity-style logic alone, and the strategist must surface
post-earnings IV-crush risk in dollar terms.

**Sources.** Coval & Shumway (2001), *J. Finance*; Bakshi & Kapadia (2003), *RFS*; Carr & Wu (2009),
*RFS*; Bollerslev, Tauchen & Zhou (2009), *RFS*.

## 10. Cross-asset confirmation, credit, and volatility indices
*Used by: `cross-asset-analyst`, `daily-debrief`.*

**Finding.** Credit conditions lead the real economy and risk assets: Gilchrist & Zakrajšek (2012)
show the "excess bond premium" predicts economic activity and equity weakness. High-yield credit
(HYG) often turns before equity at risk inflections. The VIX is the option-implied 30-day S&P
volatility (Whaley 2000) and spikes coincide with risk-off; the dollar (DXY) is a headwind for
multinationals/commodities.

**Effect / caveat.** Lead-lag relationships are *unstable* — correlations that held for a decade can
invert in a regime change, and "credit leads equity by 1–3 days" is a tendency, not a clock.
Cross-asset signals are best used to *contradict* a thesis (raise caution) rather than to confirm one.

**How this system uses it.** `cross-asset-analyst` pulls SPY/QQQ/IWM/VIX/TLT/DXY/GLD/USO/HYG plus the
ticker's sector ETF, classifies risk-on/off, and returns CONFIRM/CAUTION/CONTRADICT. `CLAUDE.md`
Hard Rule #11 requires written justification to trade *against* a clear cross-asset contradiction.
The agent is required to state the "correlations break" caveat every time.

**Sources.** Whaley (2000), *J. Derivatives*; Gilchrist & Zakrajšek (2012), *AER*.

## 11. Factor exposures and hidden concentration
*Used by: `portfolio-risk-decomposer`, `risk-officer`.*

**Finding.** Cross-sectional returns load on a handful of factors — market, size, value (Fama &
French 1992/1993), momentum (Carhart 1997), profitability and investment (Fama & French 2015). A
book of "different" stocks can be one concentrated factor bet (e.g., all long-duration growth =
one rates-down bet). Correlations rise toward 1 in crises, so diversification is weakest exactly
when you need it.

**Effect / caveat.** Factor labels are noisy and time-varying; a 90-day beta is an estimate, not a
constant. The value here is *making the implicit bet explicit*, not precise factor attribution.

**How this system uses it.** `portfolio-risk-decomposer` aggregates sector weights, factor tilts,
pairwise correlation (flagging ρ>0.7 pairs as "one trade"), portfolio beta, and the *implicit macro
bet*, with a Wolfram stress test. It explicitly warns that past correlation breaks in vol spikes.

**Sources.** Fama & French (1992, 1993, 2015), *J. Finance / JFE*; Carhart (1997), *J. Finance*.

## 12. Market microstructure: spreads, impact, and intraday liquidity
*Used by: `microstructure-analyst`, `quant-builder` (cost realism), `strategy_001` (`slippage_bps`).*

**Finding.** Realized trading cost ≈ half-spread + market impact + timing risk. Almgren & Chriss
(2000) formalize the impact-vs-timing trade-off that motivates order-splitting. Intraday volume and
spreads follow a U-shape — heavy at the open and close, thin midday (Admati & Pfleiderer 1988) —
so *when* you trade changes your cost.

**Effect / caveat.** Cost is not a footnote: for short-horizon strategies it can exceed the gross
edge. Quoted spread understates true cost for larger orders (impact). Backtests that assume mid-fill
are fiction.

**How this system uses it.** `microstructure-analyst` measures spread in bps, builds an intraday
volume z-profile, gives order-routing advice (limit vs marketable, split if >1% of minute volume),
and avoids the first/last 5 minutes by default. `quant-builder` subtracts an estimated round-trip
cost from the R-multiple, and strategy YAMLs must state `slippage_bps`.

**Sources.** Admati & Pfleiderer (1988), *RFS*; Almgren & Chriss (2000), *J. Risk*.

## 13. Behavioral failure modes (the real adversary)
*Used by: `behavioral-coach`, `journal-entry`, `post-mortem`, the refusal protocols throughout.*

**Finding.** Individual investors systematically hurt themselves:
- **Overtrading.** Barber & Odean (2000) — the most active retail traders underperformed the market
  by ~6.5%/year net, almost entirely from costs. "Trading is hazardous to your wealth."
- **Overconfidence.** Barber & Odean (2001, "Boys Will Be Boys") — more trading, worse returns.
- **Disposition effect.** Odean (1998); Shefrin & Statman (1985) — investors sell winners too early
  and ride losers too long, the opposite of optimal.
- **Loss aversion.** Kahneman & Tversky (1979), prospect theory — losses hurt ~2× as much as
  equivalent gains, which drives revenge trading and stop-moving.
- **Attention-driven buying.** Barber & Odean (2008, "All That Glitters") — retail buys attention
  grabbers (big movers, high volume, news), which underperform.

**Effect / caveat.** These are among the *largest and most replicated* effects in the literature —
much bigger than most "alpha" signals — and they act against the trader, not for them. The cheapest
edge available to a retail trader is to stop doing these things.

**How this system uses it.** This is the spine of the whole tool. `behavioral-coach` reads the
journal for revenge trades (entry <60 min after a loss), averaging down, stop-moving, post-loss
size-ups, and euphoria after win streaks, with RED = veto. `journal-entry` forces emotion fields so
tilt is detectable. `post-mortem` separates clean process losses from rule-violation losses. The
disposition effect is countered by mandatory pre-entry stops/targets (Hard Rule #2).

**Sources.** Kahneman & Tversky (1979), *Econometrica*; Shefrin & Statman (1985), *J. Finance*;
Odean (1998), *J. Finance*; Barber & Odean (2000, 2001, 2008), *J. Finance / QJE / RFS*.

## 14. Social media sentiment and attention
*Used by: `social-scout`, `scan_reddit.py`, `scan_stocktwits.py`, `aggregate_signals.py` (`social_velocity_5x` = 0.4).*

**Finding.** Media/sentiment has measurable but modest, mostly *short-horizon and largely reversing*
effects. Tetlock (2007) — media pessimism predicts short-term downward pressure that reverts.
Antweiler & Frank (2004) — message-board posts mostly don't predict returns, but posting *volume*
predicts volatility. Da, Engelberg & Gao (2011, "In Search of Attention") — retail attention
(search volume) predicts short-run price pressure that later reverses.

**Effect / caveat.** Sentiment is a *crowding/attention* indicator, not a direction signal, and it
is heavily contaminated by bots and pump dynamics. Bullish unanimity is, if anything, a contrarian
flag. Public APIs are unreliable (Stocktwits has tightened access; X is largely unindexed via web
search) — empty results are themselves information.

**How this system uses it.** `social-scout` measures *velocity* and *dispersion*, flags low
account-age as possible astroturf, treats >5× velocity as a pump-risk indicator (not an entry), and
repeats in every output that sentiment alone is never a trigger. The aggregator gives social a low
weight (0.4) with the shortest half-life (3 days).

**Sources.** Antweiler & Frank (2004), *J. Finance*; Tetlock (2007), *J. Finance*; Da, Engelberg &
Gao (2011), *J. Finance*.

## 15. Backtest overfitting and strategy validation
*Used by: `strategy-researcher`, `strategy-discovery`, `quant-builder`, `risk-audit`, the YAML graduation gates.*

**Finding.** With enough trials, spurious "strategies" pass any in-sample test. Bailey, Borwein,
López de Prado & Zhu (2014) show how backtest overfitting produces out-of-sample failure and
introduce the deflated Sharpe ratio / "minimum backtest length". Harvey, Liu & Zhu (2016) raise the
significance hurdle (t≈3) given the multiple-testing problem. McLean & Pontiff (2016) show ~58%
post-publication decay in documented predictors.

**Effect / caveat.** The implication is humbling: most backtested edges are weaker live than on
paper, and many are zero. Walk-forward, out-of-sample holdout, and *honest probability that the edge
is real vs. an artifact* are not optional.

**How this system uses it.** `strategy-researcher` must give an explicit "real edge % / backtest
artifact % / already-arbed % = 100%" split for every candidate. New strategies are `paper_only`
until they clear graduation gates (≥30 trades, ≥60 days, live expectancy within 30% of backtest).
`risk-audit` runs a Monte Carlo each week and flags edge decay when live results fall below the 5th
percentile of the backtest distribution for 3 consecutive weeks.

**Sources.** Bailey, Borwein, López de Prado & Zhu (2014), *Notices of the AMS*; Harvey, Liu & Zhu
(2016), *RFS*; McLean & Pontiff (2016), *J. Finance*; López de Prado (2018), *Advances in Financial
Machine Learning*.

---

## Consolidated references

- Admati, A. & Pfleiderer, P. (1988). "A Theory of Intraday Patterns: Volume and Price Variability." *Review of Financial Studies* 1(1).
- Antweiler, W. & Frank, M. (2004). "Is All That Talk Just Noise? The Information Content of Internet Stock Message Boards." *Journal of Finance* 59(3).
- Bailey, D., Borwein, J., López de Prado, M. & Zhu, Q. (2014). "Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance." *Notices of the AMS* 61(5).
- Bakshi, G. & Kapadia, N. (2003). "Delta-Hedged Gains and the Negative Market Volatility Risk Premium." *Review of Financial Studies* 16(2).
- Barber, B. & Odean, T. (2000). "Trading Is Hazardous to Your Wealth." *Journal of Finance* 55(2).
- Barber, B. & Odean, T. (2001). "Boys Will Be Boys: Gender, Overconfidence, and Common Stock Investment." *Quarterly Journal of Economics* 116(1).
- Barber, B. & Odean, T. (2008). "All That Glitters: The Effect of Attention and News on the Buying Behavior of Individual and Institutional Investors." *Review of Financial Studies* 21(2).
- Bollerslev, T., Tauchen, G. & Zhou, H. (2009). "Expected Stock Returns and Variance Risk Premia." *Review of Financial Studies* 22(11).
- Carhart, M. (1997). "On Persistence in Mutual Fund Performance." *Journal of Finance* 52(1).
- Carr, P. & Wu, L. (2009). "Variance Risk Premiums." *Review of Financial Studies* 22(3).
- Cohen, L., Malloy, C. & Pomorski, L. (2012). "Decoding Inside Information." *Journal of Finance* 67(3).
- Coval, J. & Shumway, T. (2001). "Expected Option Returns." *Journal of Finance* 56(3).
- Da, Z., Engelberg, J. & Gao, P. (2011). "In Search of Attention." *Journal of Finance* 66(5).
- Daniel, K. & Moskowitz, T. (2016). "Momentum Crashes." *Journal of Financial Economics* 122(2).
- De Bondt, W. & Thaler, R. (1985). "Does the Stock Market Overreact?" *Journal of Finance* 40(3).
- Easley, D. & O'Hara, M. (1987). "Price, Trade Size, and Information in Securities Markets." *Journal of Financial Economics* 19(1).
- Easley, D., Kiefer, N., O'Hara, M. & Paperman, J. (1996). "Liquidity, Information, and Infrequently Traded Stocks." *Journal of Finance* 51(4).
- Fama, E. & French, K. (1993). "Common Risk Factors in the Returns on Stocks and Bonds." *Journal of Financial Economics* 33(1).
- Fama, E. & French, K. (2015). "A Five-Factor Asset Pricing Model." *Journal of Financial Economics* 116(1).
- Gilchrist, S. & Zakrajšek, E. (2012). "Credit Spreads and Business Cycle Fluctuations." *American Economic Review* 102(4).
- Harvey, C., Liu, Y. & Zhu, H. (2016). "…and the Cross-Section of Expected Returns." *Review of Financial Studies* 29(1).
- Jegadeesh, N. (1990). "Evidence of Predictable Behavior of Security Returns." *Journal of Finance* 45(3).
- Jegadeesh, N. & Titman, S. (1993). "Returns to Buying Winners and Selling Losers." *Journal of Finance* 48(1).
- Jeng, L., Metrick, A. & Zeckhauser, R. (2003). "Estimating the Returns to Insider Trading." *Review of Economics and Statistics* 85(2).
- Kahneman, D. & Tversky, A. (1979). "Prospect Theory: An Analysis of Decision under Risk." *Econometrica* 47(2).
- Kelly, J. (1956). "A New Interpretation of Information Rate." *Bell System Technical Journal* 35(4).
- Lakonishok, J. & Lee, I. (2001). "Are Insider Trades Informative?" *Review of Financial Studies* 14(1).
- Lehmann, B. (1990). "Fads, Martingales, and Market Efficiency." *Quarterly Journal of Economics* 105(1).
- López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley.
- MacLean, L., Thorp, E. & Ziemba, W. (2011). *The Kelly Capital Growth Investment Criterion*. World Scientific.
- McLean, R. & Pontiff, J. (2016). "Does Academic Research Destroy Stock Return Predictability?" *Journal of Finance* 71(1).
- Moskowitz, T., Ooi, Y. & Pedersen, L. (2012). "Time Series Momentum." *Journal of Financial Economics* 104(2).
- Odean, T. (1998). "Are Investors Reluctant to Realize Their Losses?" *Journal of Finance* 53(5).
- Shefrin, H. & Statman, M. (1985). "The Disposition to Sell Winners Too Early and Ride Losers Too Long." *Journal of Finance* 40(3).
- Tetlock, P. (2007). "Giving Content to Investor Sentiment." *Journal of Finance* 62(3).
- Thorp, E. (2006). "The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market." In *Handbook of Asset and Liability Management*.
- Vince, R. (1990). *Portfolio Management Formulas*. Wiley.
- Whaley, R. (2000). "The Investor Fear Gauge." *Journal of Portfolio Management* 26(3).
- Ziobrowski, A., Cheng, P., Boyd, J. & Ziobrowski, B. (2004). "Abnormal Returns from the Common Stock Investments of the U.S. Senate." *Journal of Financial and Quantitative Analysis* 39(4).
- Ziobrowski, A., Boyd, J., Cheng, P. & Ziobrowski, B. (2011). "Abnormal Returns from the Common Stock Investments of Members of the U.S. House of Representatives." *Business and Politics* 13(1).

---

*Not investment advice. This file documents the reasoning behind a process tool; it does not predict
prices and does not endorse any specific trade. Verify primary sources before relying on any claim.*
