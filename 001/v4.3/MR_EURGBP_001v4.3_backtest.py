# --- EUR/GBP 1-minute mean-reversion back-tester (V 4.3) -------------
# Requires: pandas, numpy
import pandas as pd, numpy as np
from pathlib import Path

# ---------- CONFIG ---------------------------------------------------
CONFIG = dict(
    csv_path      = "/home/tradeops/exports/forex_1m_Mar_2025_EURGBP.csv",
    session_open  = "07:00",          # UK local
    session_close = "17:00",
    base_z        = 1.95,             # first-layer trigger
    step_z        = 0.25,             # add-on per open ticket same dir
    drift_gate    = 0.001,            # 0.10 % of SMA
    max_tickets   = 5,
    edge_pct      = 0.15,             # 15 % edge-zone veto
    ma_bars       = 30,
    sigma_bars    = 5,
    sigma_floor_p = 3,
    atr_bars      = 5,
    atr_gate_pips = 1.3,
    hard_stop_p   = 10,
    time_stop_min = 30,
    tz_local      = "Europe/London",
)

# ---------- Load & preprocess ---------------------------------------
df = (pd.read_csv(CONFIG["csv_path"], parse_dates=["timestamp_utc"])
        .assign(timestamp_utc=lambda d: pd.to_datetime(d.timestamp_utc, utc=True))
        .set_index("timestamp_utc")
        .tz_convert(CONFIG["tz_local"])
        .between_time(CONFIG["session_open"], CONFIG["session_close"])
        [["open","high","low","close"]])

df["date"] = df.index.date
df["sma"]  = df["close"].rolling(CONFIG["ma_bars"], min_periods=CONFIG["ma_bars"]).mean()
sig = df["close"].rolling(CONFIG["sigma_bars"], min_periods=CONFIG["sigma_bars"]).std()
df["sigma"] = sig.clip(lower=CONFIG["sigma_floor_p"] / 10000)
df["z"]     = (df["close"] - df["sma"]) / df["sigma"]

# ATR gate
prev = df["close"].shift()
tr = np.maximum(df["high"]-df["low"],
                np.maximum((df["high"]-prev).abs(), (df["low"]-prev).abs()))
df["atr5"]   = tr.rolling(CONFIG["atr_bars"], min_periods=CONFIG["atr_bars"]).mean()
df["vol_ok"] = df["atr5"] * 1e4 >= CONFIG["atr_gate_pips"]

# ---------- Back-test loop ------------------------------------------
trades, open_pos = [], []
cur_date, hi, lo = None, None, None

for ts, row in df.iterrows():
    if cur_date != row["date"]:
        cur_date = row["date"]; hi = row["high"]; lo = row["low"]
    hi = max(hi, row["high"]); lo = min(lo, row["low"]); rng = hi - lo

    # ---------- exits
    still = []
    for side, entry, etime, layer in open_pos:
        hold = (ts - etime).total_seconds() / 60
        exit_flag, ex_price = False, None
        if side == "long":
            if row["low"] <= entry - CONFIG["hard_stop_p"] / 1e4:
                exit_flag, ex_price = True, entry - CONFIG["hard_stop_p"]/1e4
            elif row["close"] >= row["sma"]:
                exit_flag, ex_price = True, row["close"]
            elif hold >= CONFIG["time_stop_min"]:
                exit_flag, ex_price = True, row["close"]
        else:
            if row["high"] >= entry + CONFIG["hard_stop_p"] / 1e4:
                exit_flag, ex_price = True, entry + CONFIG["hard_stop_p"]/1e4
            elif row["close"] <= row["sma"]:
                exit_flag, ex_price = True, row["close"]
            elif hold >= CONFIG["time_stop_min"]:
                exit_flag, ex_price = True, row["close"]

        if exit_flag:
            pips = (ex_price-entry)*1e4 if side=="long" else (entry-ex_price)*1e4
            trades.append({"timestamp": ts, "layer": layer, "side": side, "pips": pips})
        else:
            still.append((side, entry, etime, layer))
    open_pos = still

    # ---------- new entry?
    if (len(open_pos) >= CONFIG["max_tickets"] or not row["vol_ok"]
        or pd.isna(row["z"])):
        continue
    drift_ok = abs(row["close"] - row["sma"]) / row["sma"] >= CONFIG["drift_gate"]
    if not drift_ok:
        continue

    pos_pct = (row["close"] - lo) / rng if rng else 0.5
    long_block  = pos_pct > (1 - CONFIG["edge_pct"])
    short_block = pos_pct < CONFIG["edge_pct"]

    longs = sum(1 for s,_,_,_ in open_pos if s=="long")
    shorts= sum(1 for s,_,_,_ in open_pos if s=="short")

    if row["z"] <= -CONFIG["base_z"]:
        needed = CONFIG["base_z"] + CONFIG["step_z"] * longs
        if abs(row["z"]) >= needed and not short_block:
            open_pos.append(("long", row["close"], ts, longs+1))
    elif row["z"] >= CONFIG["base_z"]:
        needed = CONFIG["base_z"] + CONFIG["step_z"] * shorts
        if abs(row["z"]) >= needed and not long_block:
            open_pos.append(("short", row["close"], ts, shorts+1))

# ---------- Summary by hour -----------------------------------------
trades_df = pd.DataFrame(trades)
trades_df["hour"] = pd.to_datetime(trades_df["timestamp"]).dt.hour
hourly = (trades_df.groupby("hour")
          .agg(trades=("pips","size"),
               wins   =("pips", lambda p: (p>0).sum()),
               win_rate=("pips", lambda p: round((p>0).mean()*100,1)),
               avg_win=("pips", lambda p: p[p>0].mean()),
               avg_loss=("pips", lambda p: p[p<0].mean()),
               expectancy=("pips","mean"))
          .reset_index())

print(hourly.to_string(index=False))
