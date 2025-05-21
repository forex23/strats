"""
V1.0  –  Z ±1.25 σ   (no drift, no escalator, no caps)
"""
import pandas as pd, numpy as np, datetime as dt, pathlib

# ---------- PARAMETERS -------------------------------------------------
CSV         = "/data/forex/minute/forex_1m_Mar_2025_EURGBP.csv"
BASE_Z      = 1.25
STEP_Z      = 0.00
DRIFT_PCT   = None
EDGE_PCT    = None      # long block >(1-EDGE), short block <EDGE
MAX_TIX     = 10**9
TAG         = "V1.0"

# ---------- CONSTANTS (shared) -----------------------------------------
STOP_PIPS   = 10
TIME_MIN    = 30
MA_BARS     = 30
SIG_BARS    = 5
SIG_FLOOR   = 0.00030
ATR_BARS    = 5
ATR_GATE_P  = 1.3         # pips
SESSION     = ("07:00","17:00")
TZ          = "Europe/London"
# -----------------------------------------------------------------------

def load(csv):
    df = (pd.read_csv(csv, parse_dates=["timestamp_utc"])
            .assign(timestamp_utc=lambda d: pd.to_datetime(d.timestamp_utc, utc=True))
            .set_index("timestamp_utc")
            .tz_convert(TZ)
            .between_time(*SESSION)
            [["open","high","low","close"]])
    df["date"] = df.index.date
    return df

def backtest():
    df = load(CSV)
    df["sma"]   = df.close.rolling(MA_BARS, min_periods=MA_BARS).mean()
    sig         = df.close.rolling(SIG_BARS, min_periods=SIG_BARS).std()
    df["sigma"] = sig.clip(lower=SIG_FLOOR)
    df["z"]     = (df.close - df.sma) / df.sigma
    prev        = df.close.shift()
    tr          = np.maximum(df.high-df.low,
                             np.maximum((df.high-prev).abs(), (df.low-prev).abs()))
    df["atr"]   = tr.rolling(ATR_BARS, min_periods=ATR_BARS).mean()
    df["vol_ok"] = df.atr*1e4 >= ATR_GATE_P

    trades, opens = [], []
    hi=lo=None; today=None

    for ts,row in df.iterrows():
        if row.date!=today:
            today=row.date; hi=row.high; lo=row.low
        hi,lo = max(hi,row.high), min(lo,row.low)
        rng   = hi-lo

        # ------------- exits
        still=[]
        for s,ep,et in opens:
            dur=(ts-et).total_seconds()/60; ex=False; px=None
            if s=="long":
                if row.low<=ep-STOP_PIPS/1e4: px=ep-STOP_PIPS/1e4; ex=True
                elif row.close>=row.sma:      px=row.close; ex=True
                elif dur>=TIME_MIN:           px=row.close; ex=True
            else:
                if row.high>=ep+STOP_PIPS/1e4: px=ep+STOP_PIPS/1e4; ex=True
                elif row.close<=row.sma:       px=row.close; ex=True
                elif dur>=TIME_MIN:           px=row.close; ex=True
            if ex:
                pips=(px-ep)*1e4 if s=="long" else (ep-px)*1e4
                trades.append(pips)
            else:
                still.append((s,ep,et))
        opens=still

        # ------------- entry guards
        if len(opens)>=MAX_TIX or not row.vol_ok or pd.isna(row.z):
            continue
        if DRIFT_PCT and abs(row.close-row.sma)/row.sma < DRIFT_PCT:
            continue
        pos_pct=(row.close-lo)/rng if rng else 0.5
        if EDGE_PCT:
            if row.z>0 and pos_pct>(1-EDGE_PCT): continue
            if row.z<0 and pos_pct<EDGE_PCT:     continue

        if row.z <= -BASE_Z:
            opens.append(("long",row.close,ts))
        elif row.z >=  BASE_Z:
            opens.append(("short",row.close,ts))

    out = pathlib.Path(f"{TAG}_trades_{dt.date.today()}.csv")
    pd.Series(trades).to_csv(out, index=False, header=False)
    print(f"{TAG}: trades={len(trades)}  saved→{out}")

if __name__ == "__main__":
    backtest()
