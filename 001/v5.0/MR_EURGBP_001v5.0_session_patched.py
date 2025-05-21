import pandas as pd
import numpy as np
from datetime import timedelta

CSV_PATH = '/home/tradeops/exports/forex_1m_Mar_2025_EURGBP.csv'
df = pd.read_csv(CSV_PATH, parse_dates=['timestamp_utc'])
df = df.set_index('timestamp_utc').tz_convert('Europe/London')
df['date'] = df.index.date

out = []
unique_days = sorted(df.between_time('07:00', '17:00').index.normalize().unique())

for d in unique_days:
    prior_day = pd.Timestamp(d) - pd.Timedelta(days=1)
    session = pd.date_range(prior_day + pd.Timedelta(hours=16, minutes=30), pd.Timestamp(d) + pd.Timedelta(hours=17), freq='1min')
    day_df = df.reindex(session).dropna(subset=['close'])

    if len(day_df) < 100:
        continue

    day_df['sma'] = day_df['close'].rolling(30, min_periods=30).mean()
    sig = day_df['close'].rolling(5, min_periods=5).std().clip(lower=0.0003)
    day_df['z'] = (day_df['close'] - day_df['sma']) / sig

    day_df['hi'] = day_df['high'].where(day_df.index.time == pd.to_datetime('07:00').time(), np.nan)
    day_df['lo'] = day_df['low'].where(day_df.index.time == pd.to_datetime('07:00').time(), np.nan)
    day_df['hi'] = day_df['high'].cummax()
    day_df['lo'] = day_df['low'].cummin()
    day_df['pos_pct'] = (day_df['close'] - day_df['lo']) / (day_df['hi'] - day_df['lo']).replace(0, np.nan)

    trades = []
    for ts, row in day_df.between_time('07:00', '17:00').iterrows():
        if row['z'] > 0 and row['pos_pct'] > (1 - 0.15): continue
        if row['z'] < 0 and row['pos_pct'] < 0.15: continue
        if abs(row['z']) < 1.95: continue

        direction = -np.sign(row['z'])
        entry_price = row['close']
        stop_price = entry_price - direction * 0.0010
        tp_price = row['sma']
        expiry = ts + timedelta(minutes=30)

        exit_df = day_df.loc[ts:expiry]
        exit_price = None

        for _, exit_row in exit_df.iterrows():
            if direction == 1 and exit_row['low'] <= stop_price:
                exit_price = stop_price; break
            elif direction == -1 and exit_row['high'] >= stop_price:
                exit_price = stop_price; break
            elif (direction == 1 and exit_row['high'] >= tp_price) or                  (direction == -1 and exit_row['low'] <= tp_price):
                exit_price = tp_price; break

        if exit_price is None:
            exit_price = exit_df.iloc[-1]['close']

        pnl = (exit_price - entry_price) * 10000 * direction
        trades.append((ts, 1, 'long' if direction == 1 else 'short', pnl))

    out.extend(trades)

out_df = pd.DataFrame(out, columns=['ts','layer','side','pips'])
out_df.to_csv('/home/tradeops/strats/meanrev/EURGBP/development/001/v5.0/V5_0_trades_2025-05-12.csv', index=False)
print(f"V 5.0 session patched | trades = {len(out_df)}")
