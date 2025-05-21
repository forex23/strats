
# V 5.0 – Exact original run form
import pandas as pd, numpy as np, datetime as dt

CSV_PATH = "/home/tradeops/exports/forex_1m_Mar_2025_EURGBP.csv"
BASE_Z   = 1.95
STEP_Z   = 0.25
DRIFT_PCT= 0.001
EDGE_PCT = 0.15
MAX_TIX  = 5
STOP_PIPS= 10
TIME_MIN = 30
MA_BARS  = 30
SIG_BARS = 5
SIG_FLOOR= 0.00030
ATR_BARS = 5
ATR_GATE = 1.3
SESSION  = ("07:00","17:00")
TZ       = "Europe/London"

df = (pd.read_csv(CSV_PATH, parse_dates=["timestamp_utc"])
        .assign(timestamp_utc=lambda d: pd.to_datetime(d.timestamp_utc, utc=True))
        .set_index("timestamp_utc")
        .tz_convert(TZ)
        .between_time(*SESSION)
        [["open","high","low","close"]])
df["date"] = df.index.date
df["sma"]  = df.close.rolling(MA_BARS, min_periods=MA_BARS).mean()
sig        = df.close.rolling(SIG_BARS, min_periods=SIG_BARS).std()
df["sigma"]= sig.clip(lower=SIG_FLOOR)
df["z"]    = (df.close - df.sma) / df.sigma
prev       = df.close.shift()
tr         = np.maximum(df.high-df.low, np.maximum((df.high-prev).abs(), (df.low-prev).abs()))
df["atr"]  = tr.rolling(ATR_BARS, min_periods=ATR_BARS).mean()
df["vol_ok"] = df.atr*1e4 >= ATR_GATE

trades, opens = [], []
hi=lo=None; today=None

for ts,row in df.iterrows():
    if row.date!=today:
        today=row.date; hi=row.high; lo=row.low
    hi,lo = max(hi,row.high), min(lo,row.low); rng=hi-lo

    still=[]
    for s,ep,et,l in opens:
        hold=(ts-et).total_seconds()/60; ex=False; px=None
        if s=="long":
            if row.low<=ep-STOP_PIPS/1e4: px=ep-STOP_PIPS/1e4; ex=True
            elif row.close>=row.sma:      px=row.close; ex=True
            elif hold>=TIME_MIN:         px=row.close; ex=True
        else:
            if row.high>=ep+STOP_PIPS/1e4: px=ep+STOP_PIPS/1e4; ex=True
            elif row.close<=row.sma:       px=row.close; ex=True
            elif hold>=TIME_MIN:           px=row.close; ex=True
        if ex:
            pips=(px-ep)*1e4 if s=="long" else (ep-px)*1e4
            trades.append(pips)
        else:
            still.append((s,ep,et,l))
    opens=still

    if len(opens)>=MAX_TIX or not row.vol_ok or pd.isna(row.z): continue
    if abs(row.close-row.sma)/row.sma < DRIFT_PCT: continue

    pos_pct = (row.close-lo)/rng if rng else 0.5
    long_block  = pos_pct > (1 - EDGE_PCT)
    short_block = pos_pct < EDGE_PCT

    longs  = sum(1 for s,_,_,_ in opens if s=="long")
    shorts = sum(1 for s,_,_,_ in opens if s=="short")

    if row.z <= -BASE_Z:
        need = BASE_Z + STEP_Z*longs
        if abs(row.z) >= need and not short_block:
            opens.append(("long",row.close,ts,longs+1))
    elif row.z >= BASE_Z:
        need = BASE_Z + STEP_Z*shorts
        if abs(row.z) >= need and not long_block:
            opens.append(("short",row.close,ts,shorts+1))

pd.Series(trades).to_csv(f"V5_0_trades_{dt.date.today()}.csv", index=False, header=False)
print("Done – trades:", len(trades))
