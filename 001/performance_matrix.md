# EUR/GBP Mean-Reversion – Strat 001 Version Matrix (Mar 2025)

| Item                     | V 1.0   | V 1.1   | V 1.2   | V 2.0   | V 3.0   | V 4.3   | V 5.0   |
|--------------------------|---------|---------|---------|---------|---------|---------|---------|
| **RESULTS (Mar-25)**     |         |         |         |         |         |         |         |
| Trades                  | 2 442   | 34      | 279     | 675     | 675     | 174     | 133     |
| Win rate                | 70 %    | 53 %    | 67 %    | 71 %    | 71 %    | 74 %    | 78 %    |
| Avg win / loss (p)      | 4.2 / –6.2 | 6.5 / –8.7 | 6.3 / –7.1 | 5.1 / –6.7 | 5.1 / –6.7 | 6.5 / –6.6 | 6.9 / –6.4 |
| Expectancy (p)          | +1.15   | –0.66   | +1.90   | +1.62   | +1.62   | +3.09   | +3.77   |
| Net P/L (p)             | +2 800  | –23     | +530    | +1 094  | +1 094  | ≈ +538  | ≈ +502  |
| Profit factor           | 1.64    | 0.84    | 1.82    | 1.80    | 1.80    | 2.62    | 3.51    |
| Sharpe (per-tr)         | 9.76*   | –0.44   | 4.28    | 0.70    | 0.70    | 5.48    | 6.18    |
| Max DD (p)              | –596    | –110    | –290    | –274    | –274    | –102    | –71     |
| Hard-stops (# / %)      | 340 / 14 % | 12 / 35 % | 50 / 18 % | 102 / 15 % | 102 / 15 % | 21 / 12 % | 12 / 9 % |
| Peak tickets            | 28      | 12      | 25      | 7       | 7       | 5       | 5       |

| **SETTINGS (active knobs)** |      |         |         |         |         |         |         |
| Base \|Z\| trigger       | ±1.25σ | ±1.25σ | ±1.25σ | ±2.0σ  | ±2.0σ  | ±1.95σ | ±1.95σ |
| Escalator step σ         | —       | —       | —       | —       | —       | +0.25   | +0.25   |
| Drift gate %             | —       | 0.20    | 0.10    | —       | —       | 0.10    | 0.10    |
| Edge-zone veto           | —       | —       | —       | —       | —       | —       | ±15 %   |
| Ticket cap               | ∞       | ∞       | ∞       | ∞       | ∞       | 5       | 5       |
| Stop distance            | 10 p    | 10 p    | 10 p    | 10 p    | 10 p    | 10 p    | 10 p    |
| Time-stop                | 30 min  | 30 min  | 30 min  | 30 min  | 30 min  | 30 min  | 30 min  |
| Take-profit              | 30-bar SMA | same  | same    | same    | same    | same    | same    |
| Session hours            | 07–17 UK | same   | same    | same    | same    | same    | same    |

| **— future toggles —**   |         |         |         |         |         |         |         |
| Size taper by layer      | N/A     | N/A     | N/A     | N/A     | N/A     | idea    | idea    |
| Range-ramp sizing 1→2×   | N/A     | N/A     | N/A     | N/A     | N/A     | idea    | idea    |
| Time-bucket sizing       | N/A     | N/A     | N/A     | N/A     | N/A     | idea    | idea    |
| Cost model (spread+slip) | N/A     | N/A     | N/A     | N/A     | N/A     | N/A     | N/A     |
| News blackout            | N/A     | N/A     | N/A     | N/A     | N/A     | N/A     | N/A     |
| Synthetic-gap filter     | N/A     | N/A     | N/A     | N/A     | N/A     | N/A     | N/A     |
| Volatility shut-off      | N/A     | N/A     | N/A     | N/A     | N/A     | N/A     | N/A     |
| Daily P/L guard          | N/A     | N/A     | N/A     | N/A     | N/A     | N/A     | N/A     |
| Tick-driven entries      | N/A     | N/A     | N/A     | N/A     | N/A     | N/A     | N/A     |

\* Sharpe in V1.0 inflated by thousands of tiny zero-cost trades.
