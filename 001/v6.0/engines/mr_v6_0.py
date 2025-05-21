import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from datetime import datetime

PARAM_SCHEMA = {
    "base_z": 1.95,
    "step_z": 0.25,
    "drift": 0.001,
    "edge_pct": 0.15,
    "max_tix": 5
}

MA_BARS = 30
SIG_BARS = 5
ATR_BARS = 5
SIG_FLOOR = 0.00030
STOP_PIPS = 10
TIME_MIN = 30
ATR_GATE = 1.3

def backtest(df: pd.DataFrame, p: dict) -> dict:
    sma = df.close.rolling(MA_BARS, 1).mean()
    sigma = df.close.rolling(SIG_BARS, 1).std().clip(lower=SIG_FLOOR)
    z = (df.close - sma) / sigma
    prev = df.close.shift()
    tr = np.maximum(df.high - df.low, np.maximum((df.high - prev).abs(), (df.low - prev).abs()))
    atr = tr.rolling(ATR_BARS, 1).mean() * 1e4

    logs, opens = [], []
    today = None
    hi = lo = None

    for ts, row in df.iterrows():
        if row.name.date() != today:
            today = row.name.date()
            hi, lo = row.high, row.low
        hi, lo = max(hi, row.high), min(lo, row.low)
        rng = hi - lo

        still = []
        for side, ep, et, layer in opens:
            hold = (ts - et).total_seconds() / 60
            exit_flag, px, reason = False, None, None
            if side == "long":
                if row.low <= ep - STOP_PIPS/1e4: px, exit_flag, reason = ep - STOP_PIPS/1e4, True, "stop"
                elif row.close >= sma.loc[ts]:    px, exit_flag, reason = row.close, True, "mean"
                elif hold >= TIME_MIN:           px, exit_flag, reason = row.close, True, "time"
            else:
                if row.high >= ep + STOP_PIPS/1e4: px, exit_flag, reason = ep + STOP_PIPS/1e4, True, "stop"
                elif row.close <= sma.loc[ts]:     px, exit_flag, reason = row.close, True, "mean"
                elif hold >= TIME_MIN:            px, exit_flag, reason = row.close, True, "time"
            if exit_flag:
                pips = (px - ep)*1e4 if side == "long" else (ep - px)*1e4
                logs.append({"pips": pips, "entry_time": et, "exit_time": ts, "reason": reason})
            else:
                still.append((side, ep, et, layer))
        opens = still

        if len(opens) >= p["max_tix"]: continue
        if pd.isna(z.loc[ts]) or atr.loc[ts] < ATR_GATE: continue
        if abs(row.close - sma.loc[ts]) / sma.loc[ts] < p["drift"]: continue

        pos = (row.close - lo) / rng if rng else 0.5
        if z.loc[ts] > 0 and pos > (1 - p["edge_pct"]): continue
        if z.loc[ts] < 0 and pos < p["edge_pct"]: continue

        longs = sum(1 for s,_,_,_ in opens if s == "long")
        shorts = sum(1 for s,_,_,_ in opens if s == "short")
        opened = False

        if z.loc[ts] <= -p["base_z"] and not opened:
            need = p["base_z"] + p["step_z"]*longs
            if abs(z.loc[ts]) >= need:
                opens.append(("long", row.close, ts, longs+1))
                opened = True
        if z.loc[ts] >= p["base_z"] and not opened:
            need = p["base_z"] + p["step_z"]*shorts
            if abs(z.loc[ts]) >= need:
                opens.append(("short", row.close, ts, shorts+1))

    trade_log = pd.DataFrame(logs)
    pnl = trade_log["pips"]
    total = pnl.sum()
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]

    equity = pnl.cumsum()
    results_dir = os.path.join(os.path.dirname(__file__), 'results')
    os.makedirs(results_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    graph_path = os.path.join(results_dir, f"equity_curve_{timestamp}.png")

    try:
        plt.figure(figsize=(8, 3))
        equity.plot(title="Equity Curve")
        plt.tight_layout()
        plt.savefig(graph_path)
        plt.close()
    except Exception as e:
        print("Plot save failed:", e)

    return {
        "engine": os.path.abspath(__file__),
        "params": p,
        "trades": len(pnl),
        "win_%": round((pnl > 0).mean() * 100, 1),
        "total_pips": round(total, 2),
        "profit_factor": round(wins.sum() / -losses.sum(), 2) if not losses.empty else None,
        "equity_curve_path": graph_path,
        "csv": pnl.to_csv(index=False, header=False)
    }
