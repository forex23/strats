# EUR/GBP Intraday Mean-Reversion – Specification (Version **V 5.0**)

_Last updated: 2025-05-08_

## Quick context
*V 5.0 = V 4.3 + edge-zone veto.*

* **Signal** Z-score on Close.  
* **Trigger** |Z| ≥ 1.95 σ (1st ticket); +0.25 σ per already-open ticket same side (escalator).  
* **Drift filter** |Close − SMA| / SMA ≥ 0.10 %.  
* **Edge-zone veto** Block longs when close is in the **top 15 %** of today’s range; block shorts when in the **bottom 15 %**.  
* **Cap** max 5 live tickets total (long + short).

| Metric (Mar-25 2025) | **V 5.0** |
|----------------------|-----------|
| Trades | 133 |
| Win % | 78.2 % |
| Avg win / loss | 6.9 / –6.4 p |
| **Expectancy** | +3.77 p |
| Profit Factor | 3.51 |
| Sharpe (per-trade) | 6.18 |
| Max draw-down | –71 p |

---

## 1 · Data & Session  
* EUR/GBP 1-minute OHLC, **March 2025**.  
* London session **07:00 – 17:00** UK local (08-18 CET).  
* Mid-price fills (no spread/slip).

## 2 · Indicators  
| Name | Params |
|------|--------|
| 30-bar SMA | Close |
| 5-bar σ | Close, floored at 3 p |
| 5-bar ATR | TR on OHLC; **gate ≥ 1.3 p** |

## 3 · Entry logic (pseudo)  
```python
if drift ≥ 0.001  and  atr_gate  and  abs(z) ≥ 1.95 + 0.25*same_dir_open:
    pos_pct = (Close - DayLow) / (DayHigh - DayLow)
    if side == 'long' and pos_pct <= 0.85: enter_long()
    elif side == 'short' and pos_pct >= 0.15: enter_short()
```
-e 
### 🔢 Environment
- Python: 3.10.12
- pandas: 1.5.3
- numpy: 1.24.4
