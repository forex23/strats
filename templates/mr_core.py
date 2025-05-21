# templates/mr_core.py  –  σ-Mean-Reversion template (v1.0-clean)
# ---------------------------------------------------------------
# Exported artifacts
#   PARAM_SCHEMA        : Tunables + defaults
#   run_backtest(df, cfg) -> (trade_log_df, equity_list)
#
# df expectations
#   • tz-aware minute bars, already sliced to session (07:00-17:00 UK)
#   • columns: open, high, low, close
#   • FIRST 30 warm-up rows per day removed
#
# trade_log DataFrame cols  (all UTC)
#   pips · entry_time · exit_time · side · reason · layer
# equity_list            (for PNG builder / chart)
#   [{'ts': "2025-03-01T08:31:00Z", 'equity': 12.3}, …]
# ---------------------------------------------------------------

from __future__ import annotations
import pandas as pd, numpy as np
from typing import List, Dict

# ---- tunable schema ---------------------------------------------------------
PARAM_SCHEMA: Dict[str, Dict[str, object]] = {
    "base_z"   : {"type": "float", "default": 1.95},
    "step_z"   : {"type": "float", "default": 0.25},
    "drift"    : {"type": "float", "default": 0.001},   # 0.10 %
    "edge_pct" : {"type": "float", "default": 0.15},    # 15 %
    "ticket_cap": {"type": "int",  "default": 5},
    # ► room for future params (ATR_GATE, stop_pips…) ◄
}

# ---- strategy constants (hard-wired for v1.0) -------------------------------
MA_BARS   = 30
SIG_BARS  = 5
ATR_BARS  = 5
SIG_FLOOR = 0.00030      # 3 p
STOP_PIPS = 10           # hard stop
TIME_MIN  = 30           # time stop (minutes)
ATR_GATE  = 1.3          # pips

# -----------------------------------------------------------------------------
def run_backtest(df: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, List[dict]]:
    """Stateless σ-MR core.

    Returns:
        trade_log : DataFrame (pips, entry_time, exit_time, side, reason, layer)
        equity    : list[dict] (ts, equity)
    """
    # ── optional session slice ───────────────────────────────────────────
    session = cfg.get("session")          # e.g. ("07:00","17:00") or None
    if session:
        lo, hi = session
        df = df.between_time(lo, hi)




    # ---- indicators ---------------------------------------------------------
    sma   = df.close.rolling(MA_BARS, 1).mean()
    sigma = df.close.rolling(SIG_BARS, 1).std().clip(lower=SIG_FLOOR)
    z     = (df.close - sma) / sigma
    df['z'] = z  # so row.z is usable below

    prev  = df.close.shift()
    tr    = np.maximum(df.high - df.low,
                       np.maximum((df.high - prev).abs(),
                                  (df.low  - prev).abs()))
    atr   = tr.rolling(ATR_BARS, 1).mean() * 1e4  # pips

    # ---- main loop ----------------------------------------------------------
    opens = []                       # [(side, entry_px, entry_ts, layer)]
    log_rows = []                    # append dict per closed trade
    today = hi = lo = None

    for ts, row in df.iterrows():
        # session-day reset
        if ts.date() != today:
            today, hi, lo = ts.date(), row.high, row.low
        hi, lo = max(hi, row.high), min(lo, row.low)
        rng = hi - lo

        # ---- check exits ----------------------------------------------------
        still = []
        for side, ep, et, layer in opens:
            hold = (ts - et).total_seconds() / 60
            exit_flag = False; px = None; reason = None
            if side == "long":
                if row.low  <= ep - STOP_PIPS/1e4: px, exit_flag, reason = ep - STOP_PIPS/1e4, True, "stop"
                elif row.close >= sma.loc[ts]:     px, exit_flag, reason = row.close, True, "mean"
                elif hold >= TIME_MIN:            px, exit_flag, reason = row.close, True, "time"
            else:
                if row.high >= ep + STOP_PIPS/1e4: px, exit_flag, reason = ep + STOP_PIPS/1e4, True, "stop"
                elif row.close <= sma.loc[ts]:     px, exit_flag, reason = row.close, True, "mean"
                elif hold >= TIME_MIN:            px, exit_flag, reason = row.close, True, "time"
            if exit_flag:
                pips = (px - ep)*1e4 if side == "long" else (ep - px)*1e4
                log_rows.append({
                    "pips":       pips,
                    "entry_time": et,
                    "exit_time":  ts,
                    "side":       side,
                    "reason":     reason,
                    "layer":      layer
                })
            else:
                still.append((side, ep, et, layer))
        opens = still

        # ---- entry guards ---------------------------------------------------
        if len(opens) >= cfg["ticket_cap"]:                 continue
        if pd.isna(row.z) or atr.loc[ts] < ATR_GATE:        continue
        if abs(row.close - sma.loc[ts]) / sma.loc[ts] < cfg["drift"]: continue

        pos = (row.close - lo) / rng if rng else 0.5
        if row.z > 0 and pos > (1 - cfg["edge_pct"]): continue  # high of range
        if row.z < 0 and pos < cfg["edge_pct"]:       continue  # low  of range

        longs  = sum(1 for s,_,_,_ in opens if s == "long")
        shorts = sum(1 for s,_,_,_ in opens if s == "short")

        # ---- entries --------------------------------------------------------
        if row.z <= -cfg["base_z"]:
            need = cfg["base_z"] + cfg["step_z"]*longs
            if abs(row.z) >= need:
                opens.append(("long", row.close, ts, longs+1))
        elif row.z >= cfg["base_z"]:
            need = cfg["base_z"] + cfg["step_z"]*shorts
            if abs(row.z) >= need:
                opens.append(("short", row.close, ts, shorts+1))

    # ---- equity construction ----------------------------------------------
    bal = 0
    equity = []
    for row in log_rows:
        bal += row["pips"]
        equity.append({"ts": row["exit_time"].isoformat(), "equity": bal})

    trade_log = pd.DataFrame(log_rows)
    return trade_log, equity
