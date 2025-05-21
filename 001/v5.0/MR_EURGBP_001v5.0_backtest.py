# V 5.0 – Fully patched with warm-up drop for Pandas 2.x compatibility
import pandas as pd, numpy as np, datetime as dt, pathlib

CSV_PATH = "/home/tradeops/exports/forex_1m_Mar_2025_EURGBP.csv"
OUT_CSV = f"V5_0_trades_{dt.date.today()}.csv"

BASE_Z = 1.95
STEP_Z = 0.25
DRIFT_PCT = 0.001
EDGE_PCT = 0.15
MAX_TIX = 5
STOP_PIPS = 10
TIME_MIN = 30
MA_BARS = 30
SIG_BARS = 5
SIG_FLOOR = 0.00030
ATR_BARS = 5
ATR_GATE_P = 1.3
SESSION = ("07:00", "17:00")
TZ = "Europe/London"

def load(csv):
    df = (pd.read_csv(csv, parse_dates=["timestamp_utc"])
            .assign(timestamp_utc=lambda d: pd.to_datetime(d.timestamp_utc, utc=True))
            .set_index("timestamp_utc")
            .tz_convert(TZ)
            .between_time(*SESSION)
            [["open","high","low","close"]])
    df["date"] = df.index.date
    return df

def backtest(df):
    df["sma"] = df.close.rolling(MA_BARS, min_periods=MA_BARS).mean()
    sig = df.close.rolling(SIG_BARS, min_periods=SIG_BARS).std()
    df["sigma"] = sig.clip(lower=SIG_FLOOR)
    df["z"] = (df.close - df.sma) / df.sigma
    prev = df.close.shift()
    tr = np.maximum(df.high - df.low, np.maximum((df.high - prev).abs(), (df.low - prev).abs()))
    df["atr"] = tr.rolling(ATR_BARS, min_periods=ATR_BARS).mean()
    df["vol_ok"] = df.atr * 1e4 >= ATR_GATE_P

    # Patch for Pandas version drift
    warmup = max(MA_BARS, SIG_BARS, ATR_BARS)
    df = df.iloc[warmup:]

    trades, opens = [], []
    hi = lo = today = None

    for ts, row in df.iterrows():
        if row.date != today:
            today = row.date; hi = row.high; lo = row.low
        hi, lo = max(hi, row.high), min(lo, row.low)
        rng = hi - lo

        still = []
        for side, ep, et, layer in opens:
            hold = (ts - et).total_seconds() / 60
            ex, px = False, None
            if side == "long":
                if row.low <= ep - STOP_PIPS / 1e4: px, ex = ep - STOP_PIPS / 1e4, True
                elif row.close >= row.sma:         px, ex = row.close, True
                elif hold >= TIME_MIN:             px, ex = row.close, True
            else:
                if row.high >= ep + STOP_PIPS / 1e4: px, ex = ep + STOP_PIPS / 1e4, True
                elif row.close <= row.sma:          px, ex = row.close, True
                elif hold >= TIME_MIN:              px, ex = row.close, True
            if ex:
                pips = (px - ep) * 1e4 if side == "long" else (ep - px) * 1e4
                trades.append({"ts": ts, "layer": layer, "side": side, "pips": pips})
            else:
                still.append((side, ep, et, layer))
        opens = still

        if len(opens) >= MAX_TIX or not row.vol_ok or pd.isna(row.z): continue
        if abs(row.close - row.sma) / row.sma < DRIFT_PCT: continue

        pos_pct = (row.close - lo) / rng if rng else 0.5
        if row.z > 0 and pos_pct > (1 - EDGE_PCT): continue
        if row.z < 0 and pos_pct < EDGE_PCT: continue

        longs = sum(1 for s, _, _, _ in opens if s == "long")
        shorts = sum(1 for s, _, _, _ in opens if s == "short")

        if row.z <= -BASE_Z:
            need = BASE_Z + STEP_Z * longs
            if abs(row.z) >= need:
                opens.append(("long", row.close, ts, longs + 1))
        elif row.z >= BASE_Z:
            need = BASE_Z + STEP_Z * shorts
            if abs(row.z) >= need:
                opens.append(("short", row.close, ts, shorts + 1))

    return pd.DataFrame(trades)

if __name__ == "__main__":
    df = load(CSV_PATH)
    log = backtest(df)
    log.to_csv(OUT_CSV, index=False)
    print(f"V 5.0  |  trades = {len(log)}  |  saved → {OUT_CSV}")
