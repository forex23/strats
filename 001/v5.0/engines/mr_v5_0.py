# mr_v5_0.py  –  Mean-Reversion engine (V 5.0 baseline)
# -----------------------------------------------------
# Exports:
#   PARAM_SCHEMA  – dict describing tunable params + defaults
#   backtest(df, params) -> pd.Series  (one pip value per closed ticket)
#
# df must already be:
#   • tz-aware, Europe/London, minute bars
#   • sliced to 07:00-17:00 session
#   • AFTER removing the first 30 warm-up rows of each day
#   • contain cols: open, high, low, close
# -----------------------------------------------------
import pandas as pd
import numpy as np

# ----- public schema ---------------------------------
PARAM_SCHEMA = {
    "base_z"   : {"type": "float", "default": 1.95},
    "step_z"   : {"type": "float", "default": 0.25},
    "drift"    : {"type": "float", "default": 0.001},     # 0.10 %
    "edge_pct" : {"type": "float", "default": 0.15},      # 15 %
    "max_tix"  : {"type": "int",   "default": 5},
}

# ----- fixed constants (V 5.0) -----------------------
MA_BARS   = 30
SIG_BARS  = 5
ATR_BARS  = 5
SIG_FLOOR = 0.00030     # 3 p
STOP_PIPS = 10          # hard stop
TIME_MIN  = 30          # time stop (min)
ATR_GATE  = 1.3         # pips

# -----------------------------------------------------
def backtest(df: pd.DataFrame, p: dict) -> pd.Series:
    """Pure function – no external I/O."""
    # -- indicators --
    sma   = df.close.rolling(MA_BARS, 1).mean()
    sigma = df.close.rolling(SIG_BARS, 1).std().clip(lower=SIG_FLOOR)
    z     = (df.close - sma) / sigma
    prev  = df.close.shift()
    tr    = np.maximum(df.high - df.low,
                       np.maximum((df.high - prev).abs(),
                                  (df.low  - prev).abs()))
    atr   = tr.rolling(ATR_BARS, 1).mean() * 1e4  # pips

    trades, opens = [], []
    today = None
    hi = lo = None

    print("BACKTEST START:", df.index[:5], df.columns.tolist())
    for ts, row in df.iterrows():
        # new session range reset
        if row.name.date() != today:
            today = row.name.date()
            hi, lo = row.high, row.low
        hi, lo = max(hi, row.high), min(lo, row.low)
        rng = hi - lo

        # ---- exits ----
        still = []
        for side, ep, et, layer in opens:
            hold = (ts - et).total_seconds() / 60
            exit_flag = False; px = None
            if side == "long":
                if row.low  <= ep - STOP_PIPS/1e4: px, exit_flag = ep - STOP_PIPS/1e4, True
                elif row.close >= sma.loc[ts]:     px, exit_flag = row.close, True
                elif hold >= TIME_MIN:            px, exit_flag = row.close, True
            else:
                if row.high >= ep + STOP_PIPS/1e4: px, exit_flag = ep + STOP_PIPS/1e4, True
                elif row.close <= sma.loc[ts]:     px, exit_flag = row.close, True
                elif hold >= TIME_MIN:            px, exit_flag = row.close, True
            if exit_flag:
                pips = (px - ep)*1e4 if side == "long" else (ep - px)*1e4
                trades.append(pips)
            else:
                still.append((side, ep, et, layer))
        opens = still

        # ---- entry guards ----
        if len(opens) >= p["max_tix"]:                   continue
        if pd.isna(z.loc[ts]) or atr.loc[ts] < ATR_GATE: continue
        if abs(row.close - sma.loc[ts]) / sma.loc[ts] < p["drift"]: continue

        pos = (row.close - lo) / rng if rng else 0.5
        if z.loc[ts] > 0 and pos > (1 - p["edge_pct"]): continue  # long blocked high
        if z.loc[ts] < 0 and pos < p["edge_pct"]:       continue  # short blocked low

        longs  = sum(1 for s,_,_,_ in opens if s == "long")
        shorts = sum(1 for s,_,_,_ in opens if s == "short")

        opened = False
        if z.loc[ts] <= -p["base_z"] and not opened:
            need = p["base_z"] + p["step_z"]*longs
            if abs(z.loc[ts]) >= need:
                opens.append(("long", row.close, ts, longs+1))
                opened = True
        if z.loc[ts] >=  p["base_z"] and not opened:
            need = p["base_z"] + p["step_z"]*shorts
            if abs(z.loc[ts]) >= need:
                opens.append(("short", row.close, ts, shorts+1))

    return pd.Series(trades, name="pips")
