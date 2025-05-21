"""
Mean-reversion engine v6.02 – fresh build on new metrics stub.
Changes vs v6.01:
  • uses generate_backtest_output() for all stats
  • explicit equity tracking
  • code comments tidied
"""

# --- shim so backtest_wrapper.py can call this version -----------------
CFG = {               # defaults used when wrapper calls run_backtest(df)
    "base_z":   1.95,
    "step_z":   0.25,
    "drift":    0.001,
    "edge_pct": 0.15,
    "max_tix":  5,
    "stop_pips": 10,
    "time_min": 30,
}

def run_backtest(df, cfg=None):
    cfg = cfg or CFG.copy()
    return backtest(df, cfg)
# -----------------------------------------------------------------------

import pandas as pd, numpy as np, os
from datetime import datetime
from applications.metrics import generate_backtest_output    # local copy

PARAM_SCHEMA = {
    "base_z":   {"type": "float", "default": 1.95},
    "step_z":   {"type": "float", "default": 0.25},
    "drift":    {"type": "float", "default": 0.001},
    "edge_pct": {"type": "float", "default": 0.15},
    "max_tix":  {"type": "int",   "default": 5},
    "stop_pips": {"type": "int",  "default": 10},
    "time_min":  {"type": "int",  "default": 30},
}

MA_BARS   = 30
SIG_BARS  = 5
ATR_BARS  = 5
SIG_FLOOR = 0.00030
ATR_GATE  = 1.3

def backtest(df: pd.DataFrame, p: dict) -> dict:
    sma   = df.close.rolling(MA_BARS, 1).mean()
    sigma = df.close.rolling(SIG_BARS, 1).std().clip(lower=SIG_FLOOR)
    z     = (df.close - sma) / sigma
    prev  = df.close.shift()
    tr    = np.maximum(df.high - df.low,
            np.maximum((df.high - prev).abs(), (df.low - prev).abs()))
    atr   = tr.rolling(ATR_BARS, 1).mean() * 1e4

    logs, opens, eq_curve = [], [], []
    eq = 0
    hi = lo = None
    today = None

    for ts, row in df.iterrows():
        # reset daily hi/lo
        if ts.date() != today:
            today, hi, lo = ts.date(), row.high, row.low
        hi, lo = max(hi, row.high), min(lo, row.low)
        rng = hi - lo

        # manage open trades
        still = []
        for side, ep, et, layer in opens:
            hold = (ts - et).total_seconds() / 60
            exit_flag, px, reason = False, None, None

            stop = p["stop_pips"] / 1e4
            if side == "long":
                if row.low  <= ep - stop:  px, exit_flag, reason = ep - stop, True, "stop"
                elif row.close >= sma.loc[ts]: px, exit_flag, reason = row.close, True, "mean"
                elif hold >= p["time_min"]:   px, exit_flag, reason = row.close, True, "time"
            else:
                if row.high >= ep + stop: px, exit_flag, reason = ep + stop, True, "stop"
                elif row.close <= sma.loc[ts]: px, exit_flag, reason = row.close, True, "mean"
                elif hold >= p["time_min"]:   px, exit_flag, reason = row.close, True, "time"

            if exit_flag:
                pips = (px - ep)*1e4 if side == "long" else (ep - px)*1e4
                eq  += pips
                logs.append({
                    "pips": pips,
                    "entry_time": et,
                    "exit_time": ts,
                    "reason": reason
                })
                eq_curve.append({"ts": ts.isoformat(), "equity": eq})
            else:
                still.append((side, ep, et, layer))
        opens = still

        # entry filters
        if len(opens) >= p["max_tix"]: continue
        if pd.isna(z.loc[ts]) or atr.loc[ts] < ATR_GATE: continue
        if abs(row.close - sma.loc[ts]) / sma.loc[ts] < p["drift"]: continue

        pos = (row.close - lo) / rng if rng else 0.5
        if z.loc[ts] > 0 and pos > (1 - p["edge_pct"]): continue
        if z.loc[ts] < 0 and pos < p["edge_pct"]: continue

        longs  = sum(1 for s,_,_,_ in opens if s == "long")
        shorts = sum(1 for s,_,_,_ in opens if s == "short")

        if z.loc[ts] <= -p["base_z"]:
            need = p["base_z"] + p["step_z"]*longs
            if abs(z.loc[ts]) >= need:
                opens.append(("long", row.close, ts, longs+1))
        elif z.loc[ts] >= p["base_z"]:
            need = p["base_z"] + p["step_z"]*shorts
            if abs(z.loc[ts]) >= need:
                opens.append(("short", row.close, ts, shorts+1))

    trade_log = pd.DataFrame(logs)
    return trade_log, eq_curve        # wrapper builds metrics later
