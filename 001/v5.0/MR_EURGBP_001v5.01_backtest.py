import pandas as pd, numpy as np, datetime as dt, pathlib

PATHS = [
    "/home/tradeops/ChatGPT_Memory/forex_1m_2025-02-28_EURGBP.csv",
    "/home/tradeops/ChatGPT_Memory/forex_1m_EURGBP_fragments_2025-02-28_and_03-02.csv",
    "/home/tradeops/ChatGPT_Memory/forex_1m_EURGBP_2025-03-02T22_to_2025-03-03T07.csv",
    "/home/tradeops/ChatGPT_Memory/forex_1m_EURGBP_fragments_FriMonWarmup.csv",
    "/home/tradeops/ChatGPT_Memory/forex_1m_EURGBP_2025-02-28T1701_to_2025-03-02T2359.csv",
    "/home/tradeops/exports/forex_1m_Mar_2025_EURGBP.csv"
]

def load_csv(path):
    df = pd.read_csv(path)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")
    return df.dropna(subset=["timestamp_utc"])

raw = pd.concat([load_csv(p) for p in PATHS])
raw = raw.drop_duplicates("timestamp_utc").sort_values("timestamp_utc").reset_index(drop=True)

TZ = "Europe/London"
SESSION = ("07:00", "17:00")
MA_BARS = 30
SIG_BARS = 5
ATR_BARS = 5
WARMUP = 30
SIG_FLOOR = 0.00030

BASE_Z = 1.95
STEP_Z = 0.25
DRIFT_PCT = 0.001
EDGE_PCT = 0.15
MAX_TIX = 5

STOP_PIPS = 10
TIME_MIN = 30
ATR_GATE_P = 1.3

df = raw.set_index("timestamp_utc").tz_convert(TZ).between_time(*SESSION)[["open","high","low","close"]]
df["date"] = df.index.date
df = df.groupby("date", group_keys=False).apply(lambda g: g.iloc[WARMUP:])

df["sma"]   = df.close.rolling(MA_BARS, min_periods=1).mean()
df["sigma"] = df.close.rolling(SIG_BARS, min_periods=1).std().clip(lower=SIG_FLOOR)
df["z"]     = (df.close - df.sma) / df.sigma
prev        = df.close.shift()
tr          = np.maximum(df.high - df.low, np.maximum((df.high - prev).abs(), (df.low - prev).abs()))
df["atr"]   = tr.rolling(ATR_BARS, min_periods=1).mean()
df["vol_ok"] = df.atr * 1e4 >= ATR_GATE_P

trades, opens = [], []
today, hi, lo = None, None, None

for ts, row in df.iterrows():
    if row.date != today:
        today = row.date
        hi, lo = row.high, row.low

    hi = max(hi, row.high)
    lo = min(lo, row.low)
    rng = hi - lo

    still = []
    for side, ep, et, layer in opens:
        hold = (ts - et).total_seconds() / 60
        exit_flag = False
        px = None
        if side == "long":
            if row.low <= ep - STOP_PIPS / 1e4: px, exit_flag = ep - STOP_PIPS / 1e4, True
            elif row.close >= row.sma:         px, exit_flag = row.close, True
            elif hold >= TIME_MIN:             px, exit_flag = row.close, True
        else:
            if row.high >= ep + STOP_PIPS / 1e4: px, exit_flag = ep + STOP_PIPS / 1e4, True
            elif row.close <= row.sma:         px, exit_flag = row.close, True
            elif hold >= TIME_MIN:             px, exit_flag = row.close, True
        if exit_flag:
            pips = (px - ep)*1e4 if side == "long" else (ep - px)*1e4
            trades.append({"timestamp_uk": ts, "side": side, "layer": layer,
                           "entry": ep, "exit": px, "pips": pips,
                           "open": row.open, "high": row.high,
                           "low": row.low, "close": row.close})
        else:
            still.append((side, ep, et, layer))
    opens = still

    if len(opens) >= MAX_TIX or not row.vol_ok or pd.isna(row.z): continue
    if abs(row.close - row.sma) / row.sma < DRIFT_PCT: continue

    pos_pct = (row.close - lo) / rng if rng else 0.5
    long_block = pos_pct > (1 - EDGE_PCT)
    short_block = pos_pct < EDGE_PCT

    longs  = sum(1 for s,_,_,_ in opens if s == "long")
    shorts = sum(1 for s,_,_,_ in opens if s == "short")

    opened = False
    if row.z <= -BASE_Z and not opened:
        need = BASE_Z + STEP_Z * longs
        if abs(row.z) >= need and not short_block:
            opens.append(("long", row.close, ts, longs + 1))
            opened = True
    if row.z >= BASE_Z and not opened:
        need = BASE_Z + STEP_Z * shorts
        if abs(row.z) >= need and not long_block:
            opens.append(("short", row.close, ts, shorts + 1))

log = pd.DataFrame(trades)
log.to_csv("v5_0_trades_112_full.csv", index=False)

wins = (log.pips > 0).mean() * 100
pf   = log.pips[log.pips > 0].sum() / -log.pips[log.pips < 0].sum()
print(f"V5.0 – trades {len(log)},  win {wins:.2f} %,  PF {pf:.2f}")
