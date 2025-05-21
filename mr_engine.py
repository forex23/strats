# mr_engine.py
# Pure-Python mean-reversion back-test core
# -----------------------------------------------------------
import pandas as pd
import numpy as np

# ---- strategy-wide constants (hard-coded for clarity) -----
MA_BARS   = 30
SIG_BARS  = 5
ATR_BARS  = 5
SIG_FLOOR = 0.00030           # 3 p
STOP_PIPS = 10                # hard stop (10 p)
TIME_MIN  = 30                # time stop (minutes)
ATR_GATE  = 1.3               # pips

# -----------------------------------------------------------
def run_backtest(df: pd.DataFrame, cfg: dict) -> pd.Series:
    """
    Stateless back-test engine.

    df   : minute bars (tz-aware, 07:00–17:00 session, *no* warm-up rows)
           must contain columns open, high, low, close
    cfg  : {
             base_z   : float (e.g. 1.95),
             step_z   : float (e.g. 0.25),
             drift    : float (e.g. 0.001),
             edge_pct : float (e.g. 0.15),
             ticket_cap  : int   (e.g. 5)
           }

    Returns:
        pd.Series of pips for each closed trade.
    """
    df['timestamp_utc'] = pd.to_datetime(df['timestamp_utc'], utc=True, errors='coerce')
    df = df.set_index('timestamp_utc')
    df = df.dropna(subset=['open', 'high', 'low', 'close'])  # defensive

    # ---- indicators (vectorised) --------------------------
    sma   = df.close.rolling(MA_BARS, 1).mean()
    sigma = df.close.rolling(SIG_BARS, 1).std().clip(lower=SIG_FLOOR)
    z     = (df.close - sma) / sigma

    prev  = df.close.shift()
    tr    = np.maximum(df.high - df.low,
                       np.maximum((df.high - prev).abs(),
                                  (df.low  - prev).abs()))
    atr   = tr.rolling(ATR_BARS, 1).mean()*1e4

    # ---- main loop ----------------------------------------
    trades, opens = [], []
    today = None
    hi = lo = None

    for ts, row in df.iterrows():
        if row.name.date() != today:
            today = row.name.date()
            hi, lo = row.high, row.low

        hi = max(hi, row.high)
        lo = min(lo, row.low)
        rng = hi - lo

        # ---- exits ----------------------------------------
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

        # ---- entry guards ---------------------------------
        if len(opens) >= cfg["ticket_cap"]:
            continue
        if pd.isna(z.loc[ts]) or atr.loc[ts] < ATR_GATE:
            continue
        if abs(row.close - sma.loc[ts]) / sma.loc[ts] < cfg["drift"]:
            continue

        pos   = (row.close - lo) / rng if rng else 0.5
        if  row.z > 0 and pos > (1 - cfg["edge_pct"]): continue  # long blocked high
        if  row.z < 0 and pos < cfg["edge_pct"]:       continue  # short blocked low

        longs  = sum(1 for s,_,_,_ in opens if s == "long")
        shorts = sum(1 for s,_,_,_ in opens if s == "short")

        opened = False
        if z.loc[ts] <= -cfg["base_z"] and not opened:
            need = cfg["base_z"] + cfg["step_z"]*longs
            if abs(z.loc[ts]) >= need:
                opens.append(("long", row.close, ts, longs+1))
                opened = True
        if z.loc[ts] >=  cfg["base_z"] and not opened:
            need = cfg["base_z"] + cfg["step_z"]*shorts
            if abs(z.loc[ts]) >= need:
                opens.append(("short", row.close, ts, shorts+1))

    import math

    pips = pd.Series(trades, name="pips")
    win = round((pips > 0).mean() * 100, 2)
    gain = pips[pips > 0].sum()
    loss = -pips[pips < 0].sum()
    pf = gain / loss if loss > 0 else None
    exp = pips.mean()

    stats = {
        "win_rate": win,
        "profit_factor": round(pf, 2) if pf is not None and math.isfinite(pf) else None,
        "total_pips": round(pips.sum(), 2),
        "expectancy": round(exp, 2) if math.isfinite(exp) else None
    }
    return pips, stats
