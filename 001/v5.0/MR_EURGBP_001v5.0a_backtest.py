
import pandas as pd, numpy as np, datetime as dt

CSV = "/home/tradeops/exports/forex_1m_Mar_2025_EURGBP.csv"
BASE_Z = 1.95
STEP_Z = 0.25
DRIFT = 0.0010
EDGE_PCT = 0.15
CAP = 5
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
    df = pd.read_csv(csv, parse_dates=["timestamp_utc"])
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df = df.set_index("timestamp_utc").tz_convert(TZ)
    df = df.between_time(*SESSION)
    df = df[["open", "high", "low", "close"]]
    df["date"] = df.index.date
    return df


def backtest(df):
    df["sma"] = df.close.rolling(MA_BARS).mean()
    sig = df.close.rolling(SIG_BARS).std().clip(lower=SIG_FLOOR)
    df["sigma"] = sig
    df["z"] = (df.close - df.sma) / df.sigma
    prev = df.close.shift()
    tr = np.maximum(df.high - df.low, np.maximum((df.high - prev).abs(), (df.low - prev).abs()))
    df["atr"] = tr.rolling(ATR_BARS).mean()
    df["vol_ok"] = df.atr * 1e4 >= ATR_GATE_P
    df = df.iloc[max(MA_BARS, SIG_BARS, ATR_BARS):]

    trades, opens = [], []
    hi = lo = today = None

    for ts, row in df.iterrows():
        if row.date != today:
            today = row.date
            hi, lo = row.high, row.low
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

        if len(opens) >= CAP or not row.vol_ok or pd.isna(row.z): continue
        if abs(row.close - row.sma) / row.sma < DRIFT: continue

        pos_pct = (row.close - lo) / rng if rng else 0.5
        long_block = pos_pct > (1 - EDGE_PCT)
        short_block = pos_pct < EDGE_PCT

        longs  = sum(1 for s,_,_,_ in opens if s == "long")
        shorts = sum(1 for s,_,_,_ in opens if s == "short")

        if row.z <= -BASE_Z:
            need = BASE_Z + STEP_Z * longs
            if abs(row.z) >= need and not short_block:
                opens.append(("long", row.close, ts, longs + 1))

        elif row.z >= BASE_Z:
            need = BASE_Z + STEP_Z * shorts
            if abs(row.z) >= need and not long_block:
                opens.append(("short", row.close, ts, shorts + 1))

    out = pd.DataFrame(trades)
    out.to_csv(f"V5_0a_trades_{dt.date.today()}.csv", index=False)
    print(f"V 5.0a  |  trades = {len(out)}  |  saved → V5_0a_trades_{dt.date.today()}.csv")


if __name__ == "__main__":
    backtest(load(CSV))
