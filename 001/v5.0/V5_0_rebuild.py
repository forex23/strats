import pandas as pd, numpy as np
from datetime import timedelta

# Settings
CSV_PATH = '/home/tradeops/exports/forex_1m_Mar_2025_EURGBP.csv'
OUT_PATH = '/home/tradeops/strats/meanrev/EURGBP/development/001/v5.0/V5_0_trades_2025-05-13.csv'
BASE_Z, STEP_Z = 1.95, 0.25
EDGE_PCT, DRIFT_PCT = 0.15, 0.001
MAX_TIX, STOP_PIPS, TIME_MIN = 5, 10, 30
MA_BARS, SIG_BARS, SIG_FLOOR = 30, 5, 0.00030
ATR_BARS, ATR_GATE_P = 5, 1.3
SESSION = ('07:00', '17:00')
TZ = 'Europe/London'

# Load and prep
df = pd.read_csv(CSV_PATH, parse_dates=['timestamp_utc'])
df = df.set_index('timestamp_utc').tz_convert(TZ)
df['date'] = df.index.date

out, opens = [], []
today, hi, lo = None, None, None

# Indicators
prev = df['close'].shift()
df['tr'] = np.maximum(df.high - df.low, np.maximum((df.high - prev).abs(), (df.low - prev).abs()))
df['sma'] = df['close'].rolling(MA_BARS, min_periods=MA_BARS).mean()
df['sigma'] = df['close'].rolling(SIG_BARS, min_periods=SIG_BARS).std().clip(lower=SIG_FLOOR)
df['z'] = (df['close'] - df['sma']) / df['sigma']
df['atr'] = df['tr'].rolling(ATR_BARS, min_periods=ATR_BARS).mean()
df['vol_ok'] = df['atr'] * 1e4 >= ATR_GATE_P

# Session dates
dates = sorted(df.between_time(*SESSION).index.normalize().unique())
for d in dates:
    day = df[(df.index >= f'{d} 06:30') & (df.index <= f'{d} 17:00')].copy()
    if len(day) < MA_BARS: continue

    hi, lo = None, None
    opens = []

    for ts, row in day.iterrows():
        if ts.time() == pd.to_datetime('07:00').time():
            hi, lo = row.high, row.low
        else:
            hi = max(hi, row.high) if hi is not None else row.high
            lo = min(lo, row.low) if lo is not None else row.low

        # exits
        still = []
        for side, ep, et, layer in opens:
            age = (ts - et).total_seconds() / 60
            exit_price = None
            if side == 'long':
                if row.low <= ep - STOP_PIPS / 1e4: exit_price = ep - STOP_PIPS / 1e4
                elif row.close >= row.sma: exit_price = row.close
                elif age >= TIME_MIN: exit_price = row.close
            else:
                if row.high >= ep + STOP_PIPS / 1e4: exit_price = ep + STOP_PIPS / 1e4
                elif row.close <= row.sma: exit_price = row.close
                elif age >= TIME_MIN: exit_price = row.close
            if exit_price is not None:
                pips = (exit_price - ep) * 1e4 if side == 'long' else (ep - exit_price) * 1e4
                out.append((ts, layer, side, pips))
            else:
                still.append((side, ep, et, layer))
        opens = still

        if ts.time() < pd.to_datetime(SESSION[0]).time() or ts.time() > pd.to_datetime(SESSION[1]).time():
            continue
        if len(opens) >= MAX_TIX or not row.vol_ok or pd.isna(row.z): continue
        if abs(row.close - row.sma) / row.sma < DRIFT_PCT: continue

        pos_pct = (row.close - lo) / (hi - lo) if hi != lo else 0.5
        if row.z > 0 and pos_pct > 1 - EDGE_PCT: continue
        if row.z < 0 and pos_pct < EDGE_PCT: continue

        # Layered logic
        longs = sum(1 for s,_,_,_ in opens if s == 'long')
        shorts = sum(1 for s,_,_,_ in opens if s == 'short')
        did_open = False

        if row.z <= -BASE_Z:
            need = BASE_Z + STEP_Z * longs
            if abs(row.z) >= need:
                opens.append(('long', row.close, ts, longs + 1))
                did_open = True
        elif row.z >= BASE_Z:
            need = BASE_Z + STEP_Z * shorts
            if abs(row.z) >= need:
                opens.append(('short', row.close, ts, shorts + 1))
                did_open = True

        if did_open:
            continue  # first-pass wins

pd.DataFrame(out, columns=['ts','layer','side','pips']).to_csv(OUT_PATH, index=False)
print(f'V5_0_rebuild | trades = {len(out)} | saved → {OUT_PATH}')
