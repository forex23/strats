import pandas as pd
import numpy as np
from datetime import timedelta

CSV_PATH = '/home/tradeops/exports/forex_1m_Mar_2025_EURGBP.csv'
df = pd.read_csv(CSV_PATH, parse_dates=['timestamp_utc'])
df = df.set_index('timestamp_utc').between_time('07:00', '17:00')
df.index = df.index.tz_convert('Europe/London')

print('| Edge % | Trades | Win Rate | Expect | Total Pips | Sharpe | Max DD |')
print('|--------|--------|----------|--------|-------------|--------|--------|')

for edge_pct in range(2, 21, 2):
    df_ = df.copy()
    df_['sma'] = df_['close'].rolling(30).mean()
    sig = df_['close'].rolling(5).std().clip(lower=0.0003)
    df_['z'] = (df_['close'] - df_['sma']) / sig
    df_['entry'] = df_['z'].abs() >= 1.95
    trades = []

    for ts, row in df_.iterrows():
        if not row['entry']: continue
        direction = -np.sign(row['z'])
        entry_price = row['close']
        stop_price = entry_price - direction * 0.0010
        tp_price = row['sma']
        expiry = ts + timedelta(minutes=30)

        exit_df = df_.loc[ts:expiry]
        exit_price = None

        for exit_ts, exit_row in exit_df.iterrows():
            if direction == 1 and exit_row['low'] <= stop_price:
                exit_price = stop_price; break
            elif direction == -1 and exit_row['high'] >= stop_price:
                exit_price = stop_price; break
            elif (direction == 1 and exit_row['high'] >= tp_price) or                  (direction == -1 and exit_row['low'] <= tp_price):
                exit_price = tp_price; break

        if exit_price is None:
            final_bar = exit_df.iloc[-1]
            exit_price = final_bar['close']

        pnl = (exit_price - entry_price) * 10000 * direction
        trades.append(pnl)

    trades = pd.Series(trades)
    if len(trades) == 0:
        print(f"| {edge_pct:>6} | {0:>6} | {0:>8.2f}% | {0:>6.2f} | {0:>11.2f} | {0:>6.2f} | {0:>6.2f} |")
        continue

    cum_pnl = trades.cumsum()
    win_rate = (trades > 0).mean() * 100
    expect = trades.mean()
    total_pips = trades.sum()
    sharpe = trades.mean() / (trades.std() + 1e-8)
    max_dd = (cum_pnl.cummax() - cum_pnl).max()

    print(f"| {edge_pct:>6} | {len(trades):>6} | {win_rate:>8.2f}% | {expect:>6.2f} | {total_pips:>11.2f} | {sharpe:>6.2f} | {max_dd:>6.2f} |")
