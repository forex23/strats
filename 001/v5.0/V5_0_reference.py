import pandas as pd, numpy as np, datetime as dt, pathlib

# ── path to data ─────────────────────────────────────────────────────
CSV_PATH = "/home/tradeops/exports/forex_1m_Mar_2025_EURGBP.csv"   # adjusted
OUT_CSV  = f"V5_0_trades_{dt.date.today()}.csv"

# ── strategy constants ──────────────────────────────────────────────
BASE_Z     = 1.95
STEP_Z     = 0.25
DRIFT_PCT  = 0.001          # 0.10 %
EDGE_PCT   = 0.15
MAX_TIX    = 5

STOP_PIPS  = 10
TIME_MIN   = 30
MA_BARS    = 30
SIG_BARS   = 5
SIG_FLOOR  = 0.00030        # 3 p
ATR_BARS   = 5
ATR_GATE_P = 1.3            # pips
SESSION    = ("07:00", "17:00")
TZ         = "Europe/London"
WARMUP     = MA_BARS        # 30 rows per day – longest window

# ── load & warm-up slice ────────────────────────────────────────────
df = (pd.read_csv(CSV_PATH, parse_dates=["timestamp_utc"])
        .assign(timestamp_utc=lambda d: pd.to_datetime(d.timestamp_utc, utc=True))
        .set_index("timestamp_utc")
        .tz_convert(TZ)
        .between_time(*SESSION)
        [["open", "high", "low", "close"]])
df["date"] = df.index.date
# drop first 30 bars of each session so rolling windows are fully warm
df = df.groupby("date", group_keys=False).apply(lambda g: g.iloc[WARMUP:])

# ── indicators ──────────────────────────────────────────────────────
df["sma"]   = df.close.rolling(MA_BARS, min_periods=1).mean()
sig         = df.close.rolling(SIG_BARS, min_periods=1).std()
df["sigma"] = sig.clip(lower=SIG_FLOOR)
df["z"]     = (df.close - df.sma) / df.sigma

prev        = df.close.shift()
tr          = np.maximum(df.high-df.low,
                         np.maximum((df.high-prev).abs(), (df.low-prev).abs()))
df["atr"]   = tr.rolling(ATR_BARS, min_periods=1).mean()
df["vol_ok"]= df.atr * 1e4 >= ATR_GATE_P

# ── back-test loop ──────────────────────────────────────────────────
trades, opens = [], []
hi = lo = None
today = None

for ts, row in df.iterrows():
    if row.date != today:               # new session
        today = row.date
        hi, lo = row.high, row.low

    # update session range
    hi = max(hi, row.high)
    lo = min(lo, row.low)
    rng = hi - lo

    # exits
    still = []
    for side, ep, et, layer in opens:
        hold = (ts - et).total_seconds() / 60
        exit_flag = False
        px = None
        if side == "long":
            if row.low  <= ep - STOP_PIPS/1e4: px, exit_flag = ep - STOP_PIPS/1e4, True
            elif row.close >= row.sma:         px, exit_flag = row.close, True
            elif hold >= TIME_MIN:            px, exit_flag = row.close, True
        else:
            if row.high >= ep + STOP_PIPS/1e4: px, exit_flag = ep + STOP_PIPS/1e4, True
            elif row.close <= row.sma:         px, exit_flag = row.close, True
            elif hold >= TIME_MIN:            px, exit_flag = row.close, True
        if exit_flag:
            pips = (px - ep) * 1e4 if side == "long" else (ep - px) * 1e4
            trades.append(pips)
        else:
            still.append((side, ep, et, layer))
    opens = still

    # --- entry guards (one ticket max per bar) ----------------------
    opened_this_bar = False
    if (len(opens) >= MAX_TIX) or (not row.vol_ok) or pd.isna(row.z):
        continue
    if abs(row.close - row.sma) / row.sma < DRIFT_PCT:
        continue

    pos_pct     = (row.close - lo) / rng if rng else 0.5
    long_block  = pos_pct > (1 - EDGE_PCT)
    short_block = pos_pct < EDGE_PCT

    longs  = sum(1 for s,_,_,_ in opens if s == "long")
    shorts = sum(1 for s,_,_,_ in opens if s == "short")

    # check long first, then short – ensures “one ticket per bar”
    if row.z <= -BASE_Z and not opened_this_bar:
        need = BASE_Z + STEP_Z * longs
        if abs(row.z) >= need and not short_block:
            opens.append(("long", row.close, ts, longs+1))
            opened_this_bar = True

    if row.z >= BASE_Z and not opened_this_bar:
        need = BASE_Z + STEP_Z * shorts
        if abs(row.z) >= need and not long_block:
            opens.append(("short", row.close, ts, shorts+1))

# ── summary & save ---------------------------------------------------
pips   = pd.Series(trades, name="pips")
wins   = (pips > 0).sum()
pf     = pips[pips > 0].sum() / -pips[pips < 0].sum()
eq     = pips.cumsum(); dd = (eq.cummax() - eq).max()

print(f"V5.0 – trades {len(pips)}, win {wins/len(pips):.2%}, PF {pf:.2f}, DD –{dd:.0f} p")
pips.to_csv(OUT_CSV, index=False, header=False)
